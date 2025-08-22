from __future__ import annotations

import asyncio
import os
import logging
from typing import Optional, Dict, Any, List

import httpx

from database import SessionLocal, Setting

logger = logging.getLogger("telegram")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def _bump_setting(key: str, inc: int = 1) -> None:
    """settings.key bir sayaçsa artır (ör. telegram_429_count)."""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == key).first()
        if row is None:
            db.add(Setting(key=key, value=int(inc)))
        else:
            try:
                val = int(row.value)
            except Exception:
                val = 0
            row.value = int(val) + inc
        db.commit()
    except Exception as e:
        logger.warning("Setting bump failed for %s: %s", key, e)
    finally:
        db.close()


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
        url = self._url(token, method)
        for attempt in range(1, 4):
            try:
                r = await self.client.post(url, json=payload)
                if r.status_code == 429:
                    _bump_setting("telegram_429_count", 1)
                    retry_after = r.headers.get("retry-after")
                    sleep_s = float(retry_after) if retry_after else 2.0 * attempt
                    logger.warning("Telegram 429 (%s). Backoff %.1fs", method, sleep_s)
                    await asyncio.sleep(sleep_s)
                    continue

                if r.status_code >= 500:
                    # Yeni: 5xx hataları ayrı sayaçta
                    _bump_setting("telegram_5xx_count", 1)
                    # Eski geri uyumluluk: rate_limit_hits'i de artır (yakında kaldırılabilir)
                    _bump_setting("rate_limit_hits", 1)
                    sleep_s = 1.0 * attempt
                    logger.warning("Telegram %s server error %s. Retry in %.1fs", method, r.status_code, sleep_s)
                    await asyncio.sleep(sleep_s)
                    continue

                r.raise_for_status()
                data = r.json()
                if not data.get("ok", False):
                    # Bot API 'ok':false ise hata mesajını logla
                    desc = data.get("description")
                    logger.warning("Telegram %s error: %s", method, desc)
                    return None
                return data.get("result")

            except httpx.HTTPError as e:
                logger.warning("HTTP error on %s attempt %d: %s", method, attempt, e)
                await asyncio.sleep(1.0 * attempt)
            except Exception as e:
                logger.exception("Unexpected error on %s: %s", method, e)
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
