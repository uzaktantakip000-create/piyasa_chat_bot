"""
Embedding Cache Module

P0.1 Critical Fix: Cache sentence transformer embeddings to avoid recomputation
Reduces 50,000 embeddings/hour to ~1,000 with 100 bots

Uses Redis for distributed cache with 24-hour TTL
"""

import hashlib
import logging
import pickle
from typing import Optional, List
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Redis-backed cache for sentence transformer embeddings

    Cache key format: "embedding:{message_hash}"
    TTL: 24 hours (embeddings don't change, long cache is safe)
    """

    def __init__(self, redis_client=None, ttl_seconds: int = 86400):
        """
        Initialize embedding cache

        Args:
            redis_client: Redis client instance (optional, graceful degradation if None)
            ttl_seconds: Cache TTL in seconds (default: 24 hours)
        """
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.enabled = redis_client is not None

        # Metrics
        self.hits = 0
        self.misses = 0
        self.errors = 0

        if not self.enabled:
            logger.warning("EmbeddingCache initialized without Redis - cache disabled")
        else:
            logger.info(f"EmbeddingCache initialized with TTL={ttl_seconds}s")

    def _hash_text(self, text: str) -> str:
        """Generate stable hash for text"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def _cache_key(self, text: str) -> str:
        """Generate Redis cache key"""
        text_hash = self._hash_text(text)
        return f"embedding:{text_hash}"

    def get(self, text: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding from cache

        Args:
            text: Message text

        Returns:
            Embedding array or None if not cached
        """
        if not self.enabled:
            return None

        try:
            key = self._cache_key(text)
            cached = self.redis.get(key)

            if cached is None:
                self.misses += 1
                return None

            # Deserialize numpy array
            embedding = pickle.loads(cached)
            self.hits += 1

            logger.debug(f"Cache HIT: {text[:30]}... (key={key})")
            return embedding

        except Exception as e:
            self.errors += 1
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, text: str, embedding: np.ndarray) -> bool:
        """
        Store embedding in cache

        Args:
            text: Message text
            embedding: Numpy embedding array

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            key = self._cache_key(text)

            # Serialize numpy array
            serialized = pickle.dumps(embedding)

            # Store with TTL
            self.redis.setex(key, self.ttl, serialized)

            logger.debug(f"Cache SET: {text[:30]}... (key={key})")
            return True

        except Exception as e:
            self.errors += 1
            logger.error(f"Cache set error: {e}")
            return False

    def get_many(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        Retrieve multiple embeddings (batch operation)

        Args:
            texts: List of message texts

        Returns:
            List of embeddings (None for cache misses)
        """
        if not self.enabled:
            return [None] * len(texts)

        results = []
        for text in texts:
            embedding = self.get(text)
            results.append(embedding)

        return results

    def set_many(self, texts: List[str], embeddings: List[np.ndarray]) -> int:
        """
        Store multiple embeddings (batch operation)

        Args:
            texts: List of message texts
            embeddings: List of embedding arrays

        Returns:
            Number of successfully cached embeddings
        """
        if not self.enabled:
            return 0

        if len(texts) != len(embeddings):
            logger.error(f"Texts/embeddings length mismatch: {len(texts)} vs {len(embeddings)}")
            return 0

        success_count = 0
        for text, embedding in zip(texts, embeddings):
            if self.set(text, embedding):
                success_count += 1

        return success_count

    def get_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dict with hits, misses, hit_rate, errors
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "errors": self.errors,
            "enabled": self.enabled
        }

    def clear_stats(self):
        """Reset statistics counters"""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        logger.info("Cache statistics cleared")


# Test function
def test_embedding_cache():
    """Test embedding cache with dummy data"""
    import redis

    # Connect to Redis
    try:
        r = redis.Redis.from_url("redis://localhost:6379/0", decode_responses=False)
        r.ping()
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return

    # Initialize cache
    cache = EmbeddingCache(r, ttl_seconds=60)

    # Test data
    text1 = "BIST100 bugün yükseldi"
    text2 = "Dolar düştü, TL güçlendi"
    embedding1 = np.array([0.1, 0.2, 0.3, 0.4])
    embedding2 = np.array([0.5, 0.6, 0.7, 0.8])

    print("\n📊 Embedding Cache Test")
    print("=" * 50)

    # Test 1: Set and get
    print("\n[Test 1] Set and Get")
    cache.set(text1, embedding1)
    result = cache.get(text1)
    assert result is not None, "Cache miss on fresh set!"
    assert np.array_equal(result, embedding1), "Embedding mismatch!"
    print(f"✅ Set and get successful: {result}")

    # Test 2: Cache miss
    print("\n[Test 2] Cache Miss")
    result = cache.get("Nonexistent text")
    assert result is None, "Expected cache miss!"
    print("✅ Cache miss handled correctly")

    # Test 3: Batch operations
    print("\n[Test 3] Batch Operations")
    cache.set_many([text1, text2], [embedding1, embedding2])
    results = cache.get_many([text1, text2])
    assert len(results) == 2, "Wrong result count!"
    assert np.array_equal(results[0], embedding1), "Embedding1 mismatch!"
    assert np.array_equal(results[1], embedding2), "Embedding2 mismatch!"
    print(f"✅ Batch operations successful: {len(results)} embeddings")

    # Test 4: Statistics
    print("\n[Test 4] Statistics")
    stats = cache.get_stats()
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit Rate: {stats['hit_rate_percent']}%")
    print(f"  Errors: {stats['errors']}")
    assert stats['hits'] > 0, "No cache hits recorded!"
    print("✅ Statistics tracking works")

    print("\n" + "=" * 50)
    print("✅ All tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_embedding_cache()
