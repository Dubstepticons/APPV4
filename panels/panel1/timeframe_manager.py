"""
panels/panel1/timeframe_manager.py

Timeframe management for Panel1 equity chart.

This module handles:
- Timeframe configuration (LIVE, 1D, 1W, 1M, 3M, YTD)
- Window calculations (time ranges)
- Point filtering with binary search
- Snap intervals for different timeframes

Architecture:
- Stateless methods (class as namespace)
- Binary search for efficiency
- Configurable window and snap intervals

Usage:
    from panels.panel1.timeframe_manager import TimeframeManager

    # Filter points for timeframe
    filtered = TimeframeManager.filter_points_for_timeframe(
        points=[(ts, bal), ...],
        timeframe="1D",
        current_time=time.time()
    )

    # Get window configuration
    config = TimeframeManager.get_timeframe_config("1W")
    # Returns: {"window_sec": 604800, "snap_sec": 3600}
"""

from __future__ import annotations

import bisect
from typing import Optional


class TimeframeManager:
    """
    Manages timeframe configurations and point filtering.

    Timeframes:
    - LIVE: Last 1 hour (3600 seconds)
    - 1D: Last 1 day (86400 seconds)
    - 1W: Last 1 week (604800 seconds)
    - 1M: Last 1 month (2592000 seconds, ~30 days)
    - 3M: Last 3 months (7776000 seconds, ~90 days)
    - YTD: Year to date (no window limit)
    """

    # Timeframe configurations
    # window_sec: Time window in seconds (None = no limit)
    # snap_sec: Snap interval for hover/scrubbing
    TIMEFRAME_CONFIGS: dict[str, dict[str, Optional[int]]] = {
        "LIVE": {
            "window_sec": 3600,       # 1 hour
            "snap_sec": 60            # 1 minute
        },
        "1D": {
            "window_sec": 86400,      # 1 day
            "snap_sec": 300           # 5 minutes
        },
        "1W": {
            "window_sec": 604800,     # 1 week
            "snap_sec": 3600          # 1 hour
        },
        "1M": {
            "window_sec": 2592000,    # ~30 days
            "snap_sec": 14400         # 4 hours
        },
        "3M": {
            "window_sec": 7776000,    # ~90 days
            "snap_sec": 43200         # 12 hours
        },
        "YTD": {
            "window_sec": None,       # No limit (year to date)
            "snap_sec": 86400         # 1 day
        },
    }

    # Valid timeframe strings
    VALID_TIMEFRAMES = ["LIVE", "1D", "1W", "1M", "3M", "YTD"]

    @classmethod
    def get_timeframe_config(cls, timeframe: str) -> dict[str, Optional[int]]:
        """
        Get configuration for timeframe.

        Args:
            timeframe: Timeframe string

        Returns:
            Dict with keys: window_sec, snap_sec
            Returns empty dict if timeframe invalid

        Examples:
            >>> TimeframeManager.get_timeframe_config("1W")
            {"window_sec": 604800, "snap_sec": 3600}
        """
        return cls.TIMEFRAME_CONFIGS.get(timeframe, {})

    @classmethod
    def get_window_seconds(cls, timeframe: str) -> Optional[int]:
        """
        Get window size in seconds for timeframe.

        Args:
            timeframe: Timeframe string

        Returns:
            Window size in seconds, or None if no limit (YTD)

        Examples:
            >>> TimeframeManager.get_window_seconds("1D")
            86400
            >>> TimeframeManager.get_window_seconds("YTD")
            None
        """
        config = cls.get_timeframe_config(timeframe)
        return config.get("window_sec")

    @classmethod
    def get_snap_seconds(cls, timeframe: str) -> int:
        """
        Get snap interval in seconds for timeframe.

        Used for hover/scrubbing to snap to nearest interval.

        Args:
            timeframe: Timeframe string

        Returns:
            Snap interval in seconds (defaults to 60 if not found)

        Examples:
            >>> TimeframeManager.get_snap_seconds("1W")
            3600  # 1 hour
        """
        config = cls.get_timeframe_config(timeframe)
        return config.get("snap_sec", 60)

    @classmethod
    def is_valid_timeframe(cls, timeframe: str) -> bool:
        """
        Check if timeframe is valid.

        Args:
            timeframe: Timeframe string to validate

        Returns:
            True if valid, False otherwise

        Examples:
            >>> TimeframeManager.is_valid_timeframe("1D")
            True
            >>> TimeframeManager.is_valid_timeframe("5M")
            False
        """
        return timeframe in cls.VALID_TIMEFRAMES

    @classmethod
    def filter_points_for_timeframe(
        cls,
        points: list[tuple[float, float]],
        timeframe: str,
        current_time: Optional[float] = None
    ) -> list[tuple[float, float]]:
        """
        Filter equity points to timeframe window.

        Uses binary search to efficiently find the starting point for
        the timeframe window, then slices the list.

        Args:
            points: List of (timestamp, balance) tuples (must be sorted by timestamp)
            timeframe: Timeframe string ("LIVE", "1D", "1W", "1M", "3M", "YTD")
            current_time: Current time (defaults to last point timestamp)

        Returns:
            Filtered list of points within timeframe window

        Examples:
            >>> points = [(1000.0, 100.0), (2000.0, 110.0), (3000.0, 120.0)]
            >>> TimeframeManager.filter_points_for_timeframe(points, "1D", 3600.0)
            [(1000.0, 100.0), (2000.0, 110.0), (3000.0, 120.0)]
        """
        if not points:
            return []

        # Get window size for timeframe
        window_sec = cls.get_window_seconds(timeframe)

        # If no window limit (YTD), return all points
        if window_sec is None:
            return points

        # Determine reference time (use last point if not provided)
        if current_time is None:
            last_x = float(points[-1][0])
        else:
            last_x = float(current_time)

        # Calculate window start time
        x_min = last_x - float(window_sec)

        # Binary search for first point >= x_min
        start_index = cls._find_window_start_index(points, x_min)

        # Return slice from start_index to end
        return points[start_index:]

    @classmethod
    def _find_window_start_index(
        cls,
        points: list[tuple[float, float]],
        x_min: float
    ) -> int:
        """
        Find index of first point >= x_min using binary search.

        Args:
            points: List of (timestamp, balance) tuples (sorted by timestamp)
            x_min: Minimum x value (window start)

        Returns:
            Index of first point >= x_min, or 0 if all points < x_min

        Note:
            This is more efficient than linear search for large datasets.
            Complexity: O(log n) vs O(n)
        """
        # Extract timestamps
        xs = [p[0] for p in points]

        # Binary search for insertion point
        # bisect_left returns index where x_min would be inserted
        # to keep list sorted
        index = bisect.bisect_left(xs, x_min)

        # Clamp to valid range
        return max(0, min(index, len(points)))

    @classmethod
    def find_nearest_index(
        cls,
        xs: list[float],
        target_x: float
    ) -> Optional[int]:
        """
        Find index of nearest x value using binary search.

        Used for hover/scrubbing to find closest data point.

        Args:
            xs: Sorted list of x values (timestamps)
            target_x: Target x value to find

        Returns:
            Index of nearest point, or None if list is empty

        Examples:
            >>> TimeframeManager.find_nearest_index([1.0, 2.0, 3.0, 4.0], 2.7)
            2  # Index of 3.0
            >>> TimeframeManager.find_nearest_index([1.0, 2.0, 3.0, 4.0], 1.3)
            0  # Index of 1.0
        """
        if not xs:
            return None

        # Binary search for insertion point
        i = bisect.bisect_right(xs, target_x)

        if i == 0:
            # Before first element
            return 0

        if i >= len(xs):
            # After last element
            return len(xs) - 1

        # Choose closest of i and i-1
        if abs(xs[i] - target_x) < abs(xs[i - 1] - target_x):
            return i
        else:
            return i - 1

    @classmethod
    def calculate_x_range(
        cls,
        points: list[tuple[float, float]],
        timeframe: str
    ) -> Optional[tuple[float, float]]:
        """
        Calculate X range (min, max) for timeframe.

        Uses timeframe window to set range, not just data extent.
        This prevents over-zooming when there are few data points.

        Args:
            points: List of (timestamp, balance) tuples
            timeframe: Timeframe string

        Returns:
            Tuple of (x_min, x_max), or None if no points

        Examples:
            >>> points = [(1000.0, 100.0), (2000.0, 110.0)]
            >>> TimeframeManager.calculate_x_range(points, "1D")
            (-84400.0, 2000.0)  # 1 day window from last point
        """
        if not points:
            return None

        # Get window size
        window_sec = cls.get_window_seconds(timeframe)

        # Get latest time
        x_max = float(points[-1][0])

        if window_sec is None:
            # YTD: Use first point as minimum
            x_min = float(points[0][0])
        else:
            # Use window to set minimum
            x_min = x_max - float(window_sec)

        return (x_min, x_max)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def format_timeframe_label(timeframe: str) -> str:
    """
    Format timeframe as human-readable label.

    Args:
        timeframe: Timeframe string

    Returns:
        Formatted label string

    Examples:
        >>> format_timeframe_label("LIVE")
        "Live (1H)"
        >>> format_timeframe_label("1D")
        "1 Day"
        >>> format_timeframe_label("YTD")
        "Year to Date"
    """
    labels = {
        "LIVE": "Live (1H)",
        "1D": "1 Day",
        "1W": "1 Week",
        "1M": "1 Month",
        "3M": "3 Months",
        "YTD": "Year to Date"
    }
    return labels.get(timeframe, timeframe)


def get_default_timeframe() -> str:
    """
    Get default timeframe.

    Returns:
        Default timeframe string ("LIVE")
    """
    return "LIVE"
