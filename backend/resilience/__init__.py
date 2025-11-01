"""
Resilience patterns for production-grade fault tolerance

This module provides circuit breakers, retry policies, and rate limiting
for external API calls (Telegram, LLM providers).
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState
from .retry_policy import RetryPolicy, exponential_backoff

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitState",
    "RetryPolicy",
    "exponential_backoff",
]
