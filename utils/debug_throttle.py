"""
DebugThrottle - Rate-limited diagnostic logging

Prevents high-frequency message streams from flooding logs/console.
Uses monotonic clock for accurate throttling across system sleep/wake cycles.

Usage:
    from utils.debug_throttle import DebugThrottle

    throttle = DebugThrottle()

    # In hot loop:
    if throttle.allow("dtc-messages", interval_ms=1000):
        print(f"DTC message: {msg}")

Benefits:
- Prevents log spam from high-frequency events
- Per-key throttling (different intervals for different message types)
- Thread-safe (uses monotonic clock)
- Configurable intervals per call site
"""

from __future__ import annotations

import time
from typing import Dict


class DebugThrottle:
    """
    Rate-limits debug output based on configurable per-key intervals.

    Each key tracks its own next-allowed timestamp independently.
    """

    def __init__(self):
        # key -> next_allowed_time_ms (monotonic clock)
        self._next_allowed: Dict[str, float] = {}

    def allow(self, key: str, interval_ms: int = 1000) -> bool:
        """
        Check if debug output is allowed for this key.

        Args:
            key: Throttle key (e.g., "dtc-all", "position-updates")
            interval_ms: Minimum milliseconds between allowed outputs

        Returns:
            True if output is allowed (and updates next-allowed time)
            False if too soon since last output

        Example:
            >>> throttle = DebugThrottle()
            >>> if throttle.allow("my-loop", 500):
            ...     print("Debug output")  # Max once per 500ms
        """
        now_ms = time.monotonic() * 1000.0
        next_allowed = self._next_allowed.get(key, 0.0)

        if now_ms >= next_allowed:
            self._next_allowed[key] = now_ms + float(interval_ms)
            return True

        return False

    def reset(self, key: str) -> None:
        """
        Reset throttle state for a specific key.

        Args:
            key: Throttle key to reset
        """
        if key in self._next_allowed:
            del self._next_allowed[key]

    def reset_all(self) -> None:
        """Reset all throttle state (useful for testing)."""
        self._next_allowed.clear()


# Global singleton instance for convenience
_global_throttle = DebugThrottle()


def allow_debug_dump(key: str = "default", interval_ms: int = 1000) -> bool:
    """
    Convenience function for throttled debug output using global throttle.

    Args:
        key: Throttle key (default: "default")
        interval_ms: Minimum milliseconds between outputs

    Returns:
        True if debug output is allowed

    Example:
        >>> from utils.debug_throttle import allow_debug_dump
        >>> if allow_debug_dump("dtc-all", 2000):
        ...     print("Throttled debug output")
    """
    return _global_throttle.allow(key, interval_ms)
