"""
panels/panel2/chart_integration.py

Chart integration and market data feed module for Panel2.
Handles CSV feed reading, heat detection, proximity alerts, live banner.
"""

from __future__ import annotations

import csv
import os
from typing import Optional, TYPE_CHECKING
from PyQt6 import QtCore

from utils.logger import get_logger

if TYPE_CHECKING:
    from panels.panel2 import Panel2

log = get_logger(__name__)

# Heat detection constants
HEAT_WARN_SEC = 3 * 60  # 3:00 m
HEAT_ALERT_FLASH_SEC = 4 * 60 + 30  # 4:30 m (start flashing)
HEAT_ALERT_SOLID_SEC = 5 * 60  # 5:00 m (red + flash remain)


class ChartIntegration:
    """
    Manages market data feed from CSV and chart-related functionality.

    Responsibilities:
    - Read snapshot.csv for market data (price, VWAP, POC, CumDelta)
    - Update position extremes (for MAE/MFE tracking)
    - Detect heat state transitions
    - Update proximity alerts (near target/stop)
    - Update live mode banner
    """

    def __init__(self, panel: Panel2, csv_path: str):
        """
        Initialize chart integration.

        Args:
            panel: Reference to main Panel2 instance
            csv_path: Path to snapshot.csv file
        """
        self.panel = panel
        self.csv_path = csv_path

        # Market data state
        self.last_price: Optional[float] = None
        self.session_high: Optional[float] = None
        self.session_low: Optional[float] = None
        self.vwap: Optional[float] = None
        self.cum_delta: Optional[float] = None
        self.poc: Optional[float] = None

        log.info(f"Chart integration initialized with CSV path: {csv_path}")

    def on_csv_tick(self):
        """
        CSV timer tick - read market data from snapshot.csv.

        Updates: last_price, session_high, session_low, vwap, cum_delta, poc.
        Also updates position extremes and triggers refreshes.
        """
        if not self.read_snapshot_csv():
            return

        # Update position extremes (for MAE/MFE tracking)
        if self.last_price is not None and not self.panel._position.is_flat:
            self.panel._position.update_extremes(self.last_price)
            # Persist extremes to database
            self.panel._update_trade_extremes_in_database()

        # Trigger UI refresh
        self.panel._refresh_all_cells()

    def read_snapshot_csv(self) -> bool:
        """
        Read market data from snapshot.csv.

        Returns:
            True if read successful, False otherwise
        """
        if not os.path.exists(self.csv_path):
            return False

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if not rows:
                    return False

                row = rows[0]  # Latest snapshot

                # Parse market data
                self.last_price = self._parse_float(row.get("Last"))
                self.session_high = self._parse_float(row.get("High"))
                self.session_low = self._parse_float(row.get("Low"))
                self.vwap = self._parse_float(row.get("VWAP"))
                self.cum_delta = self._parse_float(row.get("CumulativeDelta"))
                self.poc = self._parse_float(row.get("POC"))

                return True

        except Exception as e:
            log.error(f"Chart integration read error: {e}")
            return False

    def update_heat_state_transitions(self, prev_price: Optional[float], new_price: Optional[float]):
        """
        Detect heat state transitions (price crossing entry).

        Starts heat timer when price crosses entry price for the first time.

        Args:
            prev_price: Previous price
            new_price: New price
        """
        if self.panel._position.is_flat:
            return

        if prev_price is None or new_price is None:
            return

        entry_price = self.panel._position.entry_price
        is_long = self.panel._position.is_long

        # Check for entry price crossover
        crossed = False
        if is_long:
            # Long: heat starts when price drops below entry
            crossed = prev_price >= entry_price and new_price < entry_price
        else:
            # Short: heat starts when price rises above entry
            crossed = prev_price <= entry_price and new_price > entry_price

        # Start heat timer if not already running
        if crossed and self.panel.position_display.heat_start_epoch is None:
            import time
            self.panel.position_display.heat_start_epoch = int(time.time())
            log.info(f"Heat started: entry_price={entry_price}, new_price={new_price}")

    def update_proximity_alerts(self):
        """
        Update proximity alerts for target/stop.

        Shows visual alerts when price is near target or stop.
        (To be implemented based on UI design)
        """
        # TODO: Implement proximity alert logic
        # E.g., flash target cell when price within 2 points
        # E.g., flash stop cell when price within 1 point
        pass

    def update_live_banner(self):
        """
        Update live mode banner visibility.

        Shows banner when in LIVE mode (not SIM).
        (To be implemented based on UI design)
        """
        # TODO: Implement live banner logic
        # E.g., show red banner at top when mode == "LIVE"
        pass

    def on_clock_tick(self):
        """
        Clock timer tick (1 second) - update time-based displays.

        Updates: duration, heat timer, live banner.
        """
        import time
        current_epoch = int(time.time())

        # Update time-based cells
        self.panel.position_display.update_time_and_heat(self.panel._position, current_epoch)

        # Update live banner
        self.update_live_banner()

    def get_live_feed_data(self) -> dict:
        """
        Export current market data for other panels.

        Returns:
            Dict with last_price, session_high, session_low, vwap, cum_delta
        """
        return {
            "last_price": self.last_price,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "vwap": self.vwap,
            "cum_delta": self.cum_delta,
        }

    @staticmethod
    def _parse_float(value: Optional[str]) -> Optional[float]:
        """Parse string to float, return None if invalid."""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
