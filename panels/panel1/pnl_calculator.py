"""
panels/panel1/pnl_calculator.py

PnL calculation and formatting utilities for Panel1.

This module provides functions for:
- Calculating PnL amount and percentage
- Finding baseline balance for timeframe windows
- Formatting PnL text with icons
- Determining PnL direction

Architecture:
- Static methods (no state)
- Binary search for efficiency
- Null-safe operations
- Theme-independent

Usage:
    from panels.panel1.pnl_calculator import PnLCalculator

    # Calculate PnL
    result = PnLCalculator.calculate_pnl(current=11000.0, baseline=10000.0)
    # Returns: {amount: 1000.0, percentage: 10.0, is_positive: True}

    # Get baseline for timeframe
    baseline = PnLCalculator.get_baseline_for_timeframe(
        points=[(ts, bal), ...],
        timeframe="1D",
        current_time=1699999999
    )

    # Format PnL text
    text = PnLCalculator.compose_pnl_text(amount=1000.0, pct=10.0, is_positive=True)
    # Returns: "+ $1,000.00 (10.00%)"
"""

from __future__ import annotations

import bisect
from datetime import datetime
from typing import Optional


class PnLCalculator:
    """
    PnL calculation and formatting utilities.

    All methods are static - no instance state required.
    """

    @staticmethod
    def calculate_pnl(
        current_balance: float,
        baseline_balance: float
    ) -> dict:
        """
        Calculate PnL amount and percentage from current and baseline balances.

        Args:
            current_balance: Current account balance
            baseline_balance: Baseline (starting) balance for comparison

        Returns:
            Dict with keys:
            - amount: PnL amount in dollars
            - percentage: PnL percentage
            - is_positive: True if profit, False if loss, None if neutral

        Examples:
            >>> PnLCalculator.calculate_pnl(11000.0, 10000.0)
            {
                "amount": 1000.0,
                "percentage": 10.0,
                "is_positive": True
            }
        """
        # Calculate PnL amount
        pnl_amount = current_balance - baseline_balance

        # Calculate PnL percentage
        if baseline_balance != 0:
            pnl_pct = (pnl_amount / baseline_balance) * 100.0
        else:
            pnl_pct = 0.0

        # Determine direction (with tolerance for floating point)
        if abs(pnl_amount) < 0.01:
            is_positive = None  # Neutral
        else:
            is_positive = pnl_amount > 0

        return {
            "amount": pnl_amount,
            "percentage": pnl_pct,
            "is_positive": is_positive
        }

    @staticmethod
    def get_baseline_for_timeframe(
        points: list[tuple[int, float]],
        timeframe: str,
        current_time: int
    ) -> Optional[float]:
        """
        Get baseline balance for timeframe window using binary search.

        Finds the balance at the start of the timeframe window by:
        1. Calculating window start time based on timeframe
        2. Binary searching for the point at or before that time

        Args:
            points: List of (timestamp, balance) tuples (must be sorted by timestamp)
            timeframe: Timeframe string ("LIVE", "1D", "1W", "1M", "3M", "YTD")
            current_time: Current Unix timestamp

        Returns:
            Baseline balance at window start, or None if no data

        Examples:
            >>> points = [(1000, 100.0), (2000, 110.0), (3000, 120.0)]
            >>> PnLCalculator.get_baseline_for_timeframe(points, "1D", 3600)
            100.0
        """
        if not points:
            return None

        # Extract timestamps and balances
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        # Calculate baseline time based on timeframe
        baseline_time = PnLCalculator._calculate_baseline_time(timeframe, current_time)

        # Binary search for point at or before baseline_time
        i = bisect.bisect_right(xs, baseline_time)

        if i == 0:
            # No points before baseline_time - use first point
            return ys[0]

        # Return balance at or before baseline_time
        return ys[i - 1]

    @staticmethod
    def _calculate_baseline_time(timeframe: str, current_time: int) -> float:
        """
        Calculate Unix timestamp for start of timeframe window.

        Args:
            timeframe: Timeframe string ("LIVE", "1D", "1W", "1M", "3M", "YTD")
            current_time: Current Unix timestamp

        Returns:
            Unix timestamp for window start
        """
        if timeframe == "LIVE":
            # Last hour
            return float(current_time - 3600)

        elif timeframe == "1D":
            # Start of today (midnight)
            dt = datetime.fromtimestamp(current_time)
            return datetime(dt.year, dt.month, dt.day).timestamp()

        elif timeframe == "1W":
            # Last 7 days
            return float(current_time - 604800)

        elif timeframe == "1M":
            # Last 30 days
            return float(current_time - 2592000)

        elif timeframe == "3M":
            # Last 90 days
            return float(current_time - 7776000)

        elif timeframe == "YTD":
            # Year to date (start of year)
            dt = datetime.fromtimestamp(current_time)
            return datetime(dt.year, 1, 1).timestamp()

        else:
            # Default to LIVE
            return float(current_time - 3600)

    @staticmethod
    def compose_pnl_text(
        pnl_amount: Optional[float],
        pnl_pct: Optional[float],
        is_positive: Optional[bool]
    ) -> str:
        """
        Format PnL as text with icon.

        Format: "ICON $amount (percentage%)"

        Args:
            pnl_amount: PnL amount in dollars
            pnl_pct: PnL percentage
            is_positive: True for gains, False for losses, None for neutral

        Returns:
            Formatted string like "+ $1,000.00 (10.00%)" or "- $0.00 (0.00%)"

        Examples:
            >>> PnLCalculator.compose_pnl_text(1000.0, 10.0, True)
            '+ $1,000.00 (10.00%)'
            >>> PnLCalculator.compose_pnl_text(-500.0, -5.0, False)
            '- $500.00 (5.00%)'
            >>> PnLCalculator.compose_pnl_text(None, None, None)
            '- $0.00 (0.00%)'
        """
        if pnl_amount is None or pnl_pct is None:
            # Show zero in neutral color
            return "- $0.00 (0.00%)"

        # Get absolute values (always display positive amounts with icon for direction)
        pnl_abs = abs(pnl_amount)
        pct_abs = abs(pnl_pct)

        # Choose icon based on direction
        if is_positive is None:
            icon = "-"  # Neutral
        else:
            icon = "+" if is_positive else "-"

        # Format: ICON $amount (percentage%)
        result = f"{icon} ${pnl_abs:,.2f} ({pct_abs:.2f}%)"
        return result


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def find_nearest_index(
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
        >>> find_nearest_index([1.0, 2.0, 3.0, 4.0], 2.7)
        2  # Index of 3.0
        >>> find_nearest_index([1.0, 2.0, 3.0, 4.0], 1.3)
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
