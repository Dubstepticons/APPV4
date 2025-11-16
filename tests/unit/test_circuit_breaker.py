"""
Unit Tests for Circuit Breaker Pattern

Tests circuit breaker state transitions, failure handling, and recovery logic.

Run with: pytest tests/unit/test_circuit_breaker.py -v
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import List

from core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    circuit_breaker,
    get_registry
)


class ServiceError(Exception):
    """Test exception for simulating service failures."""
    pass


class FlakeyService:
    """Mock service that can be configured to succeed or fail."""

    def __init__(self):
        self.call_count = 0
        self.should_fail = False
        self.failure_count = 0

    def call(self, value: int = 42) -> int:
        """Call service (can be configured to fail)."""
        self.call_count += 1

        if self.should_fail:
            self.failure_count += 1
            raise ServiceError(f"Service failure #{self.failure_count}")

        return value

    def reset(self):
        """Reset counters."""
        self.call_count = 0
        self.failure_count = 0


@pytest.fixture
def service():
    """Create mock service."""
    return FlakeyService()


@pytest.fixture
def breaker():
    """Create circuit breaker with short timeouts for testing."""
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=1,  # 1 second for fast testing
        expected_exception=ServiceError,
        name="test-breaker"
    )


class TestCircuitBreakerBasics:
    """Test basic circuit breaker functionality."""

    def test_initial_state(self, breaker):
        """Circuit breaker should start in CLOSED state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.total_calls == 0

    def test_successful_call(self, breaker, service):
        """Successful calls should pass through."""
        result = breaker.call(service.call, 42)
        assert result == 42
        assert service.call_count == 1
        assert breaker.state == CircuitState.CLOSED
        assert breaker.total_successes == 1

    def test_multiple_successful_calls(self, breaker, service):
        """Multiple successful calls should work."""
        for i in range(10):
            result = breaker.call(service.call, i)
            assert result == i

        assert service.call_count == 10
        assert breaker.total_successes == 10
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerFailureHandling:
    """Test circuit breaker failure detection and transitions."""

    def test_single_failure(self, breaker, service):
        """Single failure should be raised but not open circuit."""
        service.should_fail = True

        with pytest.raises(ServiceError):
            breaker.call(service.call)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1
        assert breaker.total_failures == 1

    def test_threshold_triggers_open(self, breaker, service):
        """Failures exceeding threshold should open circuit."""
        service.should_fail = True

        # Fail 3 times (threshold = 3)
        for i in range(3):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        # Circuit should now be OPEN
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

    def test_open_circuit_rejects_calls(self, breaker, service):
        """OPEN circuit should reject calls without calling service."""
        service.should_fail = True

        # Trigger circuit to open
        for i in range(3):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        assert breaker.state == CircuitState.OPEN

        # Now service is working, but circuit should reject
        service.should_fail = False
        call_count_before = service.call_count

        with pytest.raises(CircuitBreakerError):
            breaker.call(service.call)

        # Service should NOT have been called
        assert service.call_count == call_count_before
        assert breaker.total_rejections == 1

    def test_success_resets_failure_count(self, breaker, service):
        """Successful call should reset failure counter."""
        service.should_fail = True

        # 2 failures (below threshold of 3)
        for i in range(2):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        assert breaker.failure_count == 2
        assert breaker.state == CircuitState.CLOSED

        # Success should reset counter
        service.should_fail = False
        breaker.call(service.call)

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery transitions (OPEN → HALF_OPEN → CLOSED)."""

    def test_recovery_timeout(self, breaker, service):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        service.should_fail = True

        # Open circuit
        for i in range(3):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout (1 second)
        time.sleep(1.1)

        # Service is now working
        service.should_fail = False

        # Next call should test recovery (HALF_OPEN)
        result = breaker.call(service.call, 42)
        assert result == 42

        # Circuit should be CLOSED after successful recovery test
        assert breaker.state == CircuitState.CLOSED

    def test_failed_recovery_reopens_circuit(self, breaker, service):
        """Failed recovery test should reopen circuit."""
        service.should_fail = True

        # Open circuit
        for i in range(3):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(1.1)

        # Service still failing
        with pytest.raises(ServiceError):
            breaker.call(service.call)

        # Circuit should be OPEN again
        assert breaker.state == CircuitState.OPEN

    def test_manual_reset(self, breaker, service):
        """Manual reset should close circuit immediately."""
        service.should_fail = True

        # Open circuit
        for i in range(3):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        assert breaker.state == CircuitState.OPEN

        # Manual reset (without waiting for timeout)
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

        # Should be able to call immediately
        service.should_fail = False
        result = breaker.call(service.call, 100)
        assert result == 100


class TestCircuitBreakerStatistics:
    """Test circuit breaker statistics and monitoring."""

    def test_call_counters(self, breaker, service):
        """Test that all call types are counted correctly."""
        # 3 successes
        for i in range(3):
            breaker.call(service.call)

        # 2 failures
        service.should_fail = True
        for i in range(2):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        # Open circuit (3rd failure)
        with pytest.raises(ServiceError):
            breaker.call(service.call)

        # 1 rejection
        with pytest.raises(CircuitBreakerError):
            breaker.call(service.call)

        stats = breaker.get_stats()
        assert stats["total_calls"] == 7  # All calls including rejection
        assert stats["total_successes"] == 3
        assert stats["total_failures"] == 3
        assert stats["total_rejections"] == 1

    def test_get_stats_format(self, breaker):
        """Test get_stats returns expected format."""
        stats = breaker.get_stats()

        assert "name" in stats
        assert "state" in stats
        assert "failure_count" in stats
        assert "total_calls" in stats
        assert "failure_threshold" in stats
        assert "recovery_timeout" in stats
        assert "time_until_retry" in stats

        assert stats["name"] == "test-breaker"
        assert stats["state"] == "closed"
        assert stats["failure_threshold"] == 3

    def test_time_until_retry(self, breaker, service):
        """Test time_until_retry calculation."""
        service.should_fail = True

        # Open circuit
        for i in range(3):
            with pytest.raises(ServiceError):
                breaker.call(service.call)

        stats = breaker.get_stats()
        time_until_retry = stats["time_until_retry"]

        # Should be close to recovery_timeout (1 second)
        assert 0.5 <= time_until_retry <= 1.0

        # Wait half the timeout
        time.sleep(0.5)

        stats = breaker.get_stats()
        time_until_retry = stats["time_until_retry"]

        # Should be roughly half now
        assert 0.0 <= time_until_retry <= 0.6


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator."""

    def test_decorator_basic(self):
        """Test basic decorator usage."""

        @circuit_breaker(failure_threshold=2, recovery_timeout=1, name="decorated-test")
        def flaky_function(should_fail: bool = False):
            if should_fail:
                raise ServiceError("Failure")
            return "success"

        # Should work normally
        result = flaky_function(should_fail=False)
        assert result == "success"

        # Fail twice to open circuit
        with pytest.raises(ServiceError):
            flaky_function(should_fail=True)
        with pytest.raises(ServiceError):
            flaky_function(should_fail=True)

        # Circuit should be open
        with pytest.raises(CircuitBreakerError):
            flaky_function(should_fail=False)

    def test_decorator_attaches_breaker(self):
        """Test that decorator attaches circuit breaker instance."""

        @circuit_breaker(failure_threshold=5)
        def test_func():
            return 42

        # Breaker should be accessible
        assert hasattr(test_func, 'circuit_breaker')
        assert isinstance(test_func.circuit_breaker, CircuitBreaker)
        assert test_func.circuit_breaker.failure_threshold == 5


class TestCircuitBreakerRegistry:
    """Test global circuit breaker registry."""

    def test_register_breaker(self):
        """Test registering circuit breakers."""
        registry = CircuitBreakerRegistry()

        breaker1 = CircuitBreaker(name="breaker-1")
        breaker2 = CircuitBreaker(name="breaker-2")

        registry.register(breaker1)
        registry.register(breaker2)

        assert registry.get("breaker-1") == breaker1
        assert registry.get("breaker-2") == breaker2

    def test_get_all_stats(self):
        """Test getting stats for all breakers."""
        registry = CircuitBreakerRegistry()

        breaker1 = CircuitBreaker(name="breaker-1")
        breaker2 = CircuitBreaker(name="breaker-2")

        registry.register(breaker1)
        registry.register(breaker2)

        all_stats = registry.get_all_stats()

        assert "breaker-1" in all_stats
        assert "breaker-2" in all_stats
        assert all_stats["breaker-1"]["state"] == "closed"

    def test_reset_all(self, service):
        """Test resetting all breakers."""
        registry = CircuitBreakerRegistry()

        breaker1 = CircuitBreaker(failure_threshold=2, name="breaker-1", expected_exception=ServiceError)
        breaker2 = CircuitBreaker(failure_threshold=2, name="breaker-2", expected_exception=ServiceError)

        registry.register(breaker1)
        registry.register(breaker2)

        # Open both circuits
        service.should_fail = True
        for breaker in [breaker1, breaker2]:
            for i in range(2):
                with pytest.raises(ServiceError):
                    breaker.call(service.call)

        assert breaker1.state == CircuitState.OPEN
        assert breaker2.state == CircuitState.OPEN

        # Reset all
        registry.reset_all()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED

    def test_global_registry(self):
        """Test global registry singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2  # Same instance


class TestCircuitBreakerEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_threshold(self):
        """Test circuit breaker with threshold of 0 (immediately opens)."""
        breaker = CircuitBreaker(failure_threshold=0, expected_exception=ServiceError)
        service = FlakeyService()
        service.should_fail = True

        # First failure should open circuit
        with pytest.raises(ServiceError):
            breaker.call(service.call)

        # Should be open immediately
        assert breaker.state == CircuitState.OPEN

    def test_different_exception_types(self):
        """Test that only expected exceptions count as failures."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception=ServiceError  # Only catch ServiceError
        )

        def raises_value_error():
            raise ValueError("Wrong exception type")

        # ValueError should NOT be caught (will propagate)
        with pytest.raises(ValueError):
            breaker.call(raises_value_error)

        # Should NOT count as failure
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_concurrent_state_changes(self, breaker, service):
        """Test that state changes are thread-safe."""
        import threading

        results = []
        errors = []

        def worker():
            try:
                for i in range(10):
                    breaker.call(service.call)
                    results.append("success")
            except (ServiceError, CircuitBreakerError) as e:
                errors.append(str(e))

        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have recorded multiple successes
        assert len(results) > 0
        assert breaker.total_successes > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
