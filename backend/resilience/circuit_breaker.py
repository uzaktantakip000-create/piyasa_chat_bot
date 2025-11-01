"""
Circuit Breaker pattern implementation for API fault tolerance

The circuit breaker prevents cascading failures by monitoring API call success/failure
rates and "opening" the circuit (blocking calls) when failures exceed a threshold.

States:
- CLOSED: Normal operation, calls pass through
- OPEN: Too many failures, calls blocked (fail fast)
- HALF_OPEN: Testing if service recovered, limited calls allowed

Reference: Martin Fowler's Circuit Breaker pattern
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"           # Normal operation
    OPEN = "open"               # Failures detected, blocking calls
    HALF_OPEN = "half_open"     # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is OPEN"""
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker OPEN for '{service_name}'. "
            f"Retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker for external API calls

    Usage:
        breaker = CircuitBreaker("telegram_api", failure_threshold=5, timeout=60)

        try:
            result = breaker.call(telegram_api.send_message, chat_id, text)
        except CircuitBreakerError as e:
            logger.warning(f"Circuit open: {e}")
            # Handle gracefully (skip, queue, fallback)
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker

        Args:
            service_name: Name of the service (for logging/monitoring)
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before transitioning to HALF_OPEN
            half_open_max_calls: Max calls to allow in HALF_OPEN state
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

        # State
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

        # Thread safety
        self._lock = Lock()

        logger.info(
            f"CircuitBreaker initialized for '{service_name}' "
            f"(threshold={failure_threshold}, timeout={timeout}s)"
        )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Function to call
            *args, **kwargs: Arguments for the function

        Returns:
            Result from the function

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: If function raises (and circuit transitions to OPEN if threshold reached)
        """
        with self._lock:
            self._check_state_transition()

            if self.state == CircuitState.OPEN:
                retry_after = self._time_until_half_open()
                raise CircuitBreakerError(self.service_name, retry_after)

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    # Max half-open calls reached, wait for results
                    raise CircuitBreakerError(self.service_name, self.timeout)
                self.half_open_calls += 1

        # Execute function (outside lock to avoid blocking other threads)
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _check_state_transition(self):
        """Check if state should transition (OPEN -> HALF_OPEN)"""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.timeout:
                logger.info(
                    f"CircuitBreaker '{self.service_name}': "
                    f"OPEN -> HALF_OPEN (timeout expired)"
                )
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self.failure_count = 0

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    # Service recovered, close circuit
                    logger.info(
                        f"CircuitBreaker '{self.service_name}': "
                        f"HALF_OPEN -> CLOSED (service recovered)"
                    )
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    self.half_open_calls = 0
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                if self.failure_count > 0:
                    self.failure_count = 0

    def _on_failure(self, exception: Exception):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Service still failing, reopen circuit
                logger.warning(
                    f"CircuitBreaker '{self.service_name}': "
                    f"HALF_OPEN -> OPEN (failure during test: {exception})"
                )
                self.state = CircuitState.OPEN
                self.success_count = 0
                self.half_open_calls = 0

            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    # Threshold reached, open circuit
                    logger.error(
                        f"CircuitBreaker '{self.service_name}': "
                        f"CLOSED -> OPEN (failures={self.failure_count}/{self.failure_threshold})"
                    )
                    self.state = CircuitState.OPEN

    def _time_until_half_open(self) -> float:
        """Calculate seconds until HALF_OPEN transition"""
        if not self.last_failure_time:
            return 0.0
        elapsed = time.time() - self.last_failure_time
        return max(0.0, self.timeout - elapsed)

    def get_state(self) -> dict:
        """Get current circuit breaker state (for monitoring)"""
        with self._lock:
            return {
                "service": self.service_name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "half_open_calls": self.half_open_calls,
                "last_failure_time": datetime.fromtimestamp(
                    self.last_failure_time, tz=timezone.utc
                ).isoformat() if self.last_failure_time else None,
                "retry_after": self._time_until_half_open() if self.state == CircuitState.OPEN else None
            }

    def reset(self):
        """Manually reset circuit breaker (for testing/admin)"""
        with self._lock:
            logger.info(f"CircuitBreaker '{self.service_name}': Manual RESET")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            self.last_failure_time = None
