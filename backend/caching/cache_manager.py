"""
Cache Manager - Multi-layer caching orchestrator

Coordinates L1 (LRU) and L2 (Redis) caches for bot profiles and message history
"""

import logging
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime

from .lru_cache import LRUCache
from .redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass
class BotProfileData:
    """Cached bot profile data"""
    bot_id: int
    name: str
    persona_profile: Dict[str, Any]
    emotion_profile: Dict[str, Any]
    stances: List[Dict[str, Any]]
    holdings: List[Dict[str, Any]]
    persona_hint: str
    cached_at: str  # ISO timestamp


@dataclass
class CacheStats:
    """Aggregate cache statistics"""
    l1_stats: Dict[str, Any]
    l2_stats: Dict[str, Any]
    total_hit_rate: float


class CacheManager:
    """
    Multi-layer cache manager

    Architecture:
    - L1: In-memory LRU cache (fast, process-local)
    - L2: Redis cache (shared, optional)

    Cache keys:
    - Bot profile: bot:{bot_id}:profile
    - Message history: chat:{chat_id}:messages:last:{limit}
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        l1_max_size: int = 1000,
        l1_default_ttl: int = 900,  # 15 minutes
        l2_default_ttl: int = 1800,  # 30 minutes
    ):
        """
        Args:
            redis_client: Optional Redis client for L2 cache
            l1_max_size: L1 cache max size (default 1000)
            l1_default_ttl: L1 TTL in seconds (default 15 min)
            l2_default_ttl: L2 TTL in seconds (default 30 min)
        """
        # Layer 1: In-memory LRU cache
        self.l1_cache = LRUCache(max_size=l1_max_size, default_ttl_seconds=l1_default_ttl)

        # Layer 2: Redis cache (optional)
        self.l2_cache = RedisCache(redis_client=redis_client, default_ttl_seconds=l2_default_ttl)

        logger.info(
            "CacheManager initialized (L1: max_size=%d, ttl=%ds | L2: enabled=%s, ttl=%ds)",
            l1_max_size,
            l1_default_ttl,
            self.l2_cache.enabled,
            l2_default_ttl,
        )

    # ===== Bot Profile Caching =====

    def get_bot_profile(self, bot_id: int) -> Optional[BotProfileData]:
        """
        Get bot profile from cache

        Flow:
        1. Check L1 (LRU)
        2. If miss, check L2 (Redis)
        3. If L2 hit, populate L1
        4. Return None if both miss (caller must fetch from DB)

        Args:
            bot_id: Bot ID

        Returns:
            BotProfileData if found, None otherwise
        """
        key = f"bot:{bot_id}:profile"

        # Try L1 first
        data = self.l1_cache.get(key)
        if data:
            return BotProfileData(**data)

        # Try L2
        data = self.l2_cache.get(key)
        if data:
            # Populate L1
            self.l1_cache.set(key, data, ttl_seconds=900)  # 15 min in L1
            return BotProfileData(**data)

        # Cache miss
        return None

    def set_bot_profile(self, profile: BotProfileData) -> None:
        """
        Set bot profile in cache (both L1 and L2)

        Args:
            profile: BotProfileData to cache
        """
        key = f"bot:{profile.bot_id}:profile"
        data = asdict(profile)

        # Set in L1 (15 min TTL)
        self.l1_cache.set(key, data, ttl_seconds=900)

        # Set in L2 (30 min TTL)
        self.l2_cache.set(key, data, ttl_seconds=1800)

        logger.debug("Cached bot profile: bot_id=%d", profile.bot_id)

    def invalidate_bot(self, bot_id: int) -> None:
        """
        Invalidate bot profile cache

        Args:
            bot_id: Bot ID to invalidate
        """
        pattern = f"bot:{bot_id}:"

        # Delete from L1
        self.l1_cache.delete_pattern(pattern)

        # Delete from L2
        self.l2_cache.delete_pattern(f"{pattern}*")

        logger.info("Invalidated bot cache: bot_id=%d", bot_id)

    # ===== Message History Caching =====

    def get_chat_messages(self, chat_id: int, limit: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get chat message history from cache

        Flow: Same as get_bot_profile

        Args:
            chat_id: Chat ID
            limit: Number of messages (last N)

        Returns:
            List of message dicts if found, None otherwise
        """
        key = f"chat:{chat_id}:messages:last:{limit}"

        # Try L1 first
        data = self.l1_cache.get(key)
        if data:
            return data

        # Try L2
        data = self.l2_cache.get(key)
        if data:
            # Populate L1 (shorter TTL for messages - 30 sec)
            self.l1_cache.set(key, data, ttl_seconds=30)
            return data

        # Cache miss
        return None

    def set_chat_messages(self, chat_id: int, limit: int, messages: List[Dict[str, Any]]) -> None:
        """
        Set chat message history in cache

        Args:
            chat_id: Chat ID
            limit: Number of messages
            messages: List of message dicts
        """
        key = f"chat:{chat_id}:messages:last:{limit}"

        # Set in L1 (30 sec TTL - messages change frequently)
        self.l1_cache.set(key, messages, ttl_seconds=30)

        # Set in L2 (60 sec TTL)
        self.l2_cache.set(key, messages, ttl_seconds=60)

        logger.debug("Cached chat messages: chat_id=%d, limit=%d, count=%d", chat_id, limit, len(messages))

    def invalidate_chat(self, chat_id: int) -> None:
        """
        Invalidate chat message cache

        Args:
            chat_id: Chat ID to invalidate
        """
        pattern = f"chat:{chat_id}:"

        # Delete from L1
        self.l1_cache.delete_pattern(pattern)

        # Delete from L2
        self.l2_cache.delete_pattern(f"{pattern}*")

        logger.info("Invalidated chat cache: chat_id=%d", chat_id)

    # ===== Statistics & Management =====

    def get_stats(self) -> CacheStats:
        """
        Get aggregate cache statistics

        Returns:
            CacheStats with L1 and L2 stats
        """
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()

        # Calculate total hit rate (weighted by L1 since it's checked first)
        total_hit_rate = l1_stats.get("hit_rate_percent", 0.0)

        return CacheStats(
            l1_stats=l1_stats,
            l2_stats=l2_stats,
            total_hit_rate=total_hit_rate,
        )

    def clear_all(self) -> None:
        """Clear all caches (L1 and L2)"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        logger.warning("All caches cleared")

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self.l1_cache.reset_stats()
        self.l2_cache.reset_stats()
        logger.info("Cache statistics reset")
