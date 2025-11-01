"""
Retry policies with exponential backoff

Provides retry logic for transient failures (network issues, temporary API errors).
"""

import time
import logging
import random
from typing import Callable, Any, Type, Tuple, Optional
from functools import wraps

logger = logging.getLogger(__name__)


def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for exponential backoff retry logic

    Usage:
        @exponential_backoff(max_retries=5, base_delay=1.0)
        def call_api():
            response = requests.get("https://api.example.com")
            response.raise_for_status()
            return response.json()

    Args:
        max_retries: Maximum number of retries
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to avoid thundering herd
        exceptions: Tuple of exceptions to retry on

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Max retries reached
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    # Add jitter (random 0-25% variation)
                    if jitter:
                        delay *= (1 + random.uniform(-0.25, 0.25))

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s: {e}"
                    )

                    time.sleep(delay)

            # Should never reach here, but for type safety
            raise last_exception

        return wrapper
    return decorator


class RetryPolicy:
    """
    Configurable retry policy class (alternative to decorator)

    Usage:
        retry_policy = RetryPolicy(max_retries=5, base_delay=1.0)
        result = retry_policy.execute(risky_function, arg1, arg2, kwarg1=value)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.exceptions as e:
                last_exception = e

                if attempt == self.max_retries:
                    logger.error(
                        f"Max retries ({self.max_retries}) exceeded for {func.__name__}: {e}"
                    )
                    raise

                # Calculate delay
                delay = min(
                    self.base_delay * (self.exponential_base ** attempt),
                    self.max_delay
                )

                # Add jitter
                if self.jitter:
                    delay *= (1 + random.uniform(-0.25, 0.25))

                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} for {func.__name__} "
                    f"after {delay:.2f}s: {e}"
                )

                time.sleep(delay)

        raise last_exception


# Predefined retry policies for common scenarios

telegram_retry_policy = RetryPolicy(
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,)  # Will be refined to specific HTTP errors
)

llm_retry_policy = RetryPolicy(
    max_retries=3,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    exceptions=(Exception,)
)
