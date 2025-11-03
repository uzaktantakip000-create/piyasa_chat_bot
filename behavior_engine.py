from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import random
import re
from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Sequence

from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    SessionLocal, Bot, Chat, Message, Setting,
    BotStance, BotHolding, BotMemory,
)
from settings_utils import (
    DEFAULT_MESSAGE_LENGTH_PROFILE,
    normalize_message_length_profile,
    unwrap_setting_value,
)
from llm_client import LLMClient
from system_prompt import (
    generate_user_prompt,
    generate_system_prompt,  # <-- YENİ: Her bot için unique system prompt
    summarize_persona,
    summarize_stances,
)
from telegram_client import TelegramClient
from message_queue import MessageQueue, QueuedMessage, MessagePriority
from news_client import NewsClient, DEFAULT_FEEDS  # <-- HABER TETIKLEYICI
from voice_profiles import VoiceProfileGenerator  # <-- PHASE 2 Week 3 Day 4-5: Voice Profiles

# Backend behavior modules (Session 10-11: Modularization)
from backend.behavior import (
    # Topic management
    TOPIC_KEYWORDS,
    choose_topic_from_messages,
    score_topics_from_messages,
    # Persona management
    ReactionPlan,
    compose_persona_refresh_note,
    derive_tempo_multiplier,
    now_utc,
    should_refresh_persona,
    synthesize_reaction_plan,
    update_persona_refresh_state,
    # Bot selection utilities
    is_prime_hours,
    is_within_active_hours,
    parse_ranges,
    # Reply handler utilities
    detect_sentiment,
    detect_topics,
    extract_symbols,
    # Deduplication
    normalize_text,
    # Message utilities
    choose_message_length_category,
    compose_length_hint,
    generate_time_context,
    # General utilities
    clamp,
    safe_float,
    shorten,
    # Message processing
    anonymize_example_text,
    build_contextual_examples,
    build_history_transcript,
    resolve_message_speaker,
)

# Message generation functions (Session 17: Modularization Phase 1)
from backend.behavior_engine.message_generator import (
    apply_consistency_guard,
    apply_reaction_overrides,
    apply_micro_behaviors,
    paraphrase_safe,
    add_conversation_openings,
    add_hesitation_markers,
    add_colloquial_shortcuts,
    apply_natural_imperfections,
    add_filler_words,
)

# Metadata analysis functions (Session 19: Modularization Phase 2)
from backend.behavior_engine.metadata_analyzer import (
    fetch_bot_memories,
    update_memory_usage,
    format_memories_for_prompt,
    extract_message_metadata,
    find_relevant_past_messages,
    format_past_references_for_prompt,
)

# Prometheus metrics (opsiyonel)
try:
    from backend.metrics import (
        message_generation_total,
        message_generation_duration_seconds,
        active_bots_gauge,
        MetricTimer,
    )
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    # Dummy objects - metrik yoksa hata vermesin
    class DummyCounter:
        def labels(self, **kwargs): return self
        def inc(self): pass
    class DummyGauge:
        def set(self, val): pass
    class DummyHistogram:
        def observe(self, val): pass
    class DummyTimer:
        def __enter__(self): return self
        def __exit__(self, *args): pass

    message_generation_total = DummyCounter()
    active_bots_gauge = DummyGauge()
    message_generation_duration_seconds = DummyHistogram()
    MetricTimer = lambda hist: DummyTimer()

logger = logging.getLogger("behavior")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

UTC = timezone.utc

# Çalışan engine'in referansı (worker.py 'shutdown' çağırabilsin diye)
_ENGINE: Optional["BehaviorEngine"] = None


# ---------------------------
# Yardımcı fonksiyonlar
# ---------------------------
# NOTE: Most helper functions moved to backend/behavior/ modules (Session 10-11)
# TOPIC_KEYWORDS, ReactionPlan, and 20+ other functions now imported from backend.behavior


def exp_delay(mean_seconds: float) -> float:
    """Exponential (Poisson process) gecikme üreten yardımcı."""
    if mean_seconds <= 0:
        return 1.0
    return random.expovariate(1.0 / mean_seconds)


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
    # HABER tetikleyici (PHASE 2 Week 4 Day 1-3: Rich News Integration)
    d.setdefault("news_trigger_enabled", True)     # market_trigger aktif mi?
    d.setdefault("news_trigger_probability", 0.5)  # %50 olasılıkla tetik kullan (was 0.75)

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

        # Multi-worker coordination (PHASE 1B.1: Multi-Worker Architecture)
        self.worker_id = int(os.getenv("WORKER_ID", "0"))
        self.total_workers = int(os.getenv("TOTAL_WORKERS", "1"))
        logger.info(f"Worker {self.worker_id}/{self.total_workers} initialized")

        # Cache manager (PHASE 1A.2: Multi-layer caching)
        # Will be initialized after Redis client is set up below
        self.cache = None  # type: ignore

        # Haber tetikleyici (opsiyonel, bağımlılık yoksa bozulmasın)
        self.news: Optional[NewsClient] = None
        try:
            self.news = NewsClient()
        except Exception as e:
            logger.warning("NewsClient init failed: %s", e)
            self.news = None
        self._active_news_feeds: List[str] = list(self.news.feeds) if self.news else []

        # Redis (opsiyonel) - async subscriber ve priority queue
        self._redis_url: Optional[str] = os.getenv("REDIS_URL") or None
        self._redis = None  # type: ignore
        self._redis_task: Optional[asyncio.Task] = None
        self._redis_sync_client = None  # Sync client for priority queue polling

        # Priority queue Redis client (sync)
        if self._redis_url:
            try:
                import redis
                self._redis_sync_client = redis.Redis.from_url(self._redis_url, decode_responses=True)
                self._redis_sync_client.ping()
                logger.info("Priority queue Redis client initialized")
            except Exception as e:
                logger.warning("Priority queue Redis init failed: %s. User message responses disabled.", e)
                self._redis_sync_client = None

        # Message queue for rate-limited messages
        self.msg_queue = MessageQueue(self._redis_sync_client)
        self._queue_processor_task: Optional[asyncio.Task] = None
        logger.info("Message queue initialized")

        # Initialize cache manager (SESSION 13: Multi-layer caching)
        try:
            from backend.caching import CacheManager
            self.cache = CacheManager.get_instance()
            logger.info("CacheManager initialized (L1+L2 multi-layer)")
        except Exception as e:
            logger.warning("CacheManager init failed: %s. Running without cache.", e)
            self.cache = None

        # Persona yenileme takibi (bot bazlı)
        self._persona_refresh: Dict[int, Dict[str, Any]] = {}

        # PHASE 2 Week 3 Day 1-3: Semantic Deduplication (P0.1: with embedding cache)
        self.semantic_dedup = None
        try:
            from semantic_dedup import SemanticDeduplicator
            # Pass Redis client for embedding cache
            self.semantic_dedup = SemanticDeduplicator(
                similarity_threshold=0.85,
                redis_client=self._redis_sync_client
            )
            logger.info("Semantic deduplicator initialized with embedding cache")
        except Exception as e:
            logger.warning(f"Semantic deduplicator init failed: {e}. Will use exact-match dedup only.")

        # PHASE 2 Week 3 Day 4-5: Voice Profiles & Writing Style (P0.2: LRU cache + TTL)
        self.voice_generator = VoiceProfileGenerator()
        # P0.2: Use dict with TTL tracking instead of unlimited cache
        self.bot_voices: Dict[int, Dict[str, Any]] = {}  # {bot_id: {"profile": VoiceProfile, "cached_at": datetime}}
        self.voice_cache_ttl_seconds = 3600  # 1 hour TTL
        self.voice_cache_max_size = 1000  # Max 1000 entries
        logger.info("Voice profile generator initialized with LRU cache (max=1000, TTL=1h)")

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

    # ---- Cache Invalidation (PHASE 1A.2) ----
    def invalidate_bot_cache(self, bot_id: int):
        """Invalidate bot profile cache (called when bot is updated) - SESSION 13"""
        if self.cache:
            from backend.caching import invalidate_bot_cache
            invalidate_bot_cache(bot_id)
            logger.info("Bot cache invalidated: bot_id=%d", bot_id)

    def invalidate_chat_cache(self, chat_id: int):
        """Invalidate chat message cache (called when new message arrives) - SESSION 13"""
        if self.cache:
            from backend.caching import invalidate_chat_message_cache
            invalidate_chat_message_cache(chat_id)
            logger.debug("Chat cache invalidated: chat_id=%d", chat_id)

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

    def get_bot_voice(self, bot):
        """
        Bot için voice profile al (cache'den veya yeni oluştur)

        PHASE 2 Week 3 Day 4-5: Voice Profiles
        P0.2: LRU cache with TTL and size limit
        """
        now = now_utc()

        # Check if cached and not expired
        if bot.id in self.bot_voices:
            cached_entry = self.bot_voices[bot.id]
            cached_at = cached_entry.get("cached_at")
            age_seconds = (now - cached_at).total_seconds()

            if age_seconds < self.voice_cache_ttl_seconds:
                # Cache hit - valid
                return cached_entry["profile"]
            else:
                # Expired - remove
                logger.debug(f"Voice profile expired for bot {bot.name} (age={age_seconds:.0f}s)")
                del self.bot_voices[bot.id]

        # P0.2: Check cache size limit (LRU eviction)
        if len(self.bot_voices) >= self.voice_cache_max_size:
            # Evict oldest entry
            oldest_bot_id = min(self.bot_voices.keys(), key=lambda k: self.bot_voices[k]["cached_at"])
            logger.debug(f"Voice cache full, evicting bot_id={oldest_bot_id}")
            del self.bot_voices[oldest_bot_id]

        # Cache miss - generate new profile
        profile = self.voice_generator.generate(bot)
        self.bot_voices[bot.id] = {
            "profile": profile,
            "cached_at": now
        }
        logger.debug(f"Voice profile cached for bot {bot.name} (id={bot.id}, cache_size={len(self.bot_voices)})")

        return profile

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

    def pick_bot(
        self,
        db: Session,
        hourly_limit: Dict[str, Any],
        chat: Optional[Chat] = None,
    ) -> Optional[Bot]:
        bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).all()
        if not bots:
            return None

        # Multi-worker coordination: Consistent hashing for bot distribution
        # Each worker only handles bots where bot_id % total_workers == worker_id
        if self.total_workers > 1:
            my_bots = [b for b in bots if b.id % self.total_workers == self.worker_id]
            if not my_bots:
                return None  # This worker has no bots assigned
            bots = my_bots

        # Saatlik limit kontrolü
        # SESSION 27: Optimized to avoid N+1 query problem
        # Instead of querying each bot separately, fetch all counts in one query
        one_hour_ago = now_utc() - timedelta(hours=1)
        max_hourly = hourly_limit.get("max", 12)

        # Single query to get message counts for all bots in the last hour
        bot_ids = [b.id for b in bots]
        hourly_counts = (
            db.query(Message.bot_id, func.count(Message.id))
            .filter(
                Message.bot_id.in_(bot_ids),
                Message.created_at >= one_hour_ago
            )
            .group_by(Message.bot_id)
            .all()
        )

        # Build a dict for O(1) lookup
        bot_message_counts = {bot_id: count for bot_id, count in hourly_counts}

        # Filter eligible bots
        eligible: List[Bot] = []
        for b in bots:
            if not self._bot_is_active_now(b):
                continue
            sent_last_hour = bot_message_counts.get(b.id, 0)
            if sent_last_hour < max_hourly:
                eligible.append(b)

        if not eligible:
            return None

        last_bot_id: Optional[int] = None
        if chat is not None:
            last_message = (
                db.query(Message)
                .filter(Message.chat_db_id == chat.id)
                .order_by(Message.created_at.desc())
                .first()
            )
            if last_message and last_message.bot_id is not None:
                last_bot_id = last_message.bot_id

        if last_bot_id is not None:
            alternative = [b for b in eligible if b.id != last_bot_id]
            if alternative:
                eligible = alternative

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

    # ---- Smart Reply Target Selection ----

    def pick_reply_target(
        self,
        db: Session,
        chat: Chat,
        reply_p: float,
        *,
        active_bot_id: Optional[int] = None,
        active_bot_username: Optional[str] = None,
        active_bot: Optional[Bot] = None,
    ) -> tuple[Optional[Message], Optional[str]]:
        """
        Smart Reply Target Selection V2 (Week 2 Day 1-3)

        Bot-to-bot interaction'ı TEŞVİK EDER:
        - Bot mesajlarına artık pozitif puan (+2.5)
        - Akıllı scoring: mention, soru, uzmanlık alanı, sentiment, popülerlik
        - Top 3'ten weighted random seçim (çeşitlilik için)
        """
        if random.random() > reply_p:
            return None, None

        # Son 30 mesajı al (20'den artırıldı) - PHASE 1A.2: Cache-aware
        last_msgs = self.fetch_recent_messages(db, chat.id, limit=30)
        if not last_msgs:
            return None, None

        normalized_username = (active_bot_username or "").lstrip("@").lower()
        mention_tokens = [
            f"@{normalized_username}" if normalized_username else "",
            normalized_username,
        ]

        # Bot'un persona bilgilerini al
        bot_watchlist = []
        bot_empathy = 0.5
        if active_bot and hasattr(active_bot, "persona_profile"):
            persona = active_bot.persona_profile or {}
            bot_watchlist = persona.get("watchlist", [])

        if active_bot and hasattr(active_bot, "emotion_profile"):
            emotion = active_bot.emotion_profile or {}
            bot_empathy = emotion.get("empathy", 0.5)
            if isinstance(bot_empathy, str):
                # Eğer string ise, float'a çevirmeyi dene
                try:
                    bot_empathy = float(bot_empathy)
                except:
                    bot_empathy = 0.5

        scored_candidates: list[tuple[float, int, Message, Optional[str]]] = []
        now = now_utc()

        for idx, msg in enumerate(last_msgs):
            # Kendi mesajına cevap verme
            if active_bot_id is not None and msg.bot_id == active_bot_id:
                continue

            text = getattr(msg, "text", "") or ""
            lower_text = text.lower()

            score = 0.0

            # === 1. KİM YAZDI? ===
            if msg.bot_id is None:
                # İnsan mesajı - yüksek öncelik
                score += 8.0
            else:
                # Bot mesajı - ARTIK POZİTİF! (önceden -1.0 idi)
                score += 2.5  # Bot-to-bot interaction TEŞVİK EDİLİYOR!

            # === 2. TAZELIK ===
            # Handle timezone-naive or string created_at
            created_at = msg.created_at
            if isinstance(created_at, str):
                from datetime import datetime as dt_class
                try:
                    created_at = dt_class.fromisoformat(created_at)
                except Exception:
                    created_at = now  # Fallback to now if parsing fails
            if created_at.tzinfo is None:
                from datetime import timezone
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_minutes = (now - created_at).total_seconds() / 60
            if age_minutes < 3:
                score += 3.0  # Çok taze
            elif age_minutes < 10:
                score += 2.0
            elif age_minutes < 30:
                score += 1.0
            else:
                score -= 1.0  # Eski mesaj

            # === 3. SORU VAR MI? ===
            if "?" in text:
                score += 4.0  # Soru kesinlikle cevap bekliyor

            # Merak ifadeleri
            curiosity_phrases = [
                "ne düşünüyorsun", "sizce", "fikrin", "ne dersin",
                "katılıyor musun", "öyle mi", "emin misin", "nasıl yapmalı",
                "ne yapmalı", "önerir misin"
            ]
            if any(phrase in lower_text for phrase in curiosity_phrases):
                score += 3.0

            # === 4. MENTION VAR MI? ===
            if normalized_username:
                for token in mention_tokens:
                    if token and token in lower_text:
                        score += 15.0  # Kesinlikle cevap ver!
                        break

            # === 5. UZMANLIK ALANI (watchlist overlap) ===
            if bot_watchlist:
                msg_symbols = extract_symbols(text)
                overlap = set(msg_symbols) & set(bot_watchlist)
                score += len(overlap) * 2.5  # Her eşleşen sembol +2.5

            # === 6. KONU UYUMU ===
            msg_topics = detect_topics(text)
            if msg_topics:
                # Eğer bot'un expertise'i varsa kontrol et
                # (Şimdilik basit: her topic +1.5)
                score += len(msg_topics) * 1.5

            # === 7. SENTIMENT UYUMU ===
            # Empatik botlar negatif mesajlara daha çok tepki verir
            msg_sentiment = detect_sentiment(text)
            if msg_sentiment < -0.3 and bot_empathy > 0.7:
                score += 2.0  # Empatik bot, negatif mesaja tepki verir

            # === 8. POPÜLER MESAJ (çok cevap alıyorsa) ===
            # Eğer birçok bot cevap verdiyse, bu bot da katılabilir
            try:
                reply_count = db.query(Message).filter(
                    Message.reply_to_message_id == msg.telegram_message_id
                ).count()

                if reply_count >= 2:
                    score += 1.5  # Popüler tartışma
            except:
                pass  # Hata olursa geç

            # Mention handle'ı belirle
            mention_handle = None
            msg_bot = getattr(msg, "bot", None)
            username = getattr(msg_bot, "username", None) if msg_bot else None
            if isinstance(username, str) and username.strip():
                mention_handle = username.lstrip("@")

            scored_candidates.append((score, idx, msg, mention_handle))

        if not scored_candidates:
            return None, None

        # Score'a göre sırala
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Top 3'ten weighted random seç (biraz randomness, çeşitlilik için)
        top_n = min(3, len(scored_candidates))
        top_candidates = scored_candidates[:top_n]

        # Weighted random selection
        weights = [max(c[0], 0.1) for c in top_candidates]  # Negatif score'ları 0.1'e çevir
        selected = random.choices(top_candidates, weights=weights, k=1)[0]

        score, _idx, target, candidate_mention_handle = selected

        # Handle timezone-naive created_at in log
        target_created_at = target.created_at
        if target_created_at.tzinfo is None:
            from datetime import timezone
            target_created_at = target_created_at.replace(tzinfo=timezone.utc)
        logger.info(
            f"Reply target selected: '{target.text[:50]}...' (score={score:.1f}, "
            f"from_bot={target.bot_id is not None}, age={(now - target_created_at).seconds / 60:.1f}min)"
        )

        # Mention handle'ı belirle (probability ile)
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
        # scale factor uygula (daha yüksek scale = daha hızlı mesajlar = daha kısa gecikme)
        scale_factor = max(float(s.get("scale_factor", 1.0)), 0.1)  # Minimum 0.1 to avoid division by zero
        base = base / scale_factor

        # Resolve delay profile inline
        speed_profile = getattr(bot, "speed_profile", None) if bot else None
        delay_profile = {}
        if isinstance(speed_profile, dict):
            delay = speed_profile.get("delay")
            delay_profile = delay if isinstance(delay, dict) else speed_profile

        if "base_delay_seconds" in delay_profile:
            base = safe_float(delay_profile.get("base_delay_seconds"), base)

        multiplier = safe_float(
            delay_profile.get("delay_multiplier", delay_profile.get("multiplier", 1.0)), 1.0
        )
        mean = max(base * multiplier, 0.0)

        jitter_min = safe_float(
            delay_profile.get("jitter_min", delay_profile.get("delay_jitter_min", 0.7)), 0.7
        )
        jitter_max = safe_float(
            delay_profile.get("jitter_max", delay_profile.get("delay_jitter_max", 1.3)), 1.3
        )
        if jitter_max < jitter_min:
            jitter_min, jitter_max = jitter_max, jitter_min

        delay = exp_delay(mean if mean > 0 else 1.0) * random.uniform(jitter_min, jitter_max)

        min_delay = safe_float(
            delay_profile.get(
                "min_seconds",
                delay_profile.get("delay_min_seconds", delay_profile.get("seconds_min", 2.0)),
            ),
            2.0,
        )
        max_delay = safe_float(
            delay_profile.get(
                "max_seconds",
                delay_profile.get("delay_max_seconds", delay_profile.get("seconds_max", 180.0)),
            ),
            180.0,
        )
        return clamp(delay, min_delay, max_delay)

    def typing_seconds(
        self,
        db: Session,
        est_chars: int,
        *,
        bot: Optional[Bot] = None,
        tempo_multiplier: float = 1.0,
    ) -> float:
        wpm = self.settings(db).get("typing_speed_wpm", {"min": 2.5, "max": 4.5})
        min_wpm = safe_float(wpm.get("min"), 2.5)
        max_wpm = safe_float(wpm.get("max"), 4.5)

        # Resolve typing profile inline
        speed_profile = getattr(bot, "speed_profile", None) if bot else None
        typing_profile = {}
        if isinstance(speed_profile, dict):
            typing = speed_profile.get("typing")
            typing_profile = typing if isinstance(typing, dict) else speed_profile

        if isinstance(typing_profile.get("wpm"), dict):
            wpm_dict = typing_profile.get("wpm", {})
            min_wpm = safe_float(wpm_dict.get("min"), min_wpm)
            max_wpm = safe_float(wpm_dict.get("max"), max_wpm)

        min_wpm = safe_float(
            typing_profile.get("wpm_min", typing_profile.get("typing_wpm_min", min_wpm)),
            min_wpm,
        )
        max_wpm = safe_float(
            typing_profile.get("wpm_max", typing_profile.get("typing_wpm_max", max_wpm)),
            max_wpm,
        )

        multiplier = safe_float(
            typing_profile.get("typing_multiplier", typing_profile.get("multiplier", 1.0)), 1.0
        )
        min_wpm *= multiplier
        max_wpm *= multiplier

        if max_wpm < min_wpm:
            min_wpm, max_wpm = max_wpm, min_wpm

        mean_wpm = max((min_wpm + max_wpm) / 2.0, 0.1)
        cps = (mean_wpm * 5.0) / 60.0  # 1 kelime ~5 karakter varsayımı
        seconds = est_chars / max(cps, 1.0)

        min_seconds = safe_float(
            typing_profile.get(
                "min_seconds",
                typing_profile.get("typing_min_seconds", typing_profile.get("seconds_min", 2.0)),
            ),
            2.0,
        )
        max_seconds = safe_float(
            typing_profile.get(
                "max_seconds",
                typing_profile.get("typing_max_seconds", typing_profile.get("seconds_max", 8.0)),
            ),
            8.0,
        )
        seconds = clamp(seconds, min_seconds, max_seconds)
        tempo_multiplier = clamp(float(tempo_multiplier or 1.0), 0.5, 1.6)
        return seconds * tempo_multiplier

    # ---- Rate limit ----
    def global_rate_ok(self, db: Session) -> bool:
        s = self.settings(db)
        per_min_limit = int(s.get("max_msgs_per_min", 6))
        one_min_ago = now_utc() - timedelta(seconds=60)
        last_min_msgs = db.query(Message).filter(Message.created_at >= one_min_ago).count()
        return last_min_msgs < per_min_limit

    # ---- Cached Message History Fetch (PHASE 1A.2) ----
    def fetch_recent_messages(self, db: Session, chat_id: int, limit: int) -> List[Message]:
        """
        Fetch recent messages for a chat (cache-aware)

        SESSION 13: Uses helper function with multi-layer caching
        TTL: 60 seconds (messages change frequently)

        Args:
            db: Database session
            chat_id: Chat ID (database ID, not telegram_chat_id)
            limit: Number of recent messages to fetch

        Returns:
            List of Message objects (ordered by created_at desc)
        """
        # Use cached helper function
        if self.cache:
            from backend.caching import get_recent_messages_cached
            return get_recent_messages_cached(chat_id, db, limit=limit)
        else:
            # Fallback to direct DB query
            messages = (
                db.query(Message)
                .filter(Message.chat_db_id == chat_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
                .all()
            )
            return messages

    # ---- Persona/Stance/Holdings çekme ----
    def fetch_psh(
        self,
        db: Session,
        bot: Bot,
        topic_hint: Optional[str],
    ) -> tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        Bot için persona/emotion profilleri ile stance/holding verilerini oku ve sadeleştir.

        SESSION 13: Now uses helper functions with multi-layer caching
        """
        # Get persona and emotion profiles (cached)
        persona_profile = bot.persona_profile or {}
        emotion_profile = bot.emotion_profile or {}
        persona_hint = (bot.persona_hint or "").strip()

        # Stance'ler: son güncellenene öncelik (cached with helper)
        if self.cache:
            from backend.caching import get_bot_stances_cached
            stance_rows = get_bot_stances_cached(bot.id, db)
        else:
            stance_rows = (
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

        # Holdings: son güncellenene öncelik (cached with helper)
        if self.cache:
            from backend.caching import get_bot_holdings_cached
            holding_rows = get_bot_holdings_cached(bot.id, db)
        else:
            holding_rows = (
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

        # Sort stances by topic_hint (okunurluk için)
        if topic_hint:
            stances.sort(key=lambda x: (0 if (x.get("topic") or "").lower() == topic_hint.lower() else 1))

        return persona_profile, emotion_profile, stances, holdings, persona_hint

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

    # ---- Context Data Preparation (SESSION 25: Extracted from tick_once) ----
    def _prepare_context_data(
        self,
        db: Session,
        *,
        chat: Chat,
        bot: Bot,
        s: Dict[str, Any],
    ) -> tuple:
        """
        Prepare context data for message generation (history, reply target, examples).

        SESSION 25: Extracted from tick_once to reduce complexity.

        Args:
            db: Database session
            chat: Selected chat
            bot: Selected bot
            s: Settings dictionary

        Returns:
            Tuple of (recent_msgs, reply_msg, mention_handle, mode, mention_ctx,
                     history_excerpt, reply_excerpt, contextual_examples)
        """
        # Geçmiş mesajları al - PHASE 1A.2: Cache-aware
        recent_msgs = self.fetch_recent_messages(db, chat.id, limit=40)

        # Week 2 Day 4-5: Reply Probability Tuning
        # Son mesaj bot'tansa, reply_to_bots_probability kullan
        reply_prob = float(s.get("reply_probability", 0.65))
        if recent_msgs and len(recent_msgs) > 0:
            last_msg = recent_msgs[0]
            if last_msg.bot_id is not None:
                # Son mesaj bot'tan - farklı probability kullan
                reply_prob = float(s.get("reply_to_bots_probability", 0.5))
                logger.debug(f"Last message from bot, using reply_to_bots_probability={reply_prob}")

        # Reply hedefi ve mention
        reply_msg, mention_handle = self.pick_reply_target(
            db,
            chat,
            reply_prob,  # Dinamik probability
            active_bot_id=bot.id,
            active_bot_username=getattr(bot, "username", None),
            active_bot=bot,  # Smart Reply Target Selection V2 için gerekli
        )
        mode = "reply" if reply_msg else "new"
        mention_ctx = f"@{mention_handle}" if mention_handle else ""

        # Week 2 Day 6-7: Context Window Expansion (6 → 15 mesaj)
        history_source = list(recent_msgs[:15])  # 6'dan 15'e çıkarıldı
        history_excerpt = build_history_transcript(list(reversed(history_source)))
        reply_excerpt = shorten(reply_msg.text if reply_msg else "", 240)

        contextual_examples = build_contextual_examples(
            list(reversed(recent_msgs[:30])),  # 30 mesaj içinden örnek seç (daha zengin)
            bot_id=bot.id,
            max_pairs=4  # 3'ten 4'e çıkarıldı
        )

        return (
            recent_msgs,
            reply_msg,
            mention_handle,
            mode,
            mention_ctx,
            history_excerpt,
            reply_excerpt,
            contextual_examples,
        )

    # ---- Message Processing (SESSION 25: Extracted from tick_once) ----
    def _process_generated_text(
        self,
        db: Session,
        *,
        bot: Bot,
        s: Dict[str, Any],
        user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        persona_profile: Dict[str, Any],
        emotion_profile: Dict[str, Any],
        stances: List[Dict[str, Any]],
        reaction_plan: Any,
        mention_ctx: str,
    ) -> tuple:
        """
        Process generated text with LLM and apply all enhancements.

        SESSION 25: Extracted from tick_once to reduce complexity.

        Returns:
            Tuple of (processed_text, should_skip)
            should_skip is True if message should be skipped (empty or duplicate)
        """
        # ==== LLM ÜRETİMİ (YENİ PARAMETRELERLE) ====
        text = self.llm.generate(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
        )
        if not text:
            logger.warning("LLM boş/filtreli çıktı; atlanıyor.")
            return ("", True)

        # Tutarlılık koruması
        if bool(s.get("consistency_guard_enabled", True)):
            revised = apply_consistency_guard(
                self.llm,
                draft_text=text,
                persona_profile=persona_profile,
                stances=stances,
            )
            if revised:
                text = revised

        text = apply_reaction_overrides(text, reaction_plan)

        text = apply_micro_behaviors(
            text,
            emotion_profile=emotion_profile,
            plan=reaction_plan,
        )

        # İnsancıl geliştirmeler (sıralama önemli!)
        # 1. Konuşma açılışları ekle
        text = add_conversation_openings(text, probability=0.25)

        # 2. Belirsizlik belirteçleri ekle (en kritik özellik)
        text = add_hesitation_markers(text, probability=0.30)

        # 3. Günlük kısaltmalar ekle
        text = add_colloquial_shortcuts(text, probability=0.18)

        # 4. Dolgu kelimeleri ekle
        text = add_filler_words(text, probability=0.20)

        # 5. Doğal kusurlar uygula (yazım hataları + düzeltmeler)
        text = apply_natural_imperfections(text, probability=0.15)

        # Mention'ı metne kibarca ekle (başta değilse)
        if mention_ctx and mention_ctx not in text:
            if random.random() < 0.6:
                text = f"{mention_ctx} {text}"
            else:
                text = f"{text} {mention_ctx}"

        # Dedup kontrolü: son X saatte aynısı varsa yeniden yazdırmayı dene
        # Exact-match deduplication (mevcut)
        if bool(s.get("dedup_enabled", True)):
            window_h = int(s.get("dedup_window_hours", 12))
            attempts = int(s.get("dedup_max_attempts", 2))
            tries = 0
            while self.is_duplicate_recent(db, bot_id=bot.id, text=text, hours=window_h) and tries < attempts:
                alt = paraphrase_safe(self.llm, text)
                if not alt or alt.strip() == text.strip():
                    break
                text = alt.strip()
                tries += 1
            # Hâlâ birebir aynıysa mesajı es geç
            if self.is_duplicate_recent(db, bot_id=bot.id, text=text, hours=window_h):
                logger.info("Dedup: aynı metin tespit edildi, gönderim atlandı.")
                return ("", True)

        return (text, False)

    # ---- Message Finalization (SESSION 25: Extracted from tick_once) ----
    def _finalize_message_text(
        self,
        db: Session,
        *,
        bot: Bot,
        s: Dict[str, Any],
        text: str,
        recent_msgs: List[Message],
    ) -> tuple:
        """
        Finalize message text with semantic dedup and voice profile.

        SESSION 25: Extracted from tick_once to reduce complexity.

        Returns:
            Tuple of (final_text, should_skip)
            should_skip is True if message should be skipped (semantic duplicate)
        """
        # PHASE 2 Week 3 Day 1-3: Semantic Deduplication
        if bool(s.get("semantic_dedup_enabled", True)) and self.semantic_dedup and self.semantic_dedup.enabled:
            # Son 50 bot mesajını al
            recent_bot_msgs = [
                m.text for m in recent_msgs[:50]
                if m.text and m.bot_id == bot.id
            ]

            if recent_bot_msgs:
                is_dup, similarity = self.semantic_dedup.is_duplicate(text, recent_bot_msgs)

                if is_dup:
                    logger.warning(f"Semantic duplicate detected! Similarity={similarity:.3f}")

                    # 2 deneme: Paraphrase et (P1.2: with cache)
                    paraphrase_attempts = 2
                    for attempt in range(paraphrase_attempts):
                        text = self.semantic_dedup.paraphrase_message(text, self.llm, bot_id=bot.id)
                        is_dup, similarity = self.semantic_dedup.is_duplicate(text, recent_bot_msgs)

                        if not is_dup:
                            logger.info(f"Paraphrase successful! New similarity={similarity:.3f}")
                            break

                    # Hâlâ duplicate ise mesajı atla
                    if is_dup:
                        logger.error("Paraphrase failed after 2 attempts, skipping message")
                        return ("", True)

        # PHASE 2 Week 3 Day 4-5: Voice Profile Application (P0.3: deterministic)
        # Mesaja bot'un unique writing style'ını uygula
        voice = self.get_bot_voice(bot)
        original_text = text
        text = self.voice_generator.apply_voice(text, voice, bot_id=bot.id)  # P0.3: pass bot_id for determinism
        if text != original_text:
            logger.debug(f"Voice profile applied: '{original_text[:50]}...' -> '{text[:50]}...'")

        return (text, False)

    # ---- Message Sending (SESSION 25: Extracted from tick_once) ----
    async def _send_message_to_chat(
        self,
        db: Session,
        *,
        bot: Bot,
        chat: Chat,
        s: Dict[str, Any],
        text: str,
        topic: str,
        reply_msg: Optional[Message],
        tempo_multiplier: float,
        bot_id_for_metric: Optional[int],
        start_time: float,
        refresh_state: Dict[str, Any],
        should_refresh: bool,
    ) -> None:
        """
        Send message to chat with typing simulation, DB logging, and metrics.

        SESSION 25: Extracted from tick_once to reduce complexity.
        """
        # Typing simülasyonu
        if bool(s.get("typing_enabled", True)):
            await self.tg.send_typing(
                bot.token,
                chat.chat_id,
                self.typing_seconds(
                    db,
                    len(text),
                    bot=bot,
                    tempo_multiplier=tempo_multiplier,
                ),
            )

        # Mesajı gönder
        msg_id = await self.tg.send_message(
            token=bot.token,
            chat_id=chat.chat_id,
            text=text,
            reply_to_message_id=reply_msg.telegram_message_id if reply_msg else None,
            disable_preview=True,
        )

        # DB log (metadata ile birlikte kaydet)
        msg_metadata = extract_message_metadata(text, topic)
        db.add(Message(
            bot_id=bot.id,
            chat_db_id=chat.id,
            telegram_message_id=msg_id,
            text=text,
            reply_to_message_id=reply_msg.telegram_message_id if reply_msg else None,
            msg_metadata=msg_metadata,
        ))
        db.commit()

        # PHASE 1A.2: Invalidate chat cache after new message
        self.invalidate_chat_cache(chat.id)

        # ✅ PROMETHEUS METRIC: Başarılı mesaj
        if METRICS_ENABLED and bot_id_for_metric:
            import time
            duration = time.time() - start_time
            message_generation_total.labels(
                bot_id=str(bot_id_for_metric),
                status="success"
            ).inc()
            message_generation_duration_seconds.observe(duration)
            logger.debug(f"📊 Metric kaydedildi: bot={bot_id_for_metric}, süre={duration:.2f}s")

        self._persona_refresh[bot.id] = update_persona_refresh_state(
            refresh_state,
            triggered=should_refresh,
            now=now_utc(),
        )

    # ---- Generation Inputs Building (SESSION 25: Extracted from tick_once) ----
    def _build_generation_inputs(
        self,
        db: Session,
        *,
        bot: Bot,
        chat: Chat,
        s: Dict[str, Any],
        persona_profile: Dict[str, Any],
        emotion_profile: Dict[str, Any],
        stances: List[Dict[str, Any]],
        holdings: List[Dict[str, Any]],
        persona_hint: str,
        persona_refresh_note: str,
        topic_hint_pool: List[str],
        history_source: List[Message],
        history_excerpt: str,
        reply_msg: Optional[Message],
        reply_excerpt: str,
        mode: str,
        mention_ctx: str,
        contextual_examples: str,
    ) -> tuple:
        """
        Build all generation inputs (prompts, LLM parameters).

        SESSION 25: Extracted from tick_once to reduce complexity.

        Returns:
            Tuple of (user_prompt, system_prompt, temperature, max_tokens, top_p,
                     frequency_penalty, topic, reaction_plan, tempo_multiplier, bot_memories)
        """
        # Topic seç (cooldown filtreli havuzdan)
        topic = choose_topic_from_messages(history_source, topic_hint_pool)

        # ---- HABER TETIKLEYICI ----
        market_trigger = ""
        try:
            if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
                # PHASE 2 Week 4 Day 1-3: Rich News Integration (%50 olasılık)
                if random.random() < float(s.get("news_trigger_probability", 0.5)):
                    brief = self.news.get_brief(topic)
                    if brief:
                        market_trigger = brief
                        logger.debug(f"News trigger applied for topic '{topic}': {brief[:60]}...")
        except Exception as e:
            logger.debug("news trigger error: %s", e)

        reaction_plan = synthesize_reaction_plan(
            emotion_profile=emotion_profile,
            market_trigger=market_trigger,
        )
        tempo_multiplier = derive_tempo_multiplier(emotion_profile, reaction_plan)

        # Length hint
        selected_length_category = choose_message_length_category(
            s.get("message_length_profile")
        )
        length_hint = compose_length_hint(
            persona_profile=persona_profile,
            selected_category=selected_length_category,
        )

        # Zaman bağlamı oluştur
        time_context = generate_time_context()

        # ---- KİŞİSEL HAFIZA SİSTEMİ ----
        # Bot'un kişisel hafızalarını çek ve prompt'a ekle
        bot_memories = fetch_bot_memories(db, bot.id, limit=8)
        memories_text = format_memories_for_prompt(bot_memories)

        # Kullanılan hafızaları işaretle (usage_count güncelle)
        for memory in bot_memories:
            try:
                update_memory_usage(db, memory["id"])
            except Exception as e:
                logger.debug("Memory usage update error: %s", e)

        # ---- GEÇMİŞ REFERANS SİSTEMİ ----
        # Metadata çıkar (kullanılacak sembolleri tespit et)
        temp_metadata = extract_message_metadata(text="", topic=topic)
        current_symbols = temp_metadata.get("symbols", [])

        # Bot'un bu konu/sembollerde daha önce söylediklerini bul
        past_references = find_relevant_past_messages(
            db,
            bot_id=bot.id,
            current_topic=topic,
            current_symbols=current_symbols,
            days_back=7,
            limit=3,
        )
        past_references_text = format_past_references_for_prompt(past_references)

        user_prompt = generate_user_prompt(
            topic_name=topic,
            history_excerpt=shorten(history_excerpt, 400),
            reply_context=reply_excerpt,
            market_trigger=market_trigger,
            mode=mode,
            mention_context=mention_ctx,
            persona_profile=persona_profile,
            reaction_guidance=reaction_plan.instructions,
            emotion_profile=emotion_profile,
            contextual_examples=contextual_examples,
            stances=stances,
            holdings=holdings,
            memories=memories_text,
            past_references=past_references_text,
            length_hint=length_hint,
            persona_hint=persona_hint,
            persona_refresh_note=persona_refresh_note,
            time_context=time_context,
        )

        # ==== UNIQUE SYSTEM PROMPT ÜRET ====
        system_prompt = generate_system_prompt(
            persona_profile=persona_profile,
            emotion_profile=emotion_profile,
            bot_name=bot.name,
        )

        # ==== DİNAMİK LLM PARAMETRELERİ ====
        # Temperature: Bot kişiliğine göre değişir
        base_temp = 1.0
        tone = (persona_profile or {}).get("tone", "").lower()
        if "profesyonel" in tone or "akademik" in tone:
            temperature = base_temp + random.uniform(0.05, 0.10)  # 1.05-1.10 (kontrollü)
        else:
            temperature = base_temp + random.uniform(0.10, 0.20)  # 1.10-1.20 (yaratıcı)

        # PHASE 2 Week 4 Day 4-5: Dynamic Message Length
        # Base length: Bot persona'ya göre
        if "akademik" in tone or "tecrübeli" in tone or "profesyonel" in tone:
            base_min, base_max = 150, 250  # Uzun mesajlar
        elif "genç" in tone or "enerjik" in tone:
            base_min, base_max = 80, 150  # Kısa-orta
        else:
            base_min, base_max = 100, 200  # Orta

        # Context modifiers
        is_reply = (mode == "reply")
        is_question = False
        is_news_trigger = bool(market_trigger)

        # Soru mu kontrol et
        if reply_msg and reply_msg.text:
            is_question = ("?" in reply_msg.text or
                          any(w in reply_msg.text.lower() for w in ["nasıl", "neden", "ne zaman", "kim", "nerede"]))

        # Modifiers uygula
        if is_reply and not is_question:
            # Basit reply: daha kısa
            base_min = int(base_min * 0.7)
            base_max = int(base_max * 0.8)

        if is_question:
            # Soruya cevap: daha uzun
            base_min = int(base_min * 1.3)
            base_max = int(base_max * 1.4)

        if is_news_trigger:
            # Haber varsa: daha detaylı
            base_min = int(base_min * 1.2)
            base_max = int(base_max * 1.3)

        max_tokens = random.randint(base_min, base_max)

        # Top-p sampling
        top_p = 0.95

        # Frequency penalty (tekrarları önle)
        frequency_penalty = 0.5

        logger.debug(
            "LLM params for %s: temp=%.2f, max_tokens=%d (reply=%s, question=%s, news=%s), top_p=%.2f, freq_penalty=%.2f",
            bot.name, temperature, max_tokens, is_reply, is_question, is_news_trigger, top_p, frequency_penalty
        )

        return (
            user_prompt,
            system_prompt,
            temperature,
            max_tokens,
            top_p,
            frequency_penalty,
            topic,
            reaction_plan,
            tempo_multiplier,
            bot_memories,
        )

    # ---- Priority Queue İşleme ----
    def _check_priority_queue(self, db: Session) -> Optional[Dict[str, Any]]:
        """
        Redis priority queue'dan yüksek öncelikli mesajları kontrol eder.
        Returns: Priority queue item veya None
        """
        if not self._redis_sync_client:
            return None

        try:
            # Önce high priority queue'yu kontrol et
            raw_item = self._redis_sync_client.rpop("priority_queue:high")
            if raw_item:
                return json.loads(raw_item)

            # High yoksa normal queue'dan al
            raw_item = self._redis_sync_client.rpop("priority_queue:normal")
            if raw_item:
                return json.loads(raw_item)

            return None
        except Exception as e:
            logger.warning("Priority queue check failed: %s", e)
            return None

    async def _process_priority_message(self, db: Session, priority_item: Dict[str, Any]) -> bool:
        """
        Priority queue'dan gelen mesajı işle ve bot'un yanıt vermesini sağla.
        Returns: True if successfully processed
        """
        try:
            bot_id = priority_item.get("bot_id")
            chat_id = priority_item.get("chat_id")
            telegram_message_id = priority_item.get("telegram_message_id")
            user_text = priority_item.get("text", "")
            is_mentioned = priority_item.get("is_mentioned", False)
            is_reply_to_bot = priority_item.get("is_reply_to_bot", False)

            if not bot_id or not chat_id:
                logger.warning("Invalid priority item: missing bot_id or chat_id")
                return False

            # Bot'u DB'den çek
            bot = db.query(Bot).filter(Bot.id == bot_id, Bot.is_enabled.is_(True)).first()
            if not bot:
                logger.warning("Bot %s not found or disabled for priority response", bot_id)
                return False

            # Chat'i DB'den çek
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.warning("Chat %s not found for priority response", chat_id)
                return False

            # Kullanıcı mesajını DB'den bul (context için)
            incoming_msg = db.query(Message).filter(
                Message.telegram_message_id == telegram_message_id,
                Message.chat_db_id == chat_id,
            ).first()

            logger.info(
                "Processing priority message: bot=%s, chat=%s, mentioned=%s, reply=%s",
                bot.name,
                chat.title,
                is_mentioned,
                is_reply_to_bot,
            )

            # Persona/Stance/Holdings verileri
            (
                persona_profile,
                emotion_profile,
                stances,
                holdings,
                persona_hint,
            ) = self.fetch_psh(db, bot, topic_hint=None)

            # Son mesajları context olarak al - PHASE 1A.2: Cache-aware
            recent_msgs = self.fetch_recent_messages(db, chat.id, limit=40)

            # History transcript (kullanıcı mesajları da dahil!)
            history_source = list(recent_msgs[:8])  # Daha fazla context
            history_excerpt = build_history_transcript(list(reversed(history_source)))

            # Contextual examples
            contextual_examples = build_contextual_examples(
                list(reversed(recent_msgs)), bot_id=bot.id, max_pairs=3
            )

            # Topic seçimi (kullanıcı mesajından)
            topic_pool = chat.topics or ["BIST", "FX", "Kripto", "Makro"]
            topic = choose_topic_from_messages([incoming_msg] if incoming_msg else history_source, topic_pool)

            # Haber tetikleyici (priority mesajlar için daha düşük olasılık)
            s = self.settings(db)
            market_trigger = ""
            if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
                if random.random() < 0.4:  # Priority response için %40 olasılık
                    try:
                        brief = self.news.get_brief(topic)
                        if brief:
                            market_trigger = brief
                    except Exception as e:
                        logger.debug("News trigger error in priority response: %s", e)

            # Reaction plan
            reaction_plan = synthesize_reaction_plan(
                emotion_profile=emotion_profile,
                market_trigger=market_trigger,
            )
            tempo_multiplier = derive_tempo_multiplier(emotion_profile, reaction_plan)

            # Length hint
            selected_length_category = choose_message_length_category(
                s.get("message_length_profile")
            )
            length_hint = compose_length_hint(
                persona_profile=persona_profile,
                selected_category=selected_length_category,
            )

            # Time context
            time_context = generate_time_context()

            # Memories
            bot_memories = fetch_bot_memories(db, bot.id, limit=8)
            memories_text = format_memories_for_prompt(bot_memories)

            # Past references
            temp_metadata = extract_message_metadata(text=user_text, topic=topic)
            current_symbols = temp_metadata.get("symbols", [])
            past_references = find_relevant_past_messages(
                db,
                bot_id=bot.id,
                current_topic=topic,
                current_symbols=current_symbols,
                days_back=7,
                limit=3,
            )
            past_references_text = format_past_references_for_prompt(past_references)

            # User prompt için reply context
            reply_excerpt = shorten(user_text, 240)
            mention_ctx = ""

            # Priority response'da MUTLAKA reply mode
            user_prompt = generate_user_prompt(
                topic_name=topic,
                history_excerpt=shorten(history_excerpt, 400),
                reply_context=reply_excerpt,
                market_trigger=market_trigger,
                mode="reply",  # Priority mesajlar için her zaman reply
                mention_context=mention_ctx,
                persona_profile=persona_profile,
                reaction_guidance=reaction_plan.instructions,
                emotion_profile=emotion_profile,
                contextual_examples=contextual_examples,
                stances=stances,
                holdings=holdings,
                memories=memories_text,
                past_references=past_references_text,
                length_hint=length_hint,
                persona_hint=persona_hint,
                persona_refresh_note="",  # Priority için persona refresh atlayalım
                time_context=time_context,
            )

            # LLM üretimi
            text = self.llm.generate(user_prompt=user_prompt, temperature=0.75, max_tokens=220)
            if not text:
                logger.warning("LLM returned empty response for priority message")
                return False

            # Tutarlılık koruması
            if bool(s.get("consistency_guard_enabled", True)):
                revised = apply_consistency_guard(
                    self.llm,
                    draft_text=text,
                    persona_profile=persona_profile,
                    stances=stances,
                )
                if revised:
                    text = revised

            text = apply_reaction_overrides(text, reaction_plan)
            text = apply_micro_behaviors(
                text,
                emotion_profile=emotion_profile,
                plan=reaction_plan,
            )

            # İnsancıl geliştirmeler
            text = add_conversation_openings(text, probability=0.35)  # Priority için daha yüksek
            text = add_hesitation_markers(text, probability=0.25)
            text = add_colloquial_shortcuts(text, probability=0.20)
            text = add_filler_words(text, probability=0.25)
            text = apply_natural_imperfections(text, probability=0.12)

            # Typing simülasyonu
            if bool(s.get("typing_enabled", True)):
                await self.tg.send_typing(
                    bot.token,
                    chat.chat_id,
                    self.typing_seconds(
                        db,
                        len(text),
                        bot=bot,
                        tempo_multiplier=tempo_multiplier,
                    ),
                )

            # Mesajı gönder (reply olarak)
            msg_id = await self.tg.send_message(
                token=bot.token,
                chat_id=chat.chat_id,
                text=text,
                reply_to_message_id=telegram_message_id,  # Kullanıcı mesajına yanıt
                disable_preview=True,
            )

            # DB log
            msg_metadata = extract_message_metadata(text, topic)
            msg_metadata["is_priority_response"] = True
            msg_metadata["responded_to_message_id"] = telegram_message_id

            db.add(Message(
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=msg_id,
                text=text,
                reply_to_message_id=telegram_message_id,
                msg_metadata=msg_metadata,
            ))
            db.commit()

            # PHASE 1A.2: Invalidate chat cache after new message
            self.invalidate_chat_cache(chat.id)

            logger.info("Priority response sent: bot=%s, text_preview=%s", bot.name, text[:50])
            return True

        except Exception as e:
            logger.exception("Priority message processing failed: %s", e)
            return False

    # ---- Akış ----
    async def tick_once(self) -> None:
        db: Session = SessionLocal()
        import time  # Timer için
        start_time = time.time()  # Kronometre başlat
        bot_id_for_metric = None  # Metrik için bot ID'yi saklayacağız

        try:
            s = self.settings(db)
            if not bool(s.get("simulation_active", False)):
                await asyncio.sleep(1.0)
                return

            # ÖNCELİK 1: Priority queue'dan gelen mesajları kontrol et
            priority_item = self._check_priority_queue(db)
            if priority_item:
                # Priority mesajı işle (kullanıcı mention/reply'leri)
                success = await self._process_priority_message(db, priority_item)
                if success:
                    # Priority mesaj işlendikten sonra kısa bir gecikme
                    await asyncio.sleep(2.0)
                else:
                    # Başarısızsa biraz daha bekle
                    await asyncio.sleep(5.0)
                return  # Priority işlendikten sonra normal akışa geri dön

            # Global rate limit
            if not self.global_rate_ok(db):
                await asyncio.sleep(2.5)
                return

            chat = self.pick_chat(db)
            if not chat:
                logger.info("Aktif chat yok; bekleniyor.")
                await asyncio.sleep(2.0)
                return

            bot = self.pick_bot(
                db,
                hourly_limit=s.get("bot_hourly_msg_limit", {"max": 12}),
                chat=chat,
            )
            if not bot:
                logger.info("Saatlik sınır nedeniyle uygun bot bulunamadı; bekleniyor.")
                await asyncio.sleep(3.0)
                return

            # Metrik için bot ID'yi sakla
            bot_id_for_metric = bot.id

            # Persona/Stance/Holdings verilerini çek (erken çekiyoruz çünkü topic seçiminde cooldown gerekiyor)
            topic_hint_pool = (chat.topics or ["BIST", "FX", "Kripto", "Makro"]).copy()

            (
                persona_profile,
                emotion_profile,
                stances,
                holdings,
                persona_hint,
            ) = self.fetch_psh(db, bot, topic_hint=None)

            refresh_state = self._persona_refresh.setdefault(
                bot.id,
                {
                    "messages_since": 0,
                    "last": datetime.min.replace(tzinfo=UTC),
                },
            )
            now = now_utc()
            refresh_interval = int(s.get("persona_refresh_interval", 8))
            refresh_minutes = int(s.get("persona_refresh_minutes", 30))
            should_refresh, normalized_state = should_refresh_persona(
                refresh_state,
                refresh_interval=refresh_interval,
                refresh_minutes=refresh_minutes,
                now=now,
            )
            refresh_state.update(normalized_state)

            persona_refresh_note = (
                compose_persona_refresh_note(persona_profile, persona_hint, emotion_profile)
                if should_refresh
                else ""
            )

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
                    # TEMPORARY FIX (Session 14): Telegram setMessageReaction returns 400
                    # ok = await self.tg.try_set_reaction(bot.token, chat.chat_id, target.telegram_message_id)
                    ok = False  # Skip reaction API, use fallback emoji message
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
                        # logla (metadata ile)
                        emoji_metadata = extract_message_metadata(emoji, topic_hint_pool[0] if topic_hint_pool else "")
                        db.add(Message(
                            bot_id=bot.id,
                            chat_db_id=chat.id,
                            telegram_message_id=msg_id,
                            text=emoji,
                            reply_to_message_id=target.telegram_message_id,
                            msg_metadata=emoji_metadata,
                        ))
                        db.commit()
                    await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                    return

            # SESSION 25: Context preparation (extracted)
            (
                recent_msgs,
                reply_msg,
                mention_handle,
                mode,
                mention_ctx,
                history_excerpt,
                reply_excerpt,
                contextual_examples,
            ) = self._prepare_context_data(
                db,
                chat=chat,
                bot=bot,
                s=s,
            )
            history_source = list(recent_msgs[:15])  # For topic selection

            # SESSION 25: Generation inputs building (extracted)
            (
                user_prompt,
                system_prompt,
                temperature,
                max_tokens,
                top_p,
                frequency_penalty,
                topic,
                reaction_plan,
                tempo_multiplier,
                bot_memories,
            ) = self._build_generation_inputs(
                db,
                bot=bot,
                chat=chat,
                s=s,
                persona_profile=persona_profile,
                emotion_profile=emotion_profile,
                stances=stances,
                holdings=holdings,
                persona_hint=persona_hint,
                persona_refresh_note=persona_refresh_note,
                topic_hint_pool=topic_hint_pool,
                history_source=history_source,
                history_excerpt=history_excerpt,
                reply_msg=reply_msg,
                reply_excerpt=reply_excerpt,
                mode=mode,
                mention_ctx=mention_ctx,
                contextual_examples=contextual_examples,
            )

            # SESSION 25: Message processing (extracted)
            text, should_skip = self._process_generated_text(
                db,
                bot=bot,
                s=s,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                persona_profile=persona_profile,
                emotion_profile=emotion_profile,
                stances=stances,
                reaction_plan=reaction_plan,
                mention_ctx=mention_ctx,
            )
            if should_skip:
                await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                return

            # SESSION 25: Message finalization (extracted)
            text, should_skip = self._finalize_message_text(
                db,
                bot=bot,
                s=s,
                text=text,
                recent_msgs=recent_msgs,
            )
            if should_skip:
                await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                return

            # SESSION 25: Message sending (extracted)
            await self._send_message_to_chat(
                db,
                bot=bot,
                chat=chat,
                s=s,
                text=text,
                topic=topic,
                reply_msg=reply_msg,
                tempo_multiplier=tempo_multiplier,
                bot_id_for_metric=bot_id_for_metric,
                start_time=start_time,
                refresh_state=refresh_state,
                should_refresh=should_refresh,
            )

            # Sonraki gecikme
            await asyncio.sleep(self.next_delay_seconds(db, bot=bot))

        except Exception as e:
            logger.exception("tick_once error: %s", e)

            # ❌ PROMETHEUS METRIC: Başarısız mesaj
            if METRICS_ENABLED and bot_id_for_metric:
                message_generation_total.labels(
                    bot_id=str(bot_id_for_metric),
                    status="failed"
                ).inc()
                logger.debug(f"📊 Metric kaydedildi: bot={bot_id_for_metric}, status=failed")

            await asyncio.sleep(3.0)
        finally:
            db.close()

    # ---- Message queue processor ----
    async def _process_message_queue(self) -> None:
        """
        Background task to process queued messages.

        Continuously dequeues messages and attempts to send them via Telegram.
        Uses blocking dequeue with timeout to avoid busy-waiting.
        """
        logger.info("Message queue processor started")

        while True:
            try:
                # Dequeue next message (blocks for up to 1 second)
                message = self.msg_queue.dequeue(block=True, timeout=1.0)

                if message is None:
                    # No messages in queue, continue
                    await asyncio.sleep(0.1)
                    continue

                # Attempt to send message
                try:
                    msg_id = await self.tg.send_message(
                        token=message.bot_token,
                        chat_id=message.chat_id,
                        text=message.text,
                        reply_to_message_id=message.reply_to_message_id,
                        disable_preview=message.disable_preview,
                        parse_mode=message.parse_mode,
                        skip_rate_limit=False,  # Apply rate limiting
                    )

                    if msg_id:
                        # Success - acknowledge message
                        self.msg_queue.ack(message)
                        logger.debug(
                            "Queued message sent successfully: chat=%s, msg_id=%s",
                            message.chat_id, msg_id
                        )

                        # Update database if message_id provided
                        if message.message_id and message.bot_id:
                            db = SessionLocal()
                            try:
                                db_msg = db.query(Message).filter(Message.id == message.message_id).first()
                                if db_msg:
                                    db_msg.telegram_message_id = msg_id
                                    db.commit()
                            except Exception as e:
                                logger.warning("Failed to update message in DB: %s", e)
                            finally:
                                db.close()
                    else:
                        # Send failed - nack and retry
                        self.msg_queue.nack(message, "send_message returned None")

                except Exception as e:
                    # Send error - nack and retry
                    error_msg = str(e)
                    logger.warning(
                        "Failed to send queued message (retry %d/%d): %s",
                        message.retry_count + 1, message.max_retries, error_msg
                    )
                    self.msg_queue.nack(message, error_msg)

                # Small delay between messages
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.exception("Error in message queue processor: %s", e)
                await asyncio.sleep(1.0)

    async def run_forever(self):
        logger.info("BehaviorEngine started. CTRL+C ile durdurabilirsiniz.")

        # Redis listener'ı başlat
        if self._redis_url and self._redis_task is None:
            self._redis_task = asyncio.create_task(self._config_listener(), name="config_listener")

        # Message queue processor'ı başlat
        if self._queue_processor_task is None:
            self._queue_processor_task = asyncio.create_task(
                self._process_message_queue(),
                name="queue_processor"
            )
            logger.info("Message queue processor task created")

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

        # Queue processor iptali
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._queue_processor_task
            self._queue_processor_task = None
            logger.info("Message queue processor stopped")

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
