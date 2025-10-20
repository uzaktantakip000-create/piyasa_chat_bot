"""
Semantic Deduplication Module

PHASE 2 Week 3 Day 1-3: Anlamsal benzerlik kontrolü ile tekrar önleme
P0.1 Critical Fix: Embedding cache to avoid recomputation

Sentence transformers kullanarak embedding-based similarity detection.
"""

import logging
from typing import List, Tuple, Optional
from embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)

# Optional: Lazy import for sentence-transformers (requires pip install)
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SEMANTIC_DEDUP_AVAILABLE = True
except ImportError:
    SEMANTIC_DEDUP_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Semantic dedup disabled. Install: pip install sentence-transformers")


class SemanticDeduplicator:
    """
    Anlamsal benzerlik ile tekrar tespiti

    Embedding-based similarity kullanarak mesajların anlamsal benzerliğini kontrol eder.
    Eşik değerini aşan benzer mesajları paraphrase eder veya reddeder.
    """

    def __init__(self, similarity_threshold: float = 0.85, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2', redis_client=None):
        """
        Initialize semantic deduplicator

        Args:
            similarity_threshold: Benzerlik eşiği (0.0-1.0). Default 0.85 (%85)
            model_name: Sentence transformer model adı
            redis_client: Redis client for embedding cache (optional)
        """
        self.similarity_threshold = similarity_threshold
        self.model = None
        self.enabled = SEMANTIC_DEDUP_AVAILABLE
        self.redis = redis_client

        # P0.1: Initialize embedding cache
        self.embedding_cache = EmbeddingCache(redis_client, ttl_seconds=86400)  # 24 hour TTL

        # P1.2: Paraphrase cache
        self.paraphrase_cache_ttl = 21600  # 6 hours

        # P1.3: Model name for lazy loading
        self.model_name = model_name
        self.model_loading = False

        if not SEMANTIC_DEDUP_AVAILABLE:
            logger.warning("SemanticDeduplicator initialized but sentence-transformers not available")
            return

        # P1.3: Lazy initialization - model will load on first use
        logger.info(f"SemanticDeduplicator initialized (model: {model_name}, lazy load enabled)")

    def _ensure_model_loaded(self):
        """
        P1.3: Lazy load model on first use (non-blocking initialization)

        Returns:
            bool: True if model loaded successfully
        """
        if self.model is not None:
            return True

        if self.model_loading:
            logger.debug("Model loading already in progress...")
            return False

        if not SEMANTIC_DEDUP_AVAILABLE:
            return False

        try:
            self.model_loading = True
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Semantic deduplication model loaded successfully")
            self.model_loading = False
            return True
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            self.enabled = False
            self.model_loading = False
            return False

    def is_duplicate(self, new_message: str, recent_messages: List[str]) -> Tuple[bool, float]:
        """
        Yeni mesaj mevcut mesajlara çok mu benziyor?

        P0.1 Fix: Uses embedding cache to avoid recomputation
        P1.3 Fix: Lazy loads model on first use

        Args:
            new_message: Kontrol edilecek yeni mesaj
            recent_messages: Karşılaştırılacak son mesajlar listesi

        Returns:
            (is_duplicate: bool, max_similarity: float)
        """
        if not self.enabled:
            return False, 0.0

        # P1.3: Ensure model is loaded
        if not self._ensure_model_loaded():
            return False, 0.0

        if not recent_messages or not new_message.strip():
            return False, 0.0

        try:
            # P0.1: Try to get new message embedding from cache
            new_embedding = self.embedding_cache.get(new_message)
            if new_embedding is None:
                # Cache miss - encode and cache
                new_embedding = self.model.encode([new_message])[0]
                self.embedding_cache.set(new_message, new_embedding)

            # P0.1: Try to get recent embeddings from cache (batch)
            recent_embeddings = []
            cache_results = self.embedding_cache.get_many(recent_messages)

            # Separate cache hits and misses
            to_encode = []
            to_encode_indices = []
            for i, (msg, cached_emb) in enumerate(zip(recent_messages, cache_results)):
                if cached_emb is not None:
                    recent_embeddings.append(cached_emb)
                else:
                    to_encode.append(msg)
                    to_encode_indices.append(i)

            # Encode cache misses
            if to_encode:
                newly_encoded = self.model.encode(to_encode)
                # Cache newly encoded embeddings
                self.embedding_cache.set_many(to_encode, newly_encoded)
                # Insert into results at correct indices
                for idx, emb in zip(to_encode_indices, newly_encoded):
                    recent_embeddings.insert(idx, emb)

            # Cosine similarity hesapla
            similarities = []
            for rec_emb in recent_embeddings:
                # Cosine similarity = dot product / (norm1 * norm2)
                similarity = np.dot(new_embedding, rec_emb) / (
                    np.linalg.norm(new_embedding) * np.linalg.norm(rec_emb)
                )
                similarities.append(similarity)

            max_similarity = max(similarities) if similarities else 0.0

            is_dup = max_similarity > self.similarity_threshold

            if is_dup:
                logger.debug(f"Duplicate detected: similarity={max_similarity:.3f} (threshold={self.similarity_threshold})")

            return is_dup, max_similarity

        except Exception as e:
            logger.error(f"Error in semantic deduplication: {e}")
            return False, 0.0

    def _paraphrase_cache_key(self, message: str, bot_id: int = 0) -> str:
        """Generate cache key for paraphrase (P1.2)"""
        import hashlib
        cache_input = f"{message}:{bot_id}"
        msg_hash = hashlib.sha256(cache_input.encode('utf-8')).hexdigest()[:16]
        return f"paraphrase:{msg_hash}"

    def paraphrase_message(self, message: str, llm_client, bot_id: int = 0, max_tokens: int = 200) -> str:
        """
        Mesajı paraphrase et (LLM ile)

        P1.2: Uses Redis cache to avoid repeated LLM calls

        LLM kullanarak aynı anlamdaki mesajı farklı kelimelerle yeniden yazar.

        Args:
            message: Paraphrase edilecek mesaj
            llm_client: LLMClient instance
            bot_id: Bot ID for cache key uniqueness (P1.2)
            max_tokens: Maksimum token sayısı

        Returns:
            Paraphrase edilmiş mesaj
        """
        # P1.2: Check cache first
        if self.redis:
            try:
                cache_key = self._paraphrase_cache_key(message, bot_id)
                cached = self.redis.get(cache_key)
                if cached:
                    logger.debug(f"Paraphrase cache HIT: {message[:30]}...")
                    return cached.decode('utf-8') if isinstance(cached, bytes) else cached
            except Exception as e:
                logger.error(f"Paraphrase cache get error: {e}")

        try:
            prompt = f"""Şu mesajı başka kelimelerle yaz ama anlamı aynı kalsın:

"{message}"

Farklı kelimeler ve farklı cümle yapısı kullan ama aynı fikri anlat.
Samimi ve doğal ol. Sadece yeni versiyonu yaz, başka bir şey yazma."""

            paraphrased = llm_client.generate(
                user_prompt=prompt,
                temperature=1.2,  # Yüksek temperature = daha yaratıcı
                max_tokens=max_tokens
            )

            if paraphrased and paraphrased.strip():
                result = paraphrased.strip()
                logger.debug(f"Paraphrase successful: {len(message)} -> {len(result)} chars")

                # P1.2: Cache the result
                if self.redis:
                    try:
                        cache_key = self._paraphrase_cache_key(message, bot_id)
                        self.redis.setex(cache_key, self.paraphrase_cache_ttl, result)
                        logger.debug(f"Paraphrase cached: {cache_key}")
                    except Exception as e:
                        logger.error(f"Paraphrase cache set error: {e}")

                return result
            else:
                logger.warning("Paraphrase returned empty, using original")
                return message

        except Exception as e:
            logger.error(f"Error in paraphrase: {e}")
            return message  # Fallback: orijinal mesajı döndür


# Convenience function for testing
def test_semantic_dedup():
    """Test semantic deduplication with sample messages"""
    if not SEMANTIC_DEDUP_AVAILABLE:
        print("❌ sentence-transformers not installed")
        return

    dedup = SemanticDeduplicator(similarity_threshold=0.85)

    # Test mesajları
    messages = [
        "BIST bugün yükseldi, güzel bir gün",
        "Borsa bugün arttı, iyi bir gün geçirdik",
        "Dolar düştü, TL güçlendi",
    ]

    new_msg = "Bugün BIST yükseliş gösterdi, harika gün"

    is_dup, similarity = dedup.is_duplicate(new_msg, messages)

    print(f"New message: {new_msg}")
    print(f"Is duplicate: {is_dup}")
    print(f"Max similarity: {similarity:.3f}")
    print(f"Threshold: {dedup.similarity_threshold}")


if __name__ == "__main__":
    # Test module
    logging.basicConfig(level=logging.INFO)
    test_semantic_dedup()
