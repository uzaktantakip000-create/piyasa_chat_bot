"""
Multi-Layer Caching System

Provides L1 (in-memory) and L2 (Redis) caching with:
- Automatic fallback if Redis unavailable
- TTL (time-to-live) support
- Pattern-based invalidation
- Cache-aside pattern with loader functions
- Thread-safe operations
"""

import logging
import pickle
import time
from typing import Any, Callable, Optional, Dict
from threading import Lock
import os

# Redis (optional dependency)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL support."""
    __slots__ = ('value', 'expires_at')

    def __init__(self, value: Any, ttl: Optional[int] = None):
        self.value = value
        self.expires_at = time.time() + ttl if ttl else None

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class L1Cache:
    """In-memory LRU cache with TTL support. Thread-safe, process-local."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if exists and not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        with self._lock:
            # Simple LRU: remove oldest if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                first_key = next(iter(self._cache))
                del self._cache[first_key]

            self._cache[key] = CacheEntry(value, ttl)

    def invalidate(self, key: str) -> None:
        """Remove specific key from cache."""
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        """Remove all keys matching pattern (simple glob). Returns count."""
        with self._lock:
            if '*' in pattern:
                prefix = pattern.split('*')[0]
                keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            else:
                keys_to_remove = [pattern] if pattern in self._cache else []

            for key in keys_to_remove:
                del self._cache[key]

            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
            }


class L2Cache:
    """Redis-based distributed cache. Shared across workers, optional fallback."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        self.available = False

        if not REDIS_AVAILABLE:
            logger.warning("redis package not installed, L2 cache disabled")
            return

        redis_url = redis_url or os.getenv("REDIS_URL")
        if not redis_url:
            logger.info("REDIS_URL not set, L2 cache disabled")
            return

        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # We'll use pickle
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self.redis_client.ping()
            self.available = True
            logger.info("L2 Redis cache connected")
        except Exception as e:
            logger.warning("L2 Redis cache unavailable: %s", e)
            self.redis_client = None

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        if not self.available or not self.redis_client:
            return None

        try:
            data = self.redis_client.get(key)
            if data is None:
                return None
            return pickle.loads(data)
        except Exception as e:
            logger.debug("L2 cache get error for %s: %s", key, e)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in Redis cache with optional TTL."""
        if not self.available or not self.redis_client:
            return

        try:
            data = pickle.dumps(value)
            if ttl:
                self.redis_client.setex(key, ttl, data)
            else:
                self.redis_client.set(key, data)
        except Exception as e:
            logger.debug("L2 cache set error for %s: %s", key, e)

    def invalidate(self, key: str) -> None:
        """Remove specific key from Redis."""
        if not self.available or not self.redis_client:
            return

        try:
            self.redis_client.delete(key)
        except Exception:
            pass

    def invalidate_pattern(self, pattern: str) -> int:
        """Remove all keys matching pattern using Redis SCAN. Returns count."""
        if not self.available or not self.redis_client:
            return 0

        try:
            count = 0
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    self.redis_client.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            return 0


class CacheManager:
    """
    Multi-layer cache manager with L1 (in-memory) and L2 (Redis).
    Implements cache-aside pattern with automatic loader function.
    Thread-safe singleton.
    """

    _instance: Optional['CacheManager'] = None
    _lock = Lock()

    def __init__(self):
        # L1: In-memory cache (fast, process-local)
        max_size = int(os.getenv("CACHE_L1_MAX_SIZE", "1000"))
        self.l1 = L1Cache(max_size=max_size)

        # L2: Redis cache (shared, optional)
        self.l2 = L2Cache()

        logger.info(
            "CacheManager initialized (L1: %d entries, L2: %s)",
            max_size,
            "enabled" if self.l2.available else "disabled"
        )

    @classmethod
    def get_instance(cls) -> 'CacheManager':
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(
        self,
        key: str,
        loader: Optional[Callable[[], Any]] = None,
        ttl: Optional[int] = None,
        use_l2: bool = True
    ) -> Optional[Any]:
        """
        Get value from cache or load with loader function.

        Args:
            key: Cache key
            loader: Function to load value if not in cache
            ttl: Time-to-live in seconds (None = no expiration)
            use_l2: Whether to use L2 (Redis) cache

        Returns:
            Cached or loaded value, None if not found and no loader
        """
        # Try L1 cache
        value = self.l1.get(key)
        if value is not None:
            return value

        # Try L2 cache
        if use_l2:
            value = self.l2.get(key)
            if value is not None:
                # Populate L1 from L2
                self.l1.set(key, value, ttl)
                return value

        # Load from source if loader provided
        if loader is not None:
            try:
                value = loader()
                if value is not None:
                    self.set(key, value, ttl, use_l2=use_l2)
                return value
            except Exception as e:
                logger.exception("Cache loader error for %s: %s", key, e)
                return None

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        use_l2: bool = True
    ) -> None:
        """Set value in both cache layers."""
        self.l1.set(key, value, ttl)
        if use_l2:
            self.l2.set(key, value, ttl)

    def invalidate(self, key: str, use_l2: bool = True) -> None:
        """Invalidate specific key in both cache layers."""
        self.l1.invalidate(key)
        if use_l2:
            self.l2.invalidate(key)

    def invalidate_pattern(self, pattern: str, use_l2: bool = True) -> int:
        """Invalidate all keys matching pattern in both cache layers. Returns count."""
        count_l1 = self.l1.invalidate_pattern(pattern)
        count_l2 = 0
        if use_l2:
            count_l2 = self.l2.invalidate_pattern(pattern)

        total = count_l1 + count_l2
        if total > 0:
            logger.info("Invalidated %d keys matching pattern: %s", total, pattern)
        return total

    def clear(self, use_l2: bool = False) -> None:
        """Clear all cache entries."""
        self.l1.clear()
        logger.info("L1 cache cleared")

        if use_l2 and self.l2.available:
            # Note: We don't implement full Redis flush for safety
            # Use invalidate_pattern() for targeted clearing
            logger.warning("L2 cache clear not implemented (use invalidate_pattern)")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        return {
            "l1": self.l1.get_stats(),
            "l2": {
                "available": self.l2.available,
                "enabled": self.l2.redis_client is not None,
            }
        }
