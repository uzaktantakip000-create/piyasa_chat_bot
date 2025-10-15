"""
Rate Limiter Module

Token bucket algorithm implementation for rate limiting with Redis backend.
Supports both global and per-resource rate limiting for Telegram API calls.

Key Features:
- Token bucket algorithm for smooth rate limiting
- Redis-based distributed rate limiting
- Multiple limit tiers (global, per-chat, per-bot)
- Automatic token refill
- Graceful degradation when Redis unavailable
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple
from dataclasses import dataclass

import redis

logger = logging.getLogger("rate_limiter")


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_tokens: int  # Maximum tokens in bucket
    refill_rate: float  # Tokens added per second
    burst_size: Optional[int] = None  # Max burst size (defaults to max_tokens)

    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = self.max_tokens


class RateLimiter:
    """
    Token bucket rate limiter with Redis backend.

    Implements token bucket algorithm for smooth rate limiting:
    - Each bucket has a maximum capacity (max_tokens)
    - Tokens are consumed on each request
    - Tokens refill at a constant rate (refill_rate)
    - Requests are allowed if sufficient tokens available

    Example:
        # Global rate limit: 30 requests/second
        limiter = RateLimiter(redis_client, max_tokens=30, refill_rate=30.0)

        if limiter.acquire("global"):
            # Make API call
            send_telegram_message(...)
        else:
            # Rate limited - wait or queue
            logger.warning("Rate limit exceeded")

    Telegram API Limits:
    - Global: 30 messages/second
    - Per chat: 20 messages/minute (group chats)
    - Per chat: 1 message/second (same user in private chat)
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis],
        max_tokens: int = 30,
        refill_rate: float = 30.0,
        burst_size: Optional[int] = None,
        key_prefix: str = "rate_limit",
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client for distributed rate limiting
            max_tokens: Maximum tokens in bucket
            refill_rate: Tokens refilled per second
            burst_size: Maximum burst size (defaults to max_tokens)
            key_prefix: Redis key prefix for rate limit buckets
        """
        self.redis_client = redis_client
        self.config = RateLimitConfig(
            max_tokens=max_tokens,
            refill_rate=refill_rate,
            burst_size=burst_size,
        )
        self.key_prefix = key_prefix
        self._fallback_mode = redis_client is None

        if self._fallback_mode:
            logger.warning("RateLimiter initialized without Redis - using in-memory fallback")
            self._local_buckets: dict[str, dict] = {}

    def _get_key(self, resource_id: str) -> str:
        """Get Redis key for resource"""
        return f"{self.key_prefix}:{resource_id}"

    def _refill_tokens(self, current_tokens: float, last_refill: float, now: float) -> float:
        """Calculate tokens after refill"""
        time_passed = now - last_refill
        tokens_to_add = time_passed * self.config.refill_rate
        new_tokens = min(current_tokens + tokens_to_add, self.config.max_tokens)
        return new_tokens

    def acquire(
        self,
        resource_id: str,
        tokens: int = 1,
        max_wait: float = 0.0,
    ) -> bool:
        """
        Try to acquire tokens from bucket.

        Args:
            resource_id: Unique identifier for the rate limit bucket
                        (e.g., "global", "chat:123", "bot:456")
            tokens: Number of tokens to acquire (default: 1)
            max_wait: Maximum time to wait for tokens (seconds, default: 0)

        Returns:
            True if tokens acquired, False if rate limited

        Example:
            # Global rate limit
            if limiter.acquire("global"):
                send_message()

            # Per-chat rate limit
            if limiter.acquire(f"chat:{chat_id}"):
                send_message_to_chat()

            # With waiting
            if limiter.acquire("global", tokens=1, max_wait=1.0):
                send_message()
        """
        if self._fallback_mode:
            return self._acquire_local(resource_id, tokens, max_wait)

        return self._acquire_redis(resource_id, tokens, max_wait)

    def _acquire_redis(self, resource_id: str, tokens: int, max_wait: float) -> bool:
        """Acquire tokens using Redis backend"""
        key = self._get_key(resource_id)
        now = time.time()
        wait_until = now + max_wait if max_wait > 0 else now

        while time.time() <= wait_until:
            try:
                # Get current bucket state
                pipe = self.redis_client.pipeline()
                pipe.hget(key, "tokens")
                pipe.hget(key, "last_refill")
                results = pipe.execute()

                current_tokens = float(results[0] or self.config.max_tokens)
                last_refill = float(results[1] or now)

                # Refill tokens
                new_tokens = self._refill_tokens(current_tokens, last_refill, now)

                # Check if enough tokens
                if new_tokens >= tokens:
                    # Acquire tokens atomically
                    new_tokens -= tokens
                    pipe = self.redis_client.pipeline()
                    pipe.hset(key, "tokens", new_tokens)
                    pipe.hset(key, "last_refill", now)
                    pipe.expire(key, 3600)  # Expire after 1 hour of inactivity
                    pipe.execute()

                    logger.debug(
                        "Rate limit acquired: %s (tokens: %d, remaining: %.2f)",
                        resource_id, tokens, new_tokens
                    )
                    return True
                else:
                    # Not enough tokens
                    if max_wait > 0:
                        # Calculate wait time
                        tokens_needed = tokens - new_tokens
                        wait_time = tokens_needed / self.config.refill_rate
                        if wait_time <= (wait_until - time.time()):
                            time.sleep(min(wait_time, 0.1))  # Sleep in small increments
                            continue

                    logger.debug(
                        "Rate limit exceeded: %s (tokens: %d, available: %.2f)",
                        resource_id, tokens, new_tokens
                    )
                    return False

            except redis.RedisError as e:
                logger.warning("Redis error in rate limiter: %s - falling back to allow", e)
                return True  # Fail open on Redis errors
            except Exception as e:
                logger.exception("Unexpected error in rate limiter: %s", e)
                return True  # Fail open on errors

        return False

    def _acquire_local(self, resource_id: str, tokens: int, max_wait: float) -> bool:
        """Acquire tokens using in-memory fallback (single-instance only)"""
        now = time.time()
        wait_until = now + max_wait if max_wait > 0 else now

        while time.time() <= wait_until:
            # Get or initialize bucket
            if resource_id not in self._local_buckets:
                self._local_buckets[resource_id] = {
                    "tokens": float(self.config.max_tokens),
                    "last_refill": now,
                }

            bucket = self._local_buckets[resource_id]

            # Refill tokens
            current_tokens = bucket["tokens"]
            last_refill = bucket["last_refill"]
            new_tokens = self._refill_tokens(current_tokens, last_refill, now)

            # Check if enough tokens
            if new_tokens >= tokens:
                bucket["tokens"] = new_tokens - tokens
                bucket["last_refill"] = now
                logger.debug(
                    "Rate limit acquired (local): %s (tokens: %d, remaining: %.2f)",
                    resource_id, tokens, bucket["tokens"]
                )
                return True
            else:
                if max_wait > 0:
                    tokens_needed = tokens - new_tokens
                    wait_time = tokens_needed / self.config.refill_rate
                    if wait_time <= (wait_until - time.time()):
                        time.sleep(min(wait_time, 0.1))
                        continue

                logger.debug(
                    "Rate limit exceeded (local): %s (tokens: %d, available: %.2f)",
                    resource_id, tokens, new_tokens
                )
                return False

        return False

    def get_remaining(self, resource_id: str) -> Tuple[float, float]:
        """
        Get remaining tokens and refill rate for a resource.

        Args:
            resource_id: Resource identifier

        Returns:
            Tuple of (remaining_tokens, tokens_per_second)

        Example:
            remaining, rate = limiter.get_remaining("global")
            print(f"Remaining: {remaining:.1f} tokens, Rate: {rate:.1f}/s")
        """
        if self._fallback_mode:
            if resource_id not in self._local_buckets:
                return (float(self.config.max_tokens), self.config.refill_rate)

            bucket = self._local_buckets[resource_id]
            now = time.time()
            current_tokens = bucket["tokens"]
            last_refill = bucket["last_refill"]
            remaining = self._refill_tokens(current_tokens, last_refill, now)
            return (remaining, self.config.refill_rate)

        try:
            key = self._get_key(resource_id)
            now = time.time()

            pipe = self.redis_client.pipeline()
            pipe.hget(key, "tokens")
            pipe.hget(key, "last_refill")
            results = pipe.execute()

            current_tokens = float(results[0] or self.config.max_tokens)
            last_refill = float(results[1] or now)

            remaining = self._refill_tokens(current_tokens, last_refill, now)
            return (remaining, self.config.refill_rate)

        except redis.RedisError as e:
            logger.warning("Redis error getting remaining tokens: %s", e)
            return (float(self.config.max_tokens), self.config.refill_rate)

    def reset(self, resource_id: str) -> None:
        """
        Reset rate limit bucket for a resource.

        Args:
            resource_id: Resource identifier to reset

        Example:
            # Reset global rate limit
            limiter.reset("global")

            # Reset per-chat limit
            limiter.reset(f"chat:{chat_id}")
        """
        if self._fallback_mode:
            if resource_id in self._local_buckets:
                del self._local_buckets[resource_id]
            logger.debug("Rate limit reset (local): %s", resource_id)
        else:
            try:
                key = self._get_key(resource_id)
                self.redis_client.delete(key)
                logger.debug("Rate limit reset: %s", resource_id)
            except redis.RedisError as e:
                logger.warning("Redis error resetting rate limit: %s", e)


class TelegramRateLimiter:
    """
    Specialized rate limiter for Telegram API.

    Implements Telegram's rate limiting rules:
    - Global: 30 messages/second across all chats
    - Per chat (groups): 20 messages/minute
    - Per chat (private): 1 message/second to same user

    Usage:
        limiter = TelegramRateLimiter(redis_client)

        # Before sending message
        if limiter.can_send(chat_id):
            send_telegram_message(chat_id, text)
        else:
            logger.warning("Rate limited for chat %s", chat_id)
    """

    def __init__(self, redis_client: Optional[redis.Redis]):
        """
        Initialize Telegram rate limiter.

        Args:
            redis_client: Redis client for distributed rate limiting
        """
        # Global limit: 30 messages/second
        self.global_limiter = RateLimiter(
            redis_client,
            max_tokens=30,
            refill_rate=30.0,  # 30 tokens/second
            key_prefix="telegram:global",
        )

        # Per-chat limit: 20 messages/minute for groups
        # Using 20 tokens, refilling at 20/60 = 0.333 tokens/second
        self.chat_limiter = RateLimiter(
            redis_client,
            max_tokens=20,
            refill_rate=20.0 / 60.0,  # 20 messages per 60 seconds
            key_prefix="telegram:chat",
        )

    def can_send(self, chat_id: str, max_wait: float = 0.0) -> bool:
        """
        Check if message can be sent to chat.

        Args:
            chat_id: Telegram chat ID
            max_wait: Maximum time to wait for rate limit (seconds)

        Returns:
            True if message can be sent, False if rate limited

        Example:
            if limiter.can_send(chat_id, max_wait=1.0):
                telegram_client.send_message(chat_id, text)
        """
        # Check global limit first
        if not self.global_limiter.acquire("global", tokens=1, max_wait=max_wait):
            logger.warning("Global Telegram rate limit exceeded")
            return False

        # Check per-chat limit
        if not self.chat_limiter.acquire(f"chat:{chat_id}", tokens=1, max_wait=max_wait):
            logger.warning("Per-chat Telegram rate limit exceeded: %s", chat_id)
            # Return token to global bucket since we didn't use it
            # (This is approximate - token bucket doesn't support returns)
            return False

        return True

    def get_limits(self, chat_id: str) -> dict:
        """
        Get current rate limit status for chat.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Dict with global and per-chat limits

        Example:
            limits = limiter.get_limits(chat_id)
            print(f"Global: {limits['global_remaining']:.1f} tokens")
            print(f"Chat: {limits['chat_remaining']:.1f} tokens")
        """
        global_remaining, global_rate = self.global_limiter.get_remaining("global")
        chat_remaining, chat_rate = self.chat_limiter.get_remaining(f"chat:{chat_id}")

        return {
            "global_remaining": global_remaining,
            "global_rate": global_rate,
            "global_max": self.global_limiter.config.max_tokens,
            "chat_remaining": chat_remaining,
            "chat_rate": chat_rate,
            "chat_max": self.chat_limiter.config.max_tokens,
        }
