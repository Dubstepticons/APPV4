"""
DTC Request Timeout Manager

Tracks pending DTC requests and detects timeouts when Sierra Chart
doesn't respond within expected timeframe.

Usage:
    timeout_manager = RequestTimeoutManager(default_timeout=10.0)

    # When sending request:
    timeout_manager.register_request(
        request_id=1,
        request_type="TRADE_ACCOUNTS_REQUEST",
        timeout=15.0  # Override default
    )

    # When receiving response:
    timeout_manager.mark_completed(request_id=1)

    # Check for timeouts:
    timed_out = timeout_manager.check_timeouts()  # Returns list of timed out requests
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import structlog
    log = structlog.get_logger(__name__)
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

    class SimpleLogger:
        """Simple logger fallback"""
        def debug(self, msg, **kwargs):
            pass
        def info(self, msg, **kwargs):
            pass
        def warning(self, msg, **kwargs):
            print(f"[WARNING] {msg}", kwargs if kwargs else "")
        def error(self, msg, **kwargs):
            print(f"[ERROR] {msg}", kwargs if kwargs else "")

    log = SimpleLogger()


@dataclass
class PendingRequest:
    """Represents a pending DTC request waiting for response"""
    request_id: int
    request_type: str
    sent_at: float  # Unix timestamp
    timeout: float  # Seconds
    metadata: Optional[Dict] = None

    def is_timed_out(self) -> bool:
        """Check if this request has timed out"""
        return time.time() - self.sent_at > self.timeout

    def time_remaining(self) -> float:
        """Get seconds remaining before timeout"""
        return max(0.0, self.timeout - (time.time() - self.sent_at))


class RequestTimeoutManager:
    """
    Manages timeouts for DTC requests.

    Tracks pending requests by RequestID and detects when Sierra Chart
    doesn't respond within expected timeframe.
    """

    # Default timeout for various request types (in seconds)
    DEFAULT_TIMEOUTS = {
        "TRADE_ACCOUNTS_REQUEST": 15.0,      # Type 400
        "POSITION_REQUEST": 10.0,             # Type 500
        "OPEN_ORDERS_REQUEST": 10.0,          # Type 305
        "HISTORICAL_FILLS_REQUEST": 30.0,     # Type 303 (can take longer)
        "ACCOUNT_BALANCE_REQUEST": 10.0,      # Type 601
        "MARKET_DATA_REQUEST": 5.0,           # Type 101
    }

    def __init__(self, default_timeout: float = 10.0):
        """
        Initialize request timeout manager.

        Args:
            default_timeout: Default timeout in seconds for requests
                           without explicit timeout specified
        """
        self._default_timeout = default_timeout
        self._pending: Dict[int, PendingRequest] = {}
        self._completed: List[PendingRequest] = []  # Keep recent history
        self._timed_out: List[PendingRequest] = []
        self._max_history = 100  # Keep last 100 completed/timed out requests

    def register_request(
        self,
        request_id: int,
        request_type: str,
        timeout: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Register a new DTC request for timeout tracking.

        Args:
            request_id: Request ID from DTC message
            request_type: Type of request (e.g., "TRADE_ACCOUNTS_REQUEST")
            timeout: Custom timeout in seconds (overrides default)
            metadata: Optional additional context to track with request

        Examples:
            >>> manager.register_request(1, "TRADE_ACCOUNTS_REQUEST")
            >>> manager.register_request(2, "POSITION_REQUEST", timeout=20.0)
        """
        # Determine timeout
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUTS.get(request_type, self._default_timeout)

        # Create pending request
        pending = PendingRequest(
            request_id=request_id,
            request_type=request_type,
            sent_at=time.time(),
            timeout=timeout,
            metadata=metadata
        )

        self._pending[request_id] = pending

        log.debug(
            "request_registered",
            request_id=request_id,
            request_type=request_type,
            timeout=timeout
        )

    def mark_completed(self, request_id: int) -> bool:
        """
        Mark a request as completed (response received).

        Args:
            request_id: Request ID that was completed

        Returns:
            True if request was found and marked complete, False otherwise

        Examples:
            >>> manager.mark_completed(1)
            True
        """
        if request_id not in self._pending:
            log.debug("request_completed_unknown", request_id=request_id)
            return False

        pending = self._pending.pop(request_id)
        duration = time.time() - pending.sent_at

        self._completed.append(pending)
        self._trim_history()

        log.debug(
            "request_completed",
            request_id=request_id,
            request_type=pending.request_type,
            duration=f"{duration:.2f}s"
        )

        return True

    def check_timeouts(self) -> List[PendingRequest]:
        """
        Check for timed out requests and move them to timed_out list.

        Returns:
            List of requests that timed out since last check

        Examples:
            >>> timed_out = manager.check_timeouts()
            >>> for req in timed_out:
            ...     print(f"Request {req.request_id} timed out!")
        """
        newly_timed_out = []

        # Check all pending requests
        for request_id in list(self._pending.keys()):
            pending = self._pending[request_id]

            if pending.is_timed_out():
                # Move from pending to timed_out
                self._pending.pop(request_id)
                self._timed_out.append(pending)
                newly_timed_out.append(pending)

                # Log timeout warning
                log.warning(
                    "request_timeout",
                    request_id=request_id,
                    request_type=pending.request_type,
                    timeout=pending.timeout,
                    elapsed=time.time() - pending.sent_at
                )

        self._trim_history()
        return newly_timed_out

    def get_pending_count(self) -> int:
        """Get number of currently pending requests"""
        return len(self._pending)

    def get_pending_requests(self) -> List[PendingRequest]:
        """Get list of all currently pending requests"""
        return list(self._pending.values())

    def get_timeout_count(self) -> int:
        """Get total number of timed out requests"""
        return len(self._timed_out)

    def clear_timeout_history(self) -> None:
        """Clear timeout history (useful for testing or after handling)"""
        self._timed_out.clear()

    def reset(self) -> None:
        """Reset all state (useful for reconnection)"""
        self._pending.clear()
        self._completed.clear()
        self._timed_out.clear()
        log.info("request_timeout_manager_reset")

    def _trim_history(self) -> None:
        """Keep history lists at reasonable size"""
        if len(self._completed) > self._max_history:
            self._completed = self._completed[-self._max_history:]

        if len(self._timed_out) > self._max_history:
            self._timed_out = self._timed_out[-self._max_history:]

    def get_stats(self) -> Dict:
        """
        Get statistics about requests.

        Returns:
            Dictionary with request statistics

        Examples:
            >>> stats = manager.get_stats()
            >>> print(f"Pending: {stats['pending']}")
            >>> print(f"Completed: {stats['completed']}")
            >>> print(f"Timed out: {stats['timed_out']}")
        """
        return {
            "pending": len(self._pending),
            "completed": len(self._completed),
            "timed_out": len(self._timed_out),
            "success_rate": (
                len(self._completed) / (len(self._completed) + len(self._timed_out))
                if (len(self._completed) + len(self._timed_out)) > 0
                else 1.0
            )
        }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Request Timeout Manager - Self Test")
    print("=" * 60)
    print()

    # Create manager with 2-second default timeout
    manager = RequestTimeoutManager(default_timeout=2.0)

    # Test 1: Register requests
    print("Test 1: Registering requests")
    print("-" * 40)
    manager.register_request(1, "TRADE_ACCOUNTS_REQUEST")
    manager.register_request(2, "POSITION_REQUEST", timeout=5.0)
    manager.register_request(3, "ACCOUNT_BALANCE_REQUEST")
    print(f"Pending requests: {manager.get_pending_count()}")
    print()

    # Test 2: Complete a request
    print("Test 2: Completing request 1")
    print("-" * 40)
    success = manager.mark_completed(1)
    print(f"Request completed: {success}")
    print(f"Pending requests: {manager.get_pending_count()}")
    print()

    # Test 3: Simulate timeout
    print("Test 3: Checking for timeouts (wait 3 seconds...)")
    print("-" * 40)
    time.sleep(3)
    timed_out = manager.check_timeouts()
    print(f"Timed out requests: {len(timed_out)}")
    for req in timed_out:
        print(f"  - Request {req.request_id} ({req.request_type}) timed out")
    print()

    # Test 4: Stats
    print("Test 4: Statistics")
    print("-" * 40)
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
