"""
Redis cache layer (optional)

Provides shared caching across multiple workers
"""

import json
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis-based cache layer

    Features:
    - Shared cache across workers
    - TTL support (native Redis)
    - JSON serialization
    - Graceful fallback if Redis unavailable
    """

    def __init__(self, redis_client: Optional[Any] = None, default_ttl_seconds: int = 900):
        """
        Args:
            redis_client: Redis client instance (from redis-py or similar)
            default_ttl_seconds: Default TTL in seconds (default 15 minutes)
        """
        self.redis_client = redis_client
        self.default_ttl_seconds = default_ttl_seconds
        self.enabled = redis_client is not None

        # Statistics
        self._hits = 0
        self._misses = 0

        if not self.enabled:
            logger.warning("RedisCache initialized without Redis client - cache disabled")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from Redis cache

        Returns:
            Cached value if found, None otherwise
        """
        if not self.enabled:
            self._misses += 1
            return None

        try:
            value_json = self.redis_client.get(key)
            if value_json is None:
                self._misses += 1
                return None

            # Deserialize JSON
            value = json.loads(value_json)
            self._hits += 1
            return value

        except Exception as e:
            logger.warning("Redis get error for key %s: %s", key, e)
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set value in Redis cache

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_seconds: TTL in seconds (uses default if None)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # Serialize to JSON
            value_json = json.dumps(value, default=str)  # default=str for datetime/UUID

            # Set with TTL
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            self.redis_client.setex(key, ttl, value_json)
            return True

        except Exception as e:
            logger.warning("Redis set error for key %s: %s", key, e)
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from Redis

        Returns:
            True if key was deleted, False otherwise
        """
        if not self.enabled:
            return False

        try:
            result = self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning("Redis delete error for key %s: %s", key, e)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern

        Args:
            pattern: Redis pattern (e.g., "bot:123:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            # Find keys matching pattern
            keys = list(self.redis_client.scan_iter(match=pattern))
            if not keys:
                return 0

            # Delete all matching keys
            return self.redis_client.delete(*keys)

        except Exception as e:
            logger.warning("Redis delete_pattern error for pattern %s: %s", pattern, e)
            return 0

    def clear(self) -> bool:
        """
        Clear all cache (DANGEROUS - flushes entire Redis DB)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            self.redis_client.flushdb()
            return True
        except Exception as e:
            logger.warning("Redis clear error: %s", e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict with hits, misses, hit_rate
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "enabled": self.enabled,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
        }

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self._hits = 0
        self._misses = 0
