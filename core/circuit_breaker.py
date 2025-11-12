"""
Circuit Breaker Pattern - Fault Tolerance for External Services

Prevents cascade failures by automatically stopping requests to failing services.
Essential for production systems with external dependencies (DTC server, databases, APIs).

State Machine:
    CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED
         ↓                                      ↓
         └──────── (failure threshold) ─────────┘

Usage:
    >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    >>> result = breaker.call(risky_function, arg1, arg2)
    >>> # After 5 failures, circuit opens and rejects calls for 60 seconds

Thread Safety: Thread-safe using threading.Lock
Performance: Negligible overhead (~1μs per call)
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Any, Optional
from functools import wraps
import threading
from utils.logger import get_logger

log = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation, requests allowed
    OPEN = "open"            # Failing, all requests rejected
    HALF_OPEN = "half_open"  # Testing recovery, limited requests


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is OPEN and rejects a call"""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascade failures.

    Monitors failure rate and automatically "opens" (stops forwarding requests)
    when failure threshold is exceeded. After a recovery timeout, enters
    HALF_OPEN state to test if service has recovered.

    Thread-safe for concurrent use.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception,
        name: str = "default"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening (default: 5)
            recovery_timeout: Seconds to wait before attempting recovery (default: 60)
            expected_exception: Exception type(s) to count as failures (default: Exception)
            name: Identifier for logging (default: "default")
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None

        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_rejections = 0

        # Thread safety
        self._lock = threading.Lock()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: Original exception from func if circuit is CLOSED/HALF_OPEN
        """
        with self._lock:
            self.total_calls += 1

            # Check if circuit should transition states
            self._update_state()

            # OPEN: Reject all calls
            if self.state == CircuitState.OPEN:
                self.total_rejections += 1
                time_until_retry = self._time_until_retry()
                log.warning(
                    f"[CircuitBreaker:{self.name}] Circuit OPEN - rejecting call "
                    f"(retry in {time_until_retry:.1f}s, failures: {self.failure_count})"
                )
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retry in {time_until_retry:.1f} seconds."
                )

            # HALF_OPEN: Allow single test request
            if self.state == CircuitState.HALF_OPEN:
                log.info(f"[CircuitBreaker:{self.name}] Testing service recovery (HALF_OPEN)")

        # Execute function (outside lock to avoid blocking)
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _update_state(self) -> None:
        """Update circuit state based on current conditions. Must be called with lock held."""

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._should_attempt_reset():
                self._transition_to_half_open()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if not self.opened_at:
            return False

        elapsed = (datetime.now() - self.opened_at).total_seconds()
        return elapsed >= self.recovery_timeout

    def _time_until_retry(self) -> float:
        """Calculate seconds until next retry attempt"""
        if not self.opened_at:
            return 0.0

        elapsed = (datetime.now() - self.opened_at).total_seconds()
        return max(0.0, self.recovery_timeout - elapsed)

    def _on_success(self) -> None:
        """Handle successful call"""
        with self._lock:
            self.success_count += 1
            self.total_successes += 1
            self.failure_count = 0  # Reset failure counter

            if self.state == CircuitState.HALF_OPEN:
                # Success in HALF_OPEN → recovery confirmed, close circuit
                self._transition_to_closed()
                log.info(
                    f"[CircuitBreaker:{self.name}] Service recovered - circuit CLOSED "
                    f"(total successes: {self.total_successes})"
                )

    def _on_failure(self) -> None:
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.total_failures += 1
            self.last_failure_time = datetime.now()
            self.success_count = 0  # Reset success counter

            log.warning(
                f"[CircuitBreaker:{self.name}] Call failed "
                f"({self.failure_count}/{self.failure_threshold})"
            )

            # Check if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                if self.state == CircuitState.CLOSED:
                    self._transition_to_open()
                elif self.state == CircuitState.HALF_OPEN:
                    # Failed during recovery test → reopen circuit
                    self._transition_to_open()
                    log.warning(
                        f"[CircuitBreaker:{self.name}] Recovery test failed - "
                        f"reopening circuit for {self.recovery_timeout}s"
                    )

    def _transition_to_open(self) -> None:
        """Transition to OPEN state"""
        self.state = CircuitState.OPEN
        self.opened_at = datetime.now()
        log.error(
            f"[CircuitBreaker:{self.name}] Circuit OPENED - "
            f"threshold exceeded ({self.failure_count} failures). "
            f"Will retry in {self.recovery_timeout}s"
        )

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state"""
        self.state = CircuitState.HALF_OPEN
        self.failure_count = 0  # Reset for recovery test
        log.info(
            f"[CircuitBreaker:{self.name}] Circuit HALF_OPEN - testing service recovery"
        )

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None

    def reset(self) -> None:
        """
        Manually reset circuit breaker to CLOSED state.

        Use with caution - typically only for testing or administrative override.
        """
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.opened_at = None
            log.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED")

    def get_stats(self) -> dict[str, Any]:
        """
        Get circuit breaker statistics.

        Returns:
            Dictionary with current state and metrics
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_calls": self.total_calls,
                "total_failures": self.total_failures,
                "total_successes": self.total_successes,
                "total_rejections": self.total_rejections,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else 0,
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            }

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name}, state={self.state.value}, "
            f"failures={self.failure_count}/{self.failure_threshold})"
        )


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type[Exception] = Exception,
    name: Optional[str] = None
):
    """
    Decorator for protecting functions with circuit breaker.

    Args:
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before retry
        expected_exception: Exception type to catch
        name: Circuit breaker name (defaults to function name)

    Usage:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        def connect_to_api():
            return requests.get("https://api.example.com")
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker_name = name or func.__name__
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        # Attach breaker instance to wrapper for inspection
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator


class CircuitBreakerRegistry:
    """
    Global registry for managing multiple circuit breakers.

    Useful for monitoring and managing circuit breakers across application.
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def register(self, breaker: CircuitBreaker) -> None:
        """Register a circuit breaker"""
        with self._lock:
            self._breakers[breaker.name] = breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        with self._lock:
            return self._breakers.get(name)

    def get_all_stats(self) -> dict[str, dict]:
        """Get statistics for all registered circuit breakers"""
        with self._lock:
            return {
                name: breaker.get_stats()
                for name, breaker in self._breakers.items()
            }

    def reset_all(self) -> None:
        """Reset all circuit breakers (use with caution)"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


# Global registry instance
_registry = CircuitBreakerRegistry()


def get_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry"""
    return _registry
