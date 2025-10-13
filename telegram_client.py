from __future__ import annotations

import asyncio
import atexit
import os
import logging
import random
import threading
import time
from collections import defaultdict
from typing import Optional, Dict, Any, List

import httpx

from database import SessionLocal, Setting

logger = logging.getLogger("telegram")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

_COUNTER_BUFFER: Dict[str, int] = defaultdict(int)
_COUNTER_LOCK = threading.Lock()
_LAST_FLUSH = 0.0
_FLUSH_INTERVAL = float(os.getenv("TELEGRAM_COUNTER_FLUSH_INTERVAL", "5.0"))
_FLUSH_THRESHOLD = int(os.getenv("TELEGRAM_COUNTER_FLUSH_THRESHOLD", "10"))


def _flush_counters(force: bool = False) -> None:
    global _LAST_FLUSH
    with _COUNTER_LOCK:
        if not _COUNTER_BUFFER:
            return
        now = time.time()
        if not force:
            if (now - _LAST_FLUSH) < _FLUSH_INTERVAL and all(value < _FLUSH_THRESHOLD for value in _COUNTER_BUFFER.values()):
                return
        payload = dict(_COUNTER_BUFFER)
        _COUNTER_BUFFER.clear()
        _LAST_FLUSH = now

    db = SessionLocal()
    try:
        for key, inc in payload.items():
            row = db.query(Setting).filter(Setting.key == key).first()
            if row is None:
                db.add(Setting(key=key, value=int(inc)))
                continue
            try:
                current = int(row.value)
            except Exception:
                current = 0
            row.value = current + int(inc)
        db.commit()
    except Exception as exc:
        logger.warning("Counter flush failed: %s", exc)
    finally:
        db.close()


def _bump_setting(key: str, inc: int = 1) -> None:
    """Queue a metric increment and flush periodically."""
    should_flush = False
    with _COUNTER_LOCK:
        _COUNTER_BUFFER[key] += inc
        if _COUNTER_BUFFER[key] >= _FLUSH_THRESHOLD:
            should_flush = True
        elif (time.time() - _LAST_FLUSH) >= _FLUSH_INTERVAL:
            should_flush = True

    if should_flush:
        _flush_counters()


atexit.register(lambda: _flush_counters(force=True))


class TelegramClient:
    """
    Basit Telegram Bot API istemcisi.
    - Async httpx kullanır
    - 429/5xx için güvenli tekrar/backoff
    - send_message / send_typing / try_set_reaction sağlar
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")
        timeout = float(os.getenv("TELEGRAM_TIMEOUT", "20"))
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
        self.client = httpx.AsyncClient(timeout=timeout, limits=limits)

    def _url(self, token: str, method: str) -> str:
        return f"{self.base_url}/bot{token}/{method}"

    async def _post(self, token: str, method: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        POST request with exponential backoff retry logic.

        Retry strategy:
        - 429 (rate limit): Use Retry-After header or exponential backoff with jitter
        - 5xx (server errors): Exponential backoff with jitter
        - Network errors: Exponential backoff with jitter
        """
        url = self._url(token, method)
        max_retries = int(os.getenv("TELEGRAM_MAX_RETRIES", "5"))
        base_delay = float(os.getenv("TELEGRAM_BASE_DELAY", "1.0"))
        max_delay = float(os.getenv("TELEGRAM_MAX_DELAY", "60.0"))

        for attempt in range(1, max_retries + 1):
            try:
                r = await self.client.post(url, json=payload)

                # Handle rate limiting (429)
                if r.status_code == 429:
                    _bump_setting("telegram_429_count", 1)
                    retry_after = r.headers.get("retry-after")

                    if retry_after:
                        # Respect Telegram's Retry-After header
                        sleep_s = min(float(retry_after), max_delay)
                    else:
                        # Exponential backoff: base_delay * 2^(attempt-1) + jitter
                        exp_delay = base_delay * (2 ** (attempt - 1))
                        jitter = random.uniform(0, exp_delay * 0.1)  # 10% jitter
                        sleep_s = min(exp_delay + jitter, max_delay)

                    logger.warning(
                        "Telegram 429 (%s) on attempt %d/%d. Backoff %.1fs",
                        method, attempt, max_retries, sleep_s
                    )
                    await asyncio.sleep(sleep_s)
                    continue

                # Handle server errors (5xx)
                if r.status_code >= 500:
                    _bump_setting("telegram_5xx_count", 1)
                    _bump_setting("rate_limit_hits", 1)  # Backward compatibility

                    # Exponential backoff with jitter
                    exp_delay = base_delay * (2 ** (attempt - 1))
                    jitter = random.uniform(0, exp_delay * 0.1)
                    sleep_s = min(exp_delay + jitter, max_delay)

                    logger.warning(
                        "Telegram %s server error %s on attempt %d/%d. Retry in %.1fs",
                        method, r.status_code, attempt, max_retries, sleep_s
                    )
                    await asyncio.sleep(sleep_s)
                    continue

                # Success path
                r.raise_for_status()
                data = r.json()
                if not data.get("ok", False):
                    desc = data.get("description", "Unknown error")
                    logger.warning("Telegram %s API error: %s", method, desc)
                    return None
                return data.get("result")

            except httpx.HTTPError as e:
                # Network/connection errors - exponential backoff
                exp_delay = base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, exp_delay * 0.1)
                sleep_s = min(exp_delay + jitter, max_delay)

                logger.warning(
                    "HTTP error on %s attempt %d/%d: %s. Retry in %.1fs",
                    method, attempt, max_retries, e, sleep_s
                )

                if attempt < max_retries:
                    await asyncio.sleep(sleep_s)
                else:
                    logger.error("Max retries exceeded for %s: %s", method, e)

            except Exception as e:
                logger.exception("Unexpected error on %s attempt %d/%d: %s", method, attempt, max_retries, e)
                return None

        return None

    # -----------------------------
    # Public API
    # -----------------------------
    async def send_message(
        self,
        token: str,
        chat_id: str | int,
        text: str,
        reply_to_message_id: Optional[int] = None,
        disable_preview: bool = True,
        parse_mode: Optional[str] = None,
    ) -> Optional[int]:
        """Mesaj gönder ve Telegram message_id döndür."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": bool(disable_preview),
            # "allow_sending_without_reply": True  # istersen aç
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True
        if parse_mode:
            payload["parse_mode"] = parse_mode

        result = await self._post(token, "sendMessage", payload)
        if not result:
            return None
        try:
            return int(result.get("message_id"))
        except Exception:
            return None

    async def send_typing(self, token: str, chat_id: str | int, duration_seconds: float = 3.0) -> None:
        """
        'typing' göstergesini duration boyunca 2.5 sn aralıklarla yeniler.
        Telegram, typing action'un birkaç saniye sonra sönmesini bekler.
        """
        duration_seconds = max(0.5, float(duration_seconds))
        end_ts = asyncio.get_event_loop().time() + duration_seconds
        payload = {"chat_id": chat_id, "action": "typing"}
        while asyncio.get_event_loop().time() < end_ts:
            try:
                await self._post(token, "sendChatAction", payload)
            except Exception as e:
                logger.debug("sendChatAction error: %s", e)
            await asyncio.sleep(2.5)

    async def try_set_reaction(
        self,
        token: str,
        chat_id: str | int,
        message_id: Optional[int],
        emojis: Optional[List[str]] = None,
        is_big: bool = False,
    ) -> bool:
        """
        Bot API 6.7+ / 7.x sürümlerinde 'setMessageReaction' desteklenir.
        Destek yoksa veya hata alırsak False döndürür.
        """
        if not message_id:
            return False

        emojis = emojis or ["👍", "🔥", "💡", "📈", "📉", "✅", "👌"]
        # ReactionTypeEmoji formatı
        reaction = [{"type": "emoji", "emoji": emojis[0]}]

        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": reaction,
            "is_big": bool(is_big),
        }
        result = await self._post(token, "setMessageReaction", payload)
        return bool(result)

    async def close(self):
        try:
            await self.client.aclose()
        except Exception:
            pass
