"""
In-memory LRU (Least Recently Used) Cache implementation

Thread-safe, TTL-based cache with max size limit.
"""

import time
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Cache entry with TTL support"""
    value: Any
    expires_at: float  # Unix timestamp


class LRUCache:
    """
    Thread-safe LRU cache with TTL support

    Features:
    - Max size limit (evicts least recently used when full)
    - TTL (Time To Live) per entry
    - Thread-safe operations
    - Hit/miss statistics
    """

    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 900):
        """
        Args:
            max_size: Maximum number of entries (default 1000)
            default_ttl_seconds: Default TTL in seconds (default 15 minutes)
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Returns:
            Cached value if found and not expired, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check if expired
            if time.time() > entry.expires_at:
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL in seconds (uses default if None)
        """
        with self._lock:
            # Calculate expiration time
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            expires_at = time.time() + ttl

            # Create entry
            entry = CacheEntry(value=value, expires_at=expires_at)

            # If key exists, update it
            if key in self._cache:
                self._cache[key] = entry
                self._cache.move_to_end(key)
                return

            # Check if cache is full
            if len(self._cache) >= self.max_size:
                # Evict least recently used (first item)
                self._cache.popitem(last=False)
                self._evictions += 1

            # Add new entry
            self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern (simple prefix match)

        Args:
            pattern: Key prefix to match (e.g., "bot:123:")

        Returns:
            Number of keys deleted
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get current cache size"""
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict with hits, misses, evictions, size, hit_rate
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate_percent": round(hit_rate, 2),
            }

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
