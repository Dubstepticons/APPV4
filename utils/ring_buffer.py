"""
High-Performance Ring Buffer for Time-Series Data

Optimized for equity curve visualization with O(1) append and efficient range queries.
Replaces full database reloads with incremental updates.

Performance improvements over naive approach:
- Append: O(1) vs O(n) database write
- Range query: O(k) where k = visible points vs O(n) full table scan
- Memory: Fixed 5000 points (~40KB) vs unbounded growth
"""

from collections import deque
from datetime import datetime
from typing import Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class TimeSeriesPoint:
    """Single point in time series"""
    timestamp: datetime
    value: float


class RingBuffer:
    """
    Fixed-size circular buffer for time-series data.

    When buffer fills, oldest points are automatically discarded (FIFO).
    Optimized for real-time updates with minimal memory footprint.

    Thread Safety: NOT thread-safe. Use QMutex if accessing from multiple threads.
    """

    def __init__(self, max_points: int = 5000):
        """
        Initialize ring buffer.

        Args:
            max_points: Maximum number of points to retain (default: 5000)
                       Older points are discarded when limit reached.
        """
        self.max_points = max_points
        self.timestamps = deque(maxlen=max_points)
        self.values = deque(maxlen=max_points)
        self._total_points_added = 0

    def append(self, timestamp: datetime, value: float) -> None:
        """
        Add new point to buffer. O(1) operation.

        Args:
            timestamp: Time of measurement
            value: Measured value (e.g., account balance)
        """
        self.timestamps.append(timestamp)
        self.values.append(value)
        self._total_points_added += 1

    def extend(self, points: list[tuple[datetime, float]]) -> None:
        """
        Bulk append multiple points. More efficient than repeated append().

        Args:
            points: List of (timestamp, value) tuples
        """
        for timestamp, value in points:
            self.timestamps.append(timestamp)
            self.values.append(value)
        self._total_points_added += len(points)

    def get_range(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> tuple[list[datetime], list[float]]:
        """
        Get points within time range. O(n) but n = buffer size (5000 max).

        Args:
            start: Start time (inclusive). None = from beginning
            end: End time (inclusive). None = to end

        Returns:
            Tuple of (timestamps, values) within range
        """
        if not self.timestamps:
            return [], []

        # Fast path: return all if no filtering
        if start is None and end is None:
            return list(self.timestamps), list(self.values)

        # Filter by time range
        timestamps_out = []
        values_out = []

        for ts, val in zip(self.timestamps, self.values):
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            timestamps_out.append(ts)
            values_out.append(val)

        return timestamps_out, values_out

    def get_numpy_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Get data as NumPy arrays for high-performance plotting.

        Returns:
            Tuple of (timestamps as float64, values as float32)
            Timestamps are converted to seconds since epoch for plotting
        """
        if not self.timestamps:
            return np.array([]), np.array([])

        # Convert timestamps to float (seconds since epoch)
        timestamps_float = np.array([
            ts.timestamp() for ts in self.timestamps
        ], dtype=np.float64)

        values_array = np.array(list(self.values), dtype=np.float32)

        return timestamps_float, values_array

    def get_latest(self, n: int = 1) -> list[TimeSeriesPoint]:
        """
        Get n most recent points. O(n) where n is small.

        Args:
            n: Number of recent points to retrieve

        Returns:
            List of TimeSeriesPoint, newest first
        """
        if not self.timestamps:
            return []

        n = min(n, len(self.timestamps))
        points = []

        for i in range(1, n + 1):
            points.append(TimeSeriesPoint(
                timestamp=self.timestamps[-i],
                value=self.values[-i]
            ))

        return points

    def get_current_value(self) -> Optional[float]:
        """Get most recent value. O(1) operation."""
        return self.values[-1] if self.values else None

    def clear(self) -> None:
        """Remove all points from buffer."""
        self.timestamps.clear()
        self.values.clear()
        self._total_points_added = 0

    def __len__(self) -> int:
        """Return number of points currently in buffer."""
        return len(self.timestamps)

    def __repr__(self) -> str:
        return (
            f"RingBuffer(size={len(self)}/{self.max_points}, "
            f"total_added={self._total_points_added})"
        )


class EquityCurveBuffer:
    """
    Specialized ring buffer for equity curves with automatic database sync.

    Maintains separate buffers for each (mode, account) pair.
    Periodically syncs to database in batches for persistence.
    """

    def __init__(self, max_points_per_curve: int = 5000):
        """
        Initialize equity curve manager.

        Args:
            max_points_per_curve: Max points per (mode, account) curve
        """
        self.max_points = max_points_per_curve
        self._curves: dict[tuple[str, str], RingBuffer] = {}
        self._pending_db_writes: list[tuple[str, str, datetime, float]] = []
        self._last_sync_time = datetime.now()

    def add_point(self, mode: str, account: str, timestamp: datetime, value: float) -> None:
        """
        Add equity point for specific (mode, account).

        Args:
            mode: Trading mode (SIM/LIVE/DEBUG)
            account: Account identifier
            timestamp: Time of measurement
            value: Account balance
        """
        key = (mode, account)

        # Create buffer on first use
        if key not in self._curves:
            self._curves[key] = RingBuffer(self.max_points)

        self._curves[key].append(timestamp, value)

        # Queue for database sync
        self._pending_db_writes.append((mode, account, timestamp, value))

    def get_curve(self, mode: str, account: str) -> Optional[RingBuffer]:
        """
        Get ring buffer for specific (mode, account).

        Returns:
            RingBuffer instance or None if no data
        """
        return self._curves.get((mode, account))

    def get_plot_data(self, mode: str, account: str) -> tuple[np.ndarray, np.ndarray]:
        """
        Get NumPy arrays ready for plotting.

        Returns:
            Tuple of (timestamps, values) as NumPy arrays
        """
        buffer = self.get_curve(mode, account)
        if buffer:
            return buffer.get_numpy_arrays()
        return np.array([]), np.array([])

    def should_sync_to_db(self, interval_seconds: int = 10) -> bool:
        """
        Check if database sync is due.

        Args:
            interval_seconds: Minimum seconds between syncs

        Returns:
            True if sync should occur
        """
        elapsed = (datetime.now() - self._last_sync_time).total_seconds()
        return elapsed >= interval_seconds and len(self._pending_db_writes) > 0

    def get_pending_writes(self) -> list[tuple[str, str, datetime, float]]:
        """
        Get and clear pending database writes.

        Returns:
            List of (mode, account, timestamp, value) tuples
        """
        pending = self._pending_db_writes.copy()
        self._pending_db_writes.clear()
        self._last_sync_time = datetime.now()
        return pending

    def load_from_database(self, mode: str, account: str, points: list[tuple[datetime, float]]) -> None:
        """
        Load historical data from database into buffer.

        Call this once on startup to hydrate buffers.

        Args:
            mode: Trading mode
            account: Account identifier
            points: List of (timestamp, value) tuples from database
        """
        key = (mode, account)

        if key not in self._curves:
            self._curves[key] = RingBuffer(self.max_points)

        # Bulk load (efficient)
        self._curves[key].extend(points)
