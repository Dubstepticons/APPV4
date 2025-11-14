"""
Timeframe utility functions for date/time calculations.

CONSOLIDATION FIX: Central location for timeframe logic (DRY principle).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


def timeframe_start(tf: str, now: Optional[datetime] = None) -> datetime:
    """
    Calculate the start datetime for a given timeframe.

    CONSOLIDATION FIX: Single source of truth for timeframe calculations.
    Previously duplicated in services/stats_service.py and services/trade_service.py.

    Args:
        tf: Timeframe string ("LIVE", "1D", "1W", "1M", "3M", "YTD")
        now: Reference datetime (defaults to current UTC time)

    Returns:
        Start datetime for the specified timeframe

    Examples:
        >>> from datetime import datetime
        >>> ref = datetime(2024, 6, 15, 12, 0, 0)
        >>> timeframe_start("1D", ref)  # 24 hours ago
        datetime(2024, 6, 14, 12, 0, 0)
        >>> timeframe_start("YTD", ref)  # Start of year
        datetime(2024, 1, 1, 0, 0, 0)
    """
    now = now or datetime.utcnow()
    t = tf.upper()

    if t == "LIVE":
        # Short-horizon "live" view (last 1 hour)
        return now - timedelta(hours=1)
    if t == "1D":
        return now - timedelta(days=1)
    if t == "1W":
        return now - timedelta(weeks=1)
    if t == "1M":
        return now - timedelta(days=30)
    if t == "3M":
        return now - timedelta(days=90)
    # YTD (Year-To-Date)
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
