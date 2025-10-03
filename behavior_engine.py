from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import random
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Sequence

from sqlalchemy.orm import Session

from database import (
    SessionLocal, Bot, Chat, Message, Setting,
    BotStance, BotHolding,
)
from settings_utils import (
    DEFAULT_MESSAGE_LENGTH_PROFILE,
    normalize_message_length_profile,
    unwrap_setting_value,
)
from llm_client import LLMClient
from system_prompt import (
    generate_user_prompt,
    summarize_persona,
    summarize_stances,
)
from telegram_client import TelegramClient
from news_client import NewsClient, DEFAULT_FEEDS  # <-- HABER TETIKLEYICI

logger = logging.getLogger("behavior")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

UTC = timezone.utc

# Çalışan engine'in referansı (worker.py 'shutdown' çağırabilsin diye)
_ENGINE: Optional["BehaviorEngine"] = None


# ---------------------------
# Yardımcı fonksiyonlar
# ---------------------------
TOPIC_KEYWORDS: Dict[str, set] = {
    "bist": {"bist", "borsa", "hisse", "hisseler", "bist100", "x100"},
    "fx": {"fx", "doviz", "döviz", "kur", "usd", "eur", "parite"},
    "kripto": {"kripto", "crypto", "bitcoin", "btc", "eth", "ethereum", "altcoin", "coin"},
    "makro": {"makro", "enflasyon", "faiz", "ekonomi", "gsyih", "büyüme", "veri"},
}

def now_utc() -> datetime:
    return datetime.now(UTC)


def exp_delay(mean_seconds: float) -> float:
    """Exponential (Poisson process) gecikme üreten yardımcı."""
    if mean_seconds <= 0:
        return 1.0
    return random.expovariate(1.0 / mean_seconds)


def parse_ranges(ranges: List[str]) -> List[tuple]:
    """
    "HH:MM-HH:MM" listesi -> [(start_min, end_min), ...]
    Zamanlar yerel saat varsayımıyla yorumlanır; burada sadece göreli hız için kullanıyoruz.
    """
    out = []
    for r in ranges or []:
        try:
            a, b = r.split("-")
            sh, sm = [int(x) for x in a.split(":")]
            eh, em = [int(x) for x in b.split(":")]
            out.append((sh * 60 + sm, eh * 60 + em))
        except Exception:
            continue
    return out


def is_prime_hours(ranges: List[str]) -> bool:
    local = datetime.now()  # sistemin yerel saati (sunucu)
    hm = local.hour * 60 + local.minute
    if not ranges:
        return False
    return _time_matches_ranges(ranges, hm)


def _time_matches_ranges(ranges: List[str], minute_of_day: int) -> bool:
    for (s, e) in parse_ranges(ranges):
        if s <= e:
            if s <= minute_of_day <= e:
                return True
        else:
            # Gece yarısı devreden aralık (örn. 22:00-02:00)
            if minute_of_day >= s or minute_of_day <= e:
                return True
    return False


def is_within_active_hours(ranges: Optional[List[str]], *, moment: Optional[datetime] = None) -> bool:
    """Yerel zamana göre active_hours aralığında mı? Liste boşsa her zaman aktif say."""

    if not ranges:
        return True

    local = moment or datetime.now()
    hm = local.hour * 60 + local.minute
    return _time_matches_ranges(list(ranges), hm)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def shorten(s: Optional[str], max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def _resolve_message_speaker(message: Any) -> str:
    """Best effort speaker label for history transcripts."""

    bot = getattr(message, "bot", None)
    if bot is not None:
        username = getattr(bot, "username", None)
        if isinstance(username, str) and username.strip():
            return username.lstrip("@")
        name = getattr(bot, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
        bot_id = getattr(message, "bot_id", None)
        if bot_id is not None:
            return f"Bot#{bot_id}"
        return "Bot"

    # İnsan katılımcılar için potansiyel alanlar
    for attr in ("sender_name", "author_name", "display_name"):
        candidate = getattr(message, attr, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    meta = getattr(message, "meta", None)
    if isinstance(meta, dict):
        for key in ("sender_name", "username", "author", "display_name"):
            candidate = meta.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    chat = getattr(message, "chat", None)
    if chat is not None:
        title = getattr(chat, "title", None)
        if isinstance(title, str) and title.strip():
            return title.strip()

    return "Kullanıcı"


def build_history_transcript(messages: Sequence[Any]) -> str:
    """Create a multi-line dialog transcript from chronological messages."""

    lines: List[str] = []
    for msg in messages:
        if msg is None:
            continue
        text = getattr(msg, "text", "") or ""
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            text = "(boş)"
        snippet = shorten(text, 180)
        speaker = _resolve_message_speaker(msg)
        lines.append(f"[{speaker}]: {snippet}")

    return "\n".join(lines)


def _tokenize_messages(messages: Sequence[Any]) -> Counter:
    tokens: Counter = Counter()
    for msg in messages:
        if msg is None:
            continue
        text = getattr(msg, "text", None)
        if not isinstance(text, str):
            continue
        for raw_token in text.split():
            token = raw_token.strip().lower()
            token = token.strip("#.,;:!?()[]{}\"'`“”’")
            if not token:
                continue
            tokens[token] += 1
    return tokens


def score_topics_from_messages(messages: Sequence[Any], topics: Sequence[str]) -> Dict[str, float]:
    """Basit anahtar kelime eşleşmesiyle mesajlara göre topic skorla."""

    if not topics:
        return {}

    topic_list = [t for t in topics if isinstance(t, str) and t.strip()]
    if not topic_list:
        return {}

    token_counts = _tokenize_messages(messages)
    if not token_counts:
        return {}

    joined_text = " ".join(token_counts.elements())
    scores: Dict[str, float] = {}

    for topic in topic_list:
        topic_key = topic.strip()
        topic_lower = topic_key.lower()
        keywords = set()
        keywords.add(topic_lower)
        keywords.update(TOPIC_KEYWORDS.get(topic_lower, set()))
        keywords.update(k for k in re.split(r"[^\wçğıöşü]+", topic_lower) if k)

        score = 0.0
        for kw in keywords:
            if not kw:
                continue
            score += token_counts.get(kw, 0)
            if kw not in token_counts and kw in joined_text:
                score += 0.2

        if score > 0:
            scores[topic_key] = score

    return scores


def choose_topic_from_messages(
    messages: Sequence[Any],
    topic_candidates: Sequence[str],
    fallback_defaults: Optional[Sequence[str]] = None,
    *,
    rng: Optional[random.Random] = None,
) -> str:
    """Mesajlara bakarak topic seç; eşleşme yoksa rastgele fallback kullan."""

    rng = rng or random
    fallback_pool = list(fallback_defaults or ["BIST", "FX", "Kripto", "Makro"])
    candidates = [t for t in topic_candidates or [] if isinstance(t, str) and t.strip()]

    scored = score_topics_from_messages(messages, candidates)
    if scored:
        max_score = max(scored.values())
        best = [topic for topic, score in scored.items() if score == max_score]
        return rng.choice(best)

    if candidates:
        return rng.choice(candidates)

    return rng.choice(fallback_pool)


def choose_message_length_category(
    profile: Optional[Dict[str, float]], *, rng: Optional[random.Random] = None
) -> str:
    """Sample a message length category from a normalized profile."""

    if not isinstance(profile, dict):
        profile = DEFAULT_MESSAGE_LENGTH_PROFILE

    rng = rng or random
    cutoff = rng.random()

    cumulative = 0.0
    chosen = None
    for key in DEFAULT_MESSAGE_LENGTH_PROFILE:
        weight = float(profile.get(key, 0.0))
        if weight < 0:
            weight = 0.0
        cumulative += weight
        if cutoff <= cumulative:
            chosen = key
            break

    if chosen is None:
        chosen = next(iter(DEFAULT_MESSAGE_LENGTH_PROFILE))

    return chosen


_MESSAGE_LENGTH_HINTS = {
    "short": "bu tur: kısa tut (1-2 cümle)",
    "medium": "bu tur: orta uzunluk (2-3 cümle)",
    "long": "bu tur: biraz daha detay (3-4 cümle)",
}


def compose_length_hint(
    *, persona_profile: Optional[Dict[str, Any]], selected_category: str
) -> str:
    """Combine persona style length with the sampled category hint."""

    parts: List[str] = []
    if persona_profile:
        style = persona_profile.get("style") or {}
        persona_length = style.get("length")
        if persona_length:
            parts.append(str(persona_length))

    parts.append(_MESSAGE_LENGTH_HINTS.get(selected_category, selected_category))

    return " | ".join(parts)


def normalize_text(s: str) -> str:
    """Tekrar kontrolü için basit normalizasyon."""
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)          # sık boşlukları tek boşluğa indir
    s = re.sub(r"[^\w\sçğıöşü]", "", s) # emojiler/işaretler hariç sadeleştir
    return s[:400]  # kısa kesit yeterli


# ---------------------------
# Ayar okuma
# ---------------------------
def load_settings(db: Session) -> Dict[str, Any]:
    rows = db.query(Setting).all()
    d = {r.key: unwrap_setting_value(r.value) for r in rows}
    # Varsayılanlar (güvenli)
    d.setdefault("max_msgs_per_min", 6)
    d.setdefault("typing_enabled", True)
    d.setdefault("prime_hours_boost", True)
    d.setdefault("prime_hours", ["09:30-12:00", "14:00-18:00"])
    d.setdefault("reply_probability", 0.65)
    d.setdefault("mention_probability", 0.35)
    d.setdefault("short_reaction_probability", 0.12)
    d.setdefault("new_message_probability", 0.35)
    d.setdefault("message_length_profile", DEFAULT_MESSAGE_LENGTH_PROFILE.copy())
    d["message_length_profile"] = normalize_message_length_profile(d.get("message_length_profile"))
    d.setdefault("typing_speed_wpm", {"min": 2.5, "max": 4.5})
    d.setdefault("bot_hourly_msg_limit", {"min": 6, "max": 12})
    d.setdefault("simulation_active", False)
    d.setdefault("scale_factor", 1.0)
    # Tutarlılık koruması
    d.setdefault("consistency_guard_enabled", True)
    # Dedup ve cooldown ayarları
    d.setdefault("dedup_enabled", True)
    d.setdefault("dedup_window_hours", 12)   # son 12 saatte aynı metni engelle
    d.setdefault("dedup_max_attempts", 2)    # yeniden yazdırma denemesi
    d.setdefault("cooldown_filter_enabled", True)  # cooldown aktif konuları topic seçiminden çıkar
    # HABER tetikleyici
    d.setdefault("news_trigger_enabled", True)     # market_trigger aktif mi?
    d.setdefault("news_trigger_probability", 0.75) # %75 olasılıkla tetik kullan

    stored_feeds = d.get("news_feed_urls")
    if not isinstance(stored_feeds, list):
        stored_feeds = []
    stored_feeds = [str(u).strip() for u in stored_feeds if str(u).strip()]

    env_urls = os.getenv("NEWS_RSS_URLS", "")
    env_feeds = [u.strip() for u in env_urls.split(",") if u.strip()]

    merged: List[str] = []
    for candidate in env_feeds + stored_feeds:
        if candidate not in merged:
            merged.append(candidate)

    d["news_feed_urls"] = merged or list(DEFAULT_FEEDS)
    return d


# ---------------------------
# Engine sınıfı
# ---------------------------
class BehaviorEngine:
    """
    - Aktif sohbetler ve botları DB'den seçer
    - Poisson gecikme, reply/@mention, typing simülasyonu, reaksiyon uygular
    - Limitlere saygı duyar (dk başı, saat başı)
    - Redis 'config_updates' kanalını dinleyip ayar cache'ini canlı günceller (opsiyonel)
    - Botun persona/stance/holding bilgilerini prompt'a enjekte eder
    - Tutarlılık koruması: çıktı STANCE ve cooldown kurallarıyla çelişirse yumuşak düzeltme yapar
    - Dedup: son X saatte aynı metni tekrar etmeyi önler
    - Cooldown filtre: cooldown’u bitmemiş konuları topic seçiminden çıkarır
    - Haber tetikleyici: RSS’ten kısa “gündem” cümlesi ekler (market_trigger)
    """

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.tg = TelegramClient()
        self._last_settings: Dict[str, Any] = {}
        self._settings_loaded_at: datetime = datetime.min.replace(tzinfo=UTC)

        # Haber tetikleyici (opsiyonel, bağımlılık yoksa bozulmasın)
        self.news: Optional[NewsClient] = None
        try:
            self.news = NewsClient()
        except Exception as e:
            logger.warning("NewsClient init failed: %s", e)
            self.news = None
        self._active_news_feeds: List[str] = list(self.news.feeds) if self.news else []

        # Redis (opsiyonel) - async subscriber
        self._redis_url: Optional[str] = os.getenv("REDIS_URL") or None
        self._redis = None  # type: ignore
        self._redis_task: Optional[asyncio.Task] = None

    # ---- Settings cache ----
    def settings(self, db: Session) -> Dict[str, Any]:
        if (now_utc() - self._settings_loaded_at) > timedelta(seconds=15):
            self._last_settings = load_settings(db)
            self._settings_loaded_at = now_utc()
            feeds = self._last_settings.get("news_feed_urls")
            if isinstance(feeds, list):
                self._update_news_feeds(feeds)
        return self._last_settings

    def _invalidate_settings_cache(self):
        # Bir sonraki erişimde yeniden yüklensin
        self._settings_loaded_at = datetime.min.replace(tzinfo=UTC)
        logger.info("Settings cache invalidated via config update.")

    def _update_news_feeds(self, feeds: List[str]) -> None:
        if self.news is None:
            return
        normalized = [str(u).strip() for u in feeds if str(u).strip()]
        if not normalized:
            normalized = list(DEFAULT_FEEDS)
        if normalized == self._active_news_feeds:
            return
        try:
            self.news.set_feeds(normalized)
            self._active_news_feeds = list(self.news.feeds)
            logger.info("News feed list updated (%d entries).", len(self._active_news_feeds))
        except Exception as exc:
            logger.warning("Failed to update news feeds: %s", exc)

    # ---- Redis listener ----
    async def _config_listener(self):
        """
        REDIS_URL varsa 'config_updates' kanalını dinler. Her mesajda settings cache invalid edilir.
        """
        if not self._redis_url:
            return

        try:
            # redis>=4.2 ile birlikte gelen asyncio istemcisini kullan
            from redis import asyncio as aioredis  # type: ignore
        except Exception:
            logger.warning("redis.asyncio bulunamadı; canlı config sync devre dışı.")
            return

        try:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("config_updates")
            logger.info("Subscribed to Redis channel: config_updates")

            async for m in pubsub.listen():
                if m is None:
                    await asyncio.sleep(0.1)
                    continue
                if m.get("type") != "message":
                    continue
                try:
                    data = json.loads(m.get("data") or "{}")
                except Exception:
                    data = {}

                # Şimdilik herkes için cache invalid
                self._invalidate_settings_cache()

                if (
                    self.news is not None
                    and isinstance(data.get("keys"), list)
                    and "news_feed_urls" in data.get("keys", [])
                ):
                    try:
                        db = SessionLocal()
                        try:
                            fresh = load_settings(db)
                        finally:
                            db.close()
                        feeds = fresh.get("news_feed_urls")
                        if isinstance(feeds, list):
                            self._update_news_feeds(feeds)
                    except Exception as exc:
                        logger.warning("Failed to refresh news feeds after config update: %s", exc)

                # İleride: data['type'] kontrolü ile hedefli aksiyonlar (örn. belirli chat/bot)
                logger.debug("Config update received: %s", data)
        except asyncio.CancelledError:
            logger.info("Config listener cancelled.")
        except Exception as e:
            logger.warning("Config listener error: %s", e)
        finally:
            # Temizlik
            try:
                if self._redis:
                    await self._redis.close()
            except Exception:
                pass
            self._redis = None

    # ---- Seçimler ----
    def pick_chat(self, db: Session) -> Optional[Chat]:
        chats = db.query(Chat).filter(Chat.is_enabled.is_(True)).all()
        if not chats:
            return None
        return random.choice(chats)

    def pick_bot(self, db: Session, hourly_limit: Dict[str, Any]) -> Optional[Bot]:
        bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).all()
        if not bots:
            return None

        # Saatlik limit kontrolü
        one_hour_ago = now_utc() - timedelta(hours=1)
        eligible: List[Bot] = []
        for b in bots:
            if not self._bot_is_active_now(b):
                continue
            sent_last_hour = (
                db.query(Message)
                .filter(Message.bot_id == b.id, Message.created_at >= one_hour_ago)
                .count()
            )
            if sent_last_hour < hourly_limit.get("max", 12):
                eligible.append(b)

        if not eligible:
            return None
        return random.choice(eligible)

    def _bot_is_active_now(self, bot: Bot) -> bool:
        try:
            ranges = bot.active_hours  # type: ignore[attr-defined]
        except Exception:
            ranges = None
        return is_within_active_hours(ranges if isinstance(ranges, list) else None)

    def _active_cooldown_topics(self, stances: List[Dict[str, Any]]) -> List[str]:
        active: List[str] = []
        now = now_utc()
        for s in stances or []:
            cu = s.get("cooldown_until")
            if not cu:
                continue
            try:
                dt = datetime.fromisoformat(cu)
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            if dt > now:
                t = (s.get("topic") or "").strip()
                if t:
                    active.append(t)
        return active

    def pick_reply_target(
        self,
        db: Session,
        chat: Chat,
        reply_p: float,
        *,
        active_bot_id: Optional[int] = None,
        active_bot_username: Optional[str] = None,
    ) -> tuple[Optional[Message], Optional[str]]:
        """Reply yapılacak bir mesaj ve mention handle döndürür (yoksa None, None)."""
        if random.random() > reply_p:
            return None, None

        last_msgs = (
            db.query(Message)
            .filter(Message.chat_db_id == chat.id)
            .order_by(Message.created_at.desc())
            .limit(20)
            .all()
        )
        if not last_msgs:
            return None, None

        normalized_username = (active_bot_username or "").lstrip("@").lower()
        mention_tokens = [
            f"@{normalized_username}" if normalized_username else "",
            normalized_username,
        ]

        scored_candidates: list[tuple[float, int, Message, Optional[str]]] = []
        for idx, msg in enumerate(last_msgs):
            if active_bot_id is not None and msg.bot_id == active_bot_id:
                continue

            text = getattr(msg, "text", "") or ""
            lower_text = text.lower()

            score = 0.0
            if msg.bot_id is None:
                score += 3.0
            else:
                score -= 1.0

            if "?" in text:
                score += 1.5

            if normalized_username:
                for token in mention_tokens:
                    if token and token in lower_text:
                        score += 2.5
                        break

            mention_handle = None
            msg_bot = getattr(msg, "bot", None)
            username = getattr(msg_bot, "username", None) if msg_bot else None
            if isinstance(username, str) and username.strip():
                mention_handle = username.lstrip("@")

            scored_candidates.append((score, idx, msg, mention_handle))

        if not scored_candidates:
            return None, None

        best_score, _best_index, target, candidate_mention_handle = max(
            scored_candidates,
            key=lambda item: (item[0], -item[1]),
        )

        # Eğer puanlama çok düşükse, cevap vermekten kaçın
        if best_score <= -1.0:
            return None, None

        settings = self.settings(db)
        mention_handle = None
        if (
            candidate_mention_handle
            and random.random() < settings.get("mention_probability", 0.0)
        ):
            mention_handle = candidate_mention_handle

        return target, mention_handle

    # ---- Gecikme ve hız ----
    def next_delay_seconds(self, db: Session, *, bot: Optional[Bot] = None) -> float:
        s = self.settings(db)
        # prime saatlerde gecikmeyi kısalt
        base = 30.0  # ortalama gecikme tabanı
        if s.get("prime_hours_boost") and is_prime_hours(s.get("prime_hours", [])):
            base = 18.0
        # scale factor uygula
        base = base * float(s.get("scale_factor", 1.0))
        delay_profile = self._resolve_delay_profile(bot)

        if "base_delay_seconds" in delay_profile:
            base = _safe_float(delay_profile.get("base_delay_seconds"), base)

        multiplier = _safe_float(
            delay_profile.get("delay_multiplier", delay_profile.get("multiplier", 1.0)), 1.0
        )
        mean = max(base * multiplier, 0.0)

        jitter_min = _safe_float(
            delay_profile.get("jitter_min", delay_profile.get("delay_jitter_min", 0.7)), 0.7
        )
        jitter_max = _safe_float(
            delay_profile.get("jitter_max", delay_profile.get("delay_jitter_max", 1.3)), 1.3
        )
        if jitter_max < jitter_min:
            jitter_min, jitter_max = jitter_max, jitter_min

        delay = exp_delay(mean if mean > 0 else 1.0) * random.uniform(jitter_min, jitter_max)

        min_delay = _safe_float(
            delay_profile.get(
                "min_seconds",
                delay_profile.get("delay_min_seconds", delay_profile.get("seconds_min", 2.0)),
            ),
            2.0,
        )
        max_delay = _safe_float(
            delay_profile.get(
                "max_seconds",
                delay_profile.get("delay_max_seconds", delay_profile.get("seconds_max", 180.0)),
            ),
            180.0,
        )
        return clamp(delay, min_delay, max_delay)

    def typing_seconds(self, db: Session, est_chars: int, *, bot: Optional[Bot] = None) -> float:
        wpm = self.settings(db).get("typing_speed_wpm", {"min": 2.5, "max": 4.5})
        min_wpm = _safe_float(wpm.get("min"), 2.5)
        max_wpm = _safe_float(wpm.get("max"), 4.5)

        typing_profile = self._resolve_typing_profile(bot)
        if isinstance(typing_profile.get("wpm"), dict):
            wpm_dict = typing_profile.get("wpm", {})
            min_wpm = _safe_float(wpm_dict.get("min"), min_wpm)
            max_wpm = _safe_float(wpm_dict.get("max"), max_wpm)

        min_wpm = _safe_float(
            typing_profile.get("wpm_min", typing_profile.get("typing_wpm_min", min_wpm)),
            min_wpm,
        )
        max_wpm = _safe_float(
            typing_profile.get("wpm_max", typing_profile.get("typing_wpm_max", max_wpm)),
            max_wpm,
        )

        multiplier = _safe_float(
            typing_profile.get("typing_multiplier", typing_profile.get("multiplier", 1.0)), 1.0
        )
        min_wpm *= multiplier
        max_wpm *= multiplier

        if max_wpm < min_wpm:
            min_wpm, max_wpm = max_wpm, min_wpm

        mean_wpm = max((min_wpm + max_wpm) / 2.0, 0.1)
        cps = (mean_wpm * 5.0) / 60.0  # 1 kelime ~5 karakter varsayımı
        seconds = est_chars / max(cps, 1.0)

        min_seconds = _safe_float(
            typing_profile.get(
                "min_seconds",
                typing_profile.get("typing_min_seconds", typing_profile.get("seconds_min", 2.0)),
            ),
            2.0,
        )
        max_seconds = _safe_float(
            typing_profile.get(
                "max_seconds",
                typing_profile.get("typing_max_seconds", typing_profile.get("seconds_max", 8.0)),
            ),
            8.0,
        )
        return clamp(seconds, min_seconds, max_seconds)

    def _resolve_delay_profile(self, bot: Optional[Bot]) -> Dict[str, Any]:
        profile = getattr(bot, "speed_profile", None) if bot else None
        if isinstance(profile, dict):
            delay = profile.get("delay")
            if isinstance(delay, dict):
                return delay
            return profile
        return {}

    def _resolve_typing_profile(self, bot: Optional[Bot]) -> Dict[str, Any]:
        profile = getattr(bot, "speed_profile", None) if bot else None
        if isinstance(profile, dict):
            typing = profile.get("typing")
            if isinstance(typing, dict):
                return typing
            return profile
        return {}

    # ---- Rate limit ----
    def global_rate_ok(self, db: Session) -> bool:
        s = self.settings(db)
        per_min_limit = int(s.get("max_msgs_per_min", 6))
        one_min_ago = now_utc() - timedelta(seconds=60)
        last_min_msgs = db.query(Message).filter(Message.created_at >= one_min_ago).count()
        return last_min_msgs < per_min_limit

    # ---- Persona/Stance/Holdings çekme ----
    def fetch_psh(
        self,
        db: Session,
        bot: Bot,
        topic_hint: Optional[str],
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """Bot için persona_profile + stances + holdings verilerini oku ve sadeleştir."""
        persona_profile = bot.persona_profile or {}
        persona_hint = (bot.persona_hint or "").strip()

        # Stance'ler: son güncellenene öncelik
        stance_rows: List[BotStance] = (
            db.query(BotStance)
            .filter(BotStance.bot_id == bot.id)
            .order_by(BotStance.updated_at.desc())
            .all()
        )
        stances: List[Dict[str, Any]] = []
        for s in stance_rows:
            stances.append({
                "topic": s.topic,
                "stance_text": (s.stance_text or "").strip(),
                "confidence": s.confidence,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "cooldown_until": s.cooldown_until.isoformat() if s.cooldown_until else None,
            })

        # İpucu verilen topic'i öne taşı (okunurluk için)
        if topic_hint:
            stances.sort(key=lambda x: (0 if (x.get("topic") or "").lower() == topic_hint.lower() else 1))

        # Holdings: son güncellenene öncelik
        holding_rows: List[BotHolding] = (
            db.query(BotHolding)
            .filter(BotHolding.bot_id == bot.id)
            .order_by(BotHolding.updated_at.desc())
            .all()
        )
        holdings: List[Dict[str, Any]] = []
        for h in holding_rows:
            holdings.append({
                "symbol": h.symbol,
                "avg_price": h.avg_price,
                "size": h.size,
                "note": h.note,
                "updated_at": h.updated_at.isoformat() if h.updated_at else None,
            })

        return persona_profile, stances, holdings, persona_hint

    # ---- Tutarlılık koruması ----
    def apply_consistency_guard(
        self,
        *,
        draft_text: str,
        persona_profile: Dict[str, Any],
        stances: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        LLM çıktısını persona/stance ile karşılaştırıp bariz çelişki varsa nazikçe düzeltir.
        Çelişki yoksa None döndürerek mevcut metnin kullanılmasını önerir.
        """
        if not draft_text or not stances:
            return None

        persona_summary = summarize_persona(persona_profile)
        stance_summary = summarize_stances(stances)

        guard_prompt = f"""\
[PERSONA]
{persona_summary}

[STANCE]
{stance_summary}

[DRAFT]
{draft_text}

[GÖREV]
- DRAFT metnini STANCE ve (varsa) cooldown kurallarıyla karşılaştır.
- Eğer bariz çelişki YOKSA DRAFT'ı olduğu gibi geri ver (değiştirme).
- Eğer çelişki VARSA veya cooldown sürerken zıt pozisyon içeriyorsa:
  1) Tonu yumuşat ve kısa bir gerekçe ekleyerek metni düzelt.
  2) Aynı dilde (Türkçe) 2-3 cümle yaz.
  3) Aşırı iddiadan kaçın; istersen "yatırım tavsiyesi değildir." notu ekleyebilirsin.
- SADECE nihai metni döndür, başka açıklama yazma.
"""
        # Düşük sıcaklık, kısa yanıt
        revised = self.llm.generate(user_prompt=guard_prompt, temperature=0.3, max_tokens=220)
        if not revised:
            return None

        # Eğer çıktı DRAFT ile neredeyse aynıysa değişiklik yapmamış say
        if revised.strip() == draft_text.strip():
            return None

        return revised

    # ---- Dedup (tekrar) kontrolü ----
    def is_duplicate_recent(self, db: Session, *, bot_id: int, text: str, hours: int) -> bool:
        if not text:
            return False
        cutoff = now_utc() - timedelta(hours=int(max(1, hours)))
        last_msgs = (
            db.query(Message)
            .filter(Message.bot_id == bot_id, Message.created_at >= cutoff)
            .order_by(Message.created_at.desc())
            .limit(100)
            .all()
        )
        target = normalize_text(text)
        for m in last_msgs:
            if normalize_text(m.text or "") == target:
                return True
        return False

    def paraphrase_safe(self, text: str) -> Optional[str]:
        """Basit yeniden yazım; anlamı korur, tekrar algılamayı aşmaya çalışır."""
        prompt = f"""Metni aynı anlamla, 1-2 kısa cümlede farklı ifade et; iddialı/kesin ton kullanma:

METİN:
{text}
"""
        return self.llm.generate(user_prompt=prompt, temperature=0.4, max_tokens=120)

    # ---- Akış ----
    async def tick_once(self) -> None:
        db: Session = SessionLocal()
        try:
            s = self.settings(db)
            if not bool(s.get("simulation_active", False)):
                await asyncio.sleep(1.0)
                return

            # Global rate limit
            if not self.global_rate_ok(db):
                await asyncio.sleep(2.5)
                return

            chat = self.pick_chat(db)
            if not chat:
                logger.info("Aktif chat yok; bekleniyor.")
                await asyncio.sleep(2.0)
                return

            bot = self.pick_bot(db, hourly_limit=s.get("bot_hourly_msg_limit", {"max": 12}))
            if not bot:
                logger.info("Saatlik sınır nedeniyle uygun bot bulunamadı; bekleniyor.")
                await asyncio.sleep(3.0)
                return

            # Persona/Stance/Holdings verilerini çek (erken çekiyoruz çünkü topic seçiminde cooldown gerekiyor)
            topic_hint_pool = (chat.topics or ["BIST", "FX", "Kripto", "Makro"]).copy()

            (
                persona_profile,
                stances,
                holdings,
                persona_hint,
            ) = self.fetch_psh(db, bot, topic_hint=None)

            # Cooldown filtre: cooldown'da olan konuları pool'dan çıkar
            if bool(s.get("cooldown_filter_enabled", True)):
                active_cd = set(self._active_cooldown_topics(stances))
                filtered = [t for t in topic_hint_pool if t not in active_cd]
                if filtered:
                    topic_hint_pool = filtered

            # Reaksiyon-only olayı
            if random.random() < float(s.get("short_reaction_probability", 0.12)):
                last = (
                    db.query(Message)
                    .filter(Message.chat_db_id == chat.id)
                    .order_by(Message.created_at.desc())
                    .limit(10)
                    .all()
                )
                candidates = [m for m in last if m.bot_id != bot.id]
                if candidates:
                    target = random.choice(candidates)
                    ok = await self.tg.try_set_reaction(bot.token, chat.chat_id, target.telegram_message_id)
                    if not ok:
                        # fallback: çok kısa bir emoji mesajı
                        emoji = LLMClient.pick_reaction_for_text(getattr(target, "text", ""))
                        msg_id = await self.tg.send_message(
                            token=bot.token,
                            chat_id=chat.chat_id,
                            text=emoji,
                            reply_to_message_id=target.telegram_message_id,
                            disable_preview=True,
                        )
                        # logla
                        db.add(Message(
                            bot_id=bot.id,
                            chat_db_id=chat.id,
                            telegram_message_id=msg_id,
                            text=emoji,
                            reply_to_message_id=target.telegram_message_id,
                        ))
                        db.commit()
                    await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                    return

            # Reply hedefi ve mention
            reply_msg, mention_handle = self.pick_reply_target(
                db,
                chat,
                float(s.get("reply_probability", 0.65)),
                active_bot_id=bot.id,
                active_bot_username=getattr(bot, "username", None),
            )
            mode = "reply" if reply_msg else "new"
            mention_ctx = f"@{mention_handle}" if mention_handle else ""

            # Geçmiş özet (son 6 mesaj)
            last_msgs = (
                db.query(Message)
                .filter(Message.chat_db_id == chat.id)
                .order_by(Message.created_at.desc())
                .limit(6)
                .all()
            )
            # Son mesajlardan çok satırlı diyalog transkripti oluştur
            history_excerpt = build_history_transcript(list(reversed(last_msgs)))
            reply_excerpt = shorten(reply_msg.text if reply_msg else "", 240)

            # Topic seç (cooldown filtreli havuzdan)
            topic = choose_topic_from_messages(last_msgs, topic_hint_pool)

            # ---- HABER TETIKLEYICI ----
            market_trigger = ""
            try:
                if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
                    # Her mesajda değil; bir miktar rastgelelik:
                    if random.random() < float(s.get("news_trigger_probability", 0.75)):
                        brief = self.news.get_brief(topic)
                        if brief:
                            market_trigger = brief
            except Exception as e:
                logger.debug("news trigger error: %s", e)

            # (prompt için) Stance/holding özetleri; topic'i ipucu olarak veriyoruz
            selected_length_category = choose_message_length_category(
                s.get("message_length_profile")
            )
            length_hint = compose_length_hint(
                persona_profile=persona_profile,
                selected_category=selected_length_category,
            )
            user_prompt = generate_user_prompt(
                topic_name=topic,
                history_excerpt=shorten(history_excerpt, 400),
                reply_context=reply_excerpt,
                market_trigger=market_trigger,  # <-- Burada kullanılıyor
                mode=mode,
                mention_context=mention_ctx,
                persona_profile=persona_profile,
                stances=stances,
                holdings=holdings,
                length_hint=length_hint,
                persona_hint=persona_hint,
            )

            # LLM üretimi (taslak)
            text = self.llm.generate(user_prompt=user_prompt, temperature=0.8, max_tokens=220)
            if not text:
                logger.warning("LLM boş/filtreli çıktı; atlanıyor.")
                await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                return

            # Tutarlılık koruması
            if bool(s.get("consistency_guard_enabled", True)):
                revised = self.apply_consistency_guard(
                    draft_text=text,
                    persona_profile=persona_profile,
                    stances=stances,
                )
                if revised:
                    text = revised

            # Mention'ı metne kibarca ekle (başta değilse)
            if mention_ctx and mention_ctx not in text:
                if random.random() < 0.6:
                    text = f"{mention_ctx} {text}"
                else:
                    text = f"{text} {mention_ctx}"

            # Dedup kontrolü: son X saatte aynısı varsa yeniden yazdırmayı dene
            if bool(s.get("dedup_enabled", True)):
                window_h = int(s.get("dedup_window_hours", 12))
                attempts = int(s.get("dedup_max_attempts", 2))
                tries = 0
                while self.is_duplicate_recent(db, bot_id=bot.id, text=text, hours=window_h) and tries < attempts:
                    alt = self.paraphrase_safe(text)
                    if not alt or alt.strip() == text.strip():
                        break
                    text = alt.strip()
                    tries += 1
                # Hâlâ birebir aynıysa mesajı es geç
                if self.is_duplicate_recent(db, bot_id=bot.id, text=text, hours=window_h):
                    logger.info("Dedup: aynı metin tespit edildi, gönderim atlandı.")
                    await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                    return

            # Typing simülasyonu
            if bool(s.get("typing_enabled", True)):
                await self.tg.send_typing(
                    bot.token,
                    chat.chat_id,
                    self.typing_seconds(db, len(text), bot=bot),
                )

            # Mesajı gönder
            msg_id = await self.tg.send_message(
                token=bot.token,
                chat_id=chat.chat_id,
                text=text,
                reply_to_message_id=reply_msg.telegram_message_id if reply_msg else None,
                disable_preview=True,
            )

            # DB log
            db.add(Message(
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=msg_id,
                text=text,
                reply_to_message_id=reply_msg.telegram_message_id if reply_msg else None,
            ))
            db.commit()

            # Sonraki gecikme
            await asyncio.sleep(self.next_delay_seconds(db, bot=bot))

        except Exception as e:
            logger.exception("tick_once error: %s", e)
            await asyncio.sleep(3.0)
        finally:
            db.close()

    async def run_forever(self):
        logger.info("BehaviorEngine started. CTRL+C ile durdurabilirsiniz.")

        # Redis listener'ı başlat
        if self._redis_url and self._redis_task is None:
            self._redis_task = asyncio.create_task(self._config_listener(), name="config_listener")

        while True:
            await self.tick_once()

    # ---- Temiz kapanış ----
    async def shutdown(self) -> None:
        """Worker sinyali geldiğinde kaynakları nazikçe kapat."""
        # Redis listener iptali
        if self._redis_task:
            self._redis_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._redis_task
            self._redis_task = None

        # Telegram HTTP istemcisi
        try:
            await self.tg.close()
        except Exception:
            pass
        logger.info("BehaviorEngine shutdown completed.")


# ---------------------------
# Çalıştırma
# ---------------------------
async def run_engine_forever():
    global _ENGINE
    engine = BehaviorEngine()
    _ENGINE = engine
    try:
        await engine.run_forever()
    finally:
        # Çalışma döngüsü biterse (iptal/çökme), referansı temizle
        _ENGINE = None


# ---------------------------
# Modül seviyesi kapanış kancası
# ---------------------------
async def shutdown() -> None:
    """worker.py bu fonksiyonu çağırır: aktif engine varsa kapatır."""
    if _ENGINE is None:
        logger.info("No active BehaviorEngine to shutdown.")
        return
    try:
        await _ENGINE.shutdown()
    finally:
        logger.info("Module-level shutdown done.")
