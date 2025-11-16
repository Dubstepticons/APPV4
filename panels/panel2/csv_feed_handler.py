"""
panels/panel2/csv_feed_handler.py

CSV market data feed handler for Panel2.

This module polls snapshot.csv every 500ms to get real-time market data:
- Last price (for P&L calculations)
- Session high/low (for session extremes)
- VWAP (volume-weighted average price)
- Cumulative delta
- Point of control (POC)

Architecture:
- Isolated file I/O (no UI dependencies)
- Emits Qt signals on data updates
- Robust error handling
- Header-aware CSV parsing

Usage:
    from panels.panel2.csv_feed_handler import CSVFeedHandler

    handler = CSVFeedHandler(csv_path="/path/to/snapshot.csv")
    handler.feedUpdated.connect(on_feed_updated)
    handler.start()

    def on_feed_updated(data: dict):
        print(f"Last: {data['last']}, VWAP: {data['vwap']}")
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from PyQt6 import QtCore

import structlog

log = structlog.get_logger(__name__)


class CSVFeedHandler(QtCore.QObject):
    """
    Polls market data from CSV file at regular intervals.

    Emits feedUpdated signal with market data dict on successful reads.
    Handles missing files, malformed CSV, and empty data gracefully.
    """

    # Signals
    feedUpdated = QtCore.pyqtSignal(dict)  # Market data dict
    feedError = QtCore.pyqtSignal(str)  # Error message

    def __init__(
        self,
        csv_path: str,
        poll_interval_ms: int = 500,
        parent: Optional[QtCore.QObject] = None
    ):
        """
        Initialize CSV feed handler.

        Args:
            csv_path: Path to snapshot CSV file
            poll_interval_ms: Polling interval in milliseconds (default: 500ms)
            parent: Parent QObject (optional)
        """
        super().__init__(parent)

        self.csv_path = Path(csv_path)
        self.poll_interval_ms = poll_interval_ms

        # Last known values (for change detection if needed)
        self._last_data: Optional[dict] = None

        # Error state tracking (to avoid log spam)
        self._missing_file_logged = False
        self._error_count = 0

        # Timer
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.poll_interval_ms)
        self._timer.timeout.connect(self._on_tick)

        log.info(
            "[CSVFeedHandler] Initialized",
            csv_path=str(self.csv_path),
            poll_interval_ms=self.poll_interval_ms
        )

    def start(self) -> None:
        """Start polling the CSV file."""
        if not self._timer.isActive():
            self._timer.start()
            log.info("[CSVFeedHandler] Started polling")

    def stop(self) -> None:
        """Stop polling the CSV file."""
        if self._timer.isActive():
            self._timer.stop()
            log.info("[CSVFeedHandler] Stopped polling")

    def is_active(self) -> bool:
        """Return True if currently polling."""
        return self._timer.isActive()

    def _on_tick(self) -> None:
        """
        Timer tick handler - reads CSV and emits data.

        Called every poll_interval_ms milliseconds.
        """
        data = self._read_csv()

        if data:
            # Reset error state on successful read
            if self._error_count > 0:
                log.info("[CSVFeedHandler] Feed recovered after errors")
                self._error_count = 0

            # Store last data
            self._last_data = data

            # Emit signal
            self.feedUpdated.emit(data)

    def _read_csv(self) -> Optional[dict]:
        """
        Read snapshot CSV file.

        Expected CSV format:
            Header row: last,high,low,vwap,cum_delta,poc
            Data row:   6750.25,6800.0,6700.0,6745.5,1234.5,6750.0

        Returns:
            Dict with market data:
            {
                'last': float,       # Current market price
                'high': float,       # Session high
                'low': float,        # Session low
                'vwap': float,       # Volume-weighted average price
                'cum_delta': float,  # Cumulative delta
                'poc': float         # Point of control
            }

            Returns None on error.
        """
        try:
            # Open with UTF-8-sig to handle BOM
            with open(self.csv_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                # Read first data row (after header)
                row = next(reader, None)

                if not row:
                    # Header exists but no data rows
                    return None

                # Parse all fields
                data = {
                    "last": self._parse_float(row, "last"),
                    "high": self._parse_float(row, "high"),
                    "low": self._parse_float(row, "low"),
                    "vwap": self._parse_float(row, "vwap"),
                    "cum_delta": self._parse_float(row, "cum_delta"),
                    "poc": self._parse_float(row, "poc"),
                }

                # Reset missing file flag on successful read
                if self._missing_file_logged:
                    self._missing_file_logged = False
                    log.info("[CSVFeedHandler] CSV file found again")

                return data

        except FileNotFoundError:
            # Log once, then suppress to avoid log spam
            if not self._missing_file_logged:
                log.warning(
                    "[CSVFeedHandler] Snapshot CSV not found",
                    path=str(self.csv_path)
                )
                self._missing_file_logged = True
                self._error_count += 1
                self.feedError.emit(f"File not found: {self.csv_path}")

            return None

        except StopIteration:
            # Header exists but no data rows yet
            # This is normal during startup, don't log
            return None

        except Exception as e:
            # Log every 10th error to avoid spam but track issues
            self._error_count += 1
            if self._error_count % 10 == 1:
                log.error(
                    "[CSVFeedHandler] CSV read error",
                    error=str(e),
                    error_count=self._error_count,
                    exc_info=True
                )
                self.feedError.emit(f"Read error: {e}")

            return None

    @staticmethod
    def _parse_float(row: dict, key: str) -> float:
        """
        Parse float from CSV row dict.

        Args:
            row: CSV row as dict (from DictReader)
            key: Column name

        Returns:
            Parsed float value, or 0.0 if parsing fails
        """
        val = (row.get(key, "") or "").strip()

        if not val:
            return 0.0

        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def get_last_data(self) -> Optional[dict]:
        """
        Get the last successfully read data.

        Returns:
            Last market data dict, or None if no data read yet
        """
        return self._last_data

    def set_poll_interval(self, interval_ms: int) -> None:
        """
        Change the polling interval.

        Args:
            interval_ms: New interval in milliseconds

        Note:
            If timer is active, it will be restarted with new interval.
        """
        was_active = self.is_active()

        if was_active:
            self.stop()

        self.poll_interval_ms = interval_ms
        self._timer.setInterval(interval_ms)

        if was_active:
            self.start()

        log.info(
            "[CSVFeedHandler] Polling interval changed",
            interval_ms=interval_ms
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def validate_csv_format(csv_path: str) -> tuple[bool, str]:
    """
    Validate that CSV file has expected format.

    Args:
        csv_path: Path to CSV file

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, "Error description")

    Usage:
        valid, error = validate_csv_format("/path/to/snapshot.csv")
        if not valid:
            print(f"Invalid CSV: {error}")
    """
    required_columns = {"last", "high", "low", "vwap", "cum_delta", "poc"}

    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            # Check headers
            if reader.fieldnames is None:
                return False, "No header row found"

            headers = set(reader.fieldnames)
            missing = required_columns - headers

            if missing:
                return False, f"Missing columns: {', '.join(missing)}"

            # Try to read first row
            row = next(reader, None)
            if row is None:
                return False, "No data rows found"

            # Try to parse all required fields
            for col in required_columns:
                val = row.get(col, "")
                try:
                    float(val)
                except (ValueError, TypeError):
                    return False, f"Invalid numeric value in column '{col}': {val}"

            return True, ""

    except FileNotFoundError:
        return False, f"File not found: {csv_path}"

    except Exception as e:
        return False, f"Read error: {e}"
