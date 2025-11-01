"""
Circuit Breaker pattern tests

Tests circuit breaker functionality for Telegram and LLM APIs.
"""

import pytest
import time
from backend.resilience import CircuitBreaker, CircuitBreakerError, CircuitState


def test_circuit_breaker_closed_state():
    """Test circuit breaker starts in CLOSED state"""
    breaker = CircuitBreaker("test_service", failure_threshold=3, timeout=5)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_successful_call():
    """Test successful call keeps circuit CLOSED"""
    breaker = CircuitBreaker("test_service", failure_threshold=3, timeout=5)

    def successful_func():
        return "success"

    result = breaker.call(successful_func)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_opens_on_threshold():
    """Test circuit opens after reaching failure threshold"""
    breaker = CircuitBreaker("test_service", failure_threshold=3, timeout=5)

    def failing_func():
        raise Exception("Test failure")

    # Fail 3 times to reach threshold
    for _ in range(3):
        try:
            breaker.call(failing_func)
        except Exception:
            pass

    # Circuit should be OPEN now
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


def test_circuit_breaker_blocks_when_open():
    """Test circuit breaker blocks calls when OPEN"""
    breaker = CircuitBreaker("test_service", failure_threshold=2, timeout=5)

    def failing_func():
        raise Exception("Test failure")

    # Open the circuit
    for _ in range(2):
        try:
            breaker.call(failing_func)
        except Exception:
            pass

    assert breaker.state == CircuitState.OPEN

    # Attempt should be blocked
    with pytest.raises(CircuitBreakerError) as exc_info:
        breaker.call(lambda: "success")

    assert "Circuit breaker OPEN" in str(exc_info.value)
    assert exc_info.value.service_name == "test_service"


def test_circuit_breaker_transitions_to_half_open():
    """Test circuit transitions to HALF_OPEN after timeout"""
    breaker = CircuitBreaker("test_service", failure_threshold=2, timeout=1)

    def failing_func():
        raise Exception("Test failure")

    # Open the circuit
    for _ in range(2):
        try:
            breaker.call(failing_func)
        except Exception:
            pass

    assert breaker.state == CircuitState.OPEN

    # Wait for timeout
    time.sleep(1.5)

    # Check state transition (internal method)
    breaker._check_state_transition()
    assert breaker.state == CircuitState.HALF_OPEN


def test_circuit_breaker_half_open_to_closed():
    """Test successful calls in HALF_OPEN state close circuit"""
    breaker = CircuitBreaker("test_service", failure_threshold=2, timeout=1, half_open_max_calls=2)

    def failing_func():
        raise Exception("Test failure")

    def successful_func():
        return "success"

    # Open the circuit
    for _ in range(2):
        try:
            breaker.call(failing_func)
        except Exception:
            pass

    assert breaker.state == CircuitState.OPEN

    # Wait for timeout
    time.sleep(1.5)
    breaker._check_state_transition()
    assert breaker.state == CircuitState.HALF_OPEN

    # Successful calls should close circuit
    breaker.call(successful_func)
    breaker.call(successful_func)

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_half_open_to_open():
    """Test failure in HALF_OPEN state reopens circuit"""
    breaker = CircuitBreaker("test_service", failure_threshold=2, timeout=1)

    def failing_func():
        raise Exception("Test failure")

    # Open the circuit
    for _ in range(2):
        try:
            breaker.call(failing_func)
        except Exception:
            pass

    assert breaker.state == CircuitState.OPEN

    # Wait for timeout
    time.sleep(1.5)
    breaker._check_state_transition()
    assert breaker.state == CircuitState.HALF_OPEN

    # Failure should reopen circuit
    try:
        breaker.call(failing_func)
    except Exception:
        pass

    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_get_state():
    """Test get_state returns correct circuit state"""
    breaker = CircuitBreaker("test_service", failure_threshold=2, timeout=60)

    state = breaker.get_state()
    assert state["service"] == "test_service"
    assert state["state"] == "closed"
    assert state["failure_count"] == 0
    assert state["last_failure_time"] is None
    assert state["retry_after"] is None


def test_circuit_breaker_reset():
    """Test manual circuit breaker reset"""
    breaker = CircuitBreaker("test_service", failure_threshold=2, timeout=5)

    def failing_func():
        raise Exception("Test failure")

    # Open the circuit
    for _ in range(2):
        try:
            breaker.call(failing_func)
        except Exception:
            pass

    assert breaker.state == CircuitState.OPEN

    # Manual reset
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.last_failure_time is None


def test_circuit_breaker_success_resets_failure_count():
    """Test successful call resets failure count in CLOSED state"""
    breaker = CircuitBreaker("test_service", failure_threshold=3, timeout=5)

    def failing_func():
        raise Exception("Test failure")

    def successful_func():
        return "success"

    # Fail once
    try:
        breaker.call(failing_func)
    except Exception:
        pass

    assert breaker.failure_count == 1

    # Success should reset count
    breaker.call(successful_func)
    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED
