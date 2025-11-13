"""
panels/panel2/__init__.py

Panel2 - Live trading metrics with modular architecture.

PHASE 7 REFACTOR: Panel2 broken into focused modules:
- position_display.py - Entry qty, price, time, duration, heat
- pnl_display.py - P&L, MAE, MFE, efficiency, R-multiple, risk
- vwap_display.py - VWAP/POC/CumDelta entry snapshots
- bracket_orders.py - Target/stop price management
- chart_integration.py - CSV feed, heat detection, proximity alerts

This file (__init__.py) contains the main Panel2 class that orchestrates the modules.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtCore, QtWidgets

from config.theme import THEME
from domain.position import Position
from utils.logger import get_logger
from utils.theme_mixin import ThemeAwareMixin

# Import modules
from .position_display import PositionDisplay
from .pnl_display import PnLDisplay
from .vwap_display import VWAPDisplay
from .bracket_orders import BracketOrders
from .chart_integration import ChartIntegration

log = get_logger(__name__)

# CSV feed path
CSV_FEED_PATH = r"C:\Users\cgrah\Desktop\APPSIERRA\data\snapshot.csv"
CSV_REFRESH_MS = 500
TIMER_TICK_MS = 1000


class Panel2(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Panel 2 -- Live trading metrics, modular architecture.

    Modules:
    - PositionDisplay: Entry info, duration, heat timer
    - PnLDisplay: P&L, MAE, MFE, efficiency, R-multiple, risk
    - VWAPDisplay: VWAP/POC/Delta entry snapshots
    - BracketOrders: Target/stop management
    - ChartIntegration: CSV feed, heat detection, alerts
    """

    tradesChanged = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # CRITICAL: (mode, account) scoping
        self.current_mode: str = "SIM"
        self.current_account: str = ""

        # Symbol
        self.symbol: str = "ES"

        # Position domain object (Phase 6 refactor)
        self._position: Position = Position.flat(mode=self.current_mode, account=self.current_account)
        self._position.symbol = self.symbol

        # Module instances (Phase 7 refactor)
        self.position_display: Optional[PositionDisplay] = None
        self.pnl_display: Optional[PnLDisplay] = None
        self.vwap_display: Optional[VWAPDisplay] = None
        self.bracket_orders: Optional[BracketOrders] = None
        self.chart_integration: Optional[ChartIntegration] = None

        # Timers
        self.csv_timer: Optional[QtCore.QTimer] = None
        self.clock_timer: Optional[QtCore.QTimer] = None

        # Build UI
        self._build()
        self._setup_timers()
        self._connect_signal_bus()

        log.info("panel2.initialized", mode=self.current_mode, symbol=self.symbol)

    def _build(self):
        """
        Build UI layout and initialize modules.

        Creates 3x5 grid of metric cells organized into modules.
        """
        layout = QtWidgets.QVBoxLayout(self)
        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        # Initialize modules with grid layout
        # Row 0-1: Position Display (entry, duration, heat)
        self.position_display = PositionDisplay(grid, row_offset=0)

        # Row 2-3: P&L Display (P&L, MAE, MFE, efficiency, R-multiple, risk)
        self.pnl_display = PnLDisplay(grid, row_offset=2)

        # Row 4: VWAP Display (entry VWAP, POC, Delta)
        self.vwap_display = VWAPDisplay(grid, row_offset=4)

        # Additional rows: Bracket Orders (target, stop)
        # Note: These might overlap with existing rows - adjust layout as needed
        # self.bracket_orders = BracketOrders(grid, row_offset=5)

        # Chart integration (no UI cells, handles data feed)
        self.chart_integration = ChartIntegration(self, CSV_FEED_PATH)

        log.info("panel2.built", msg="Panel2 UI built with modular architecture")

    def _setup_timers(self):
        """Setup CSV feed timer (500ms) and clock timer (1s)."""
        # CSV feed timer
        self.csv_timer = QtCore.QTimer(self)
        self.csv_timer.timeout.connect(self.chart_integration.on_csv_tick)
        self.csv_timer.start(CSV_REFRESH_MS)

        # Clock timer (for duration/heat updates)
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.timeout.connect(self.chart_integration.on_clock_tick)
        self.clock_timer.start(TIMER_TICK_MS)

        log.info("panel2.timers_started", csv_ms=CSV_REFRESH_MS, clock_ms=TIMER_TICK_MS)

    def _connect_signal_bus(self):
        """
        Connect to SignalBus for event-driven updates.

        (Phase 3 refactor - migrated from MessageRouter)
        """
        try:
            from core.signal_bus import get_signal_bus
            signal_bus = get_signal_bus()

            # Position updates from DTC
            signal_bus.positionUpdated.connect(
                self.on_position_update,
                type=QtCore.Qt.ConnectionType.QueuedConnection
            )

            # Order updates from DTC
            signal_bus.orderUpdateReceived.connect(
                self.on_order_update,
                type=QtCore.Qt.ConnectionType.QueuedConnection
            )

            # Mode changes
            signal_bus.modeChanged.connect(
                lambda mode: self.set_trading_mode(mode, None),
                type=QtCore.Qt.ConnectionType.QueuedConnection
            )

            log.info("panel2.signal_bus_connected")

        except Exception as e:
            log.error(f"[Panel2] Failed to connect to SignalBus: {e}")

    def _refresh_all_cells(self, initial: bool = False):
        """
        Refresh all display modules from current state.

        Args:
            initial: True if this is initial load
        """
        # Update position display
        self.position_display.update_from_position(self._position)

        # Update P&L display
        self.pnl_display.update_from_position(self._position, self.chart_integration.last_price)

        # Update VWAP display
        if self._position.is_flat:
            # Show live values when no position
            self.vwap_display.update_live_values(
                self.chart_integration.vwap,
                self.chart_integration.poc,
                self.chart_integration.cum_delta
            )
        else:
            # Show entry snapshots when in position
            self.vwap_display.update_entry_snapshots(self._position)

        # Update bracket orders
        # self.bracket_orders.update_from_position(self._position)

    def set_trading_mode(self, mode: str, account: Optional[str] = None):
        """
        Switch trading mode (SIM/LIVE/DEBUG).

        Args:
            mode: Trading mode
            account: Optional account name
        """
        self.current_mode = mode
        if account:
            self.current_account = account

        # Update Position object with new mode
        self._position.mode = mode
        self._position.account = account or ""

        log.info("panel2.mode_changed", mode=mode, account=account)

    def refresh(self):
        """Force refresh of all cells."""
        self._refresh_all_cells()

    # ========================================================================
    # DATABASE & SIGNAL HANDLERS (to be implemented)
    # ========================================================================

    def on_position_update(self, payload: dict):
        """Handle position update from DTC."""
        # TODO: Implement from original panel2.py
        pass

    def on_order_update(self, payload: dict):
        """Handle order update from DTC."""
        # TODO: Implement from original panel2.py
        pass

    def _update_trade_extremes_in_database(self) -> bool:
        """Persist trade extremes (MAE/MFE) to database."""
        # TODO: Implement from original panel2.py
        return False

    # ========================================================================
    # COMPATIBILITY PROPERTIES (Phase 6 - will be removed after full migration)
    # ========================================================================

    @property
    def entry_price(self) -> Optional[float]:
        """Entry price (proxies to _position.entry_price)."""
        return self._position.entry_price if not self._position.is_flat else None

    @property
    def entry_qty(self) -> int:
        """Entry quantity (proxies to _position.qty_abs)."""
        return self._position.qty_abs

    @property
    def is_long(self) -> Optional[bool]:
        """Position direction (proxies to _position.is_long)."""
        return self._position.is_long
