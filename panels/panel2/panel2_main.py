"""
panels/panel2/panel2_main.py

Panel2 main orchestrator - wires all submodules together.

This is the thin coordination layer that:
- Creates all UI widgets
- Instantiates all submodules
- Wires signal connections
- Provides backwards-compatible public API
- Coordinates state updates

Architecture:
- Minimal logic (delegation only)
- Clear signal routing
- Immutable state flow
- Event-driven updates

Usage:
    from panels.panel2.panel2_main import Panel2

    panel = Panel2(parent=main_window)
    panel.on_order_update(dtc_payload)
    panel.on_position_update(dtc_payload)
"""

from __future__ import annotations

import contextlib
import time
from typing import Optional

from PyQt6 import QtCore, QtWidgets

from config.settings import SNAPSHOT_CSV_PATH
from config.theme import THEME, ColorTheme
from utils.theme_mixin import ThemeAwareMixin
from widgets.metric_cell import MetricCell

import structlog

from .position_state import PositionState
from .metrics_calculator import MetricsCalculator
from .csv_feed_handler import CSVFeedHandler
from .state_persistence import StatePersistence
from .visual_indicators import VisualIndicators
from .position_display import PositionDisplay
from .order_flow import OrderFlow

log = structlog.get_logger(__name__)


class Panel2(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Panel2 main orchestrator.

    Coordinates all submodules and provides backwards-compatible API for
    integration with existing APPSIERRA components.

    Modules:
    - PositionState: Immutable state snapshots
    - MetricsCalculator: Pure calculation functions
    - CSVFeedHandler: Market data polling
    - StatePersistence: JSON + DB persistence
    - VisualIndicators: Heat & proximity alerts
    - PositionDisplay: UI rendering
    - OrderFlow: DTC message handling
    """

    # Legacy signal for backwards compatibility
    tradesChanged = QtCore.pyqtSignal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """
        Initialize Panel2 orchestrator.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        # =====================================================================
        # TRADING MODE STATE
        # =====================================================================
        self.current_mode: str = "SIM"
        self.current_account: str = ""
        self._tf: str = "LIVE"  # Timeframe (for pills)

        # =====================================================================
        # BUILD UI WIDGETS
        # =====================================================================
        self._build_ui()

        # =====================================================================
        # CREATE SUBMODULES
        # =====================================================================
        # CSV feed handler
        self.csv_feed = CSVFeedHandler(csv_path=SNAPSHOT_CSV_PATH)

        # Persistence layer
        self.persistence = StatePersistence(
            mode=self.current_mode,
            account=self.current_account
        )

        # Visual indicators
        self.indicators = VisualIndicators()

        # Position display (rendering layer)
        self.display = PositionDisplay(
            # Row 1
            c_price=self.c_price,
            c_heat=self.c_heat,
            c_time=self.c_time,
            c_target=self.c_target,
            c_stop=self.c_stop,
            # Row 2
            c_risk=self.c_risk,
            c_rmult=self.c_rmult,
            c_range=self.c_range,
            c_mae=self.c_mae,
            c_mfe=self.c_mfe,
            # Row 3
            c_vwap=self.c_vwap,
            c_delta=self.c_delta,
            c_poc=self.c_poc,
            c_eff=self.c_eff,
            c_pts=self.c_pts,
            # Banners
            symbol_banner=self.symbol_banner,
            live_banner=self.live_banner,
        )

        # Order flow handler
        self.order_flow = OrderFlow()

        # =====================================================================
        # CURRENT STATE
        # =====================================================================
        # Start with flat state
        self._state = PositionState.flat(mode=self.current_mode, account=self.current_account)

        # =====================================================================
        # WIRE SIGNALS
        # =====================================================================
        self._connect_signals()

        # =====================================================================
        # LOAD PERSISTED STATE
        # =====================================================================
        loaded_state = self.persistence.load_state()
        if loaded_state:
            self._state = loaded_state
            log.info(
                "[Panel2Main] Restored persisted state",
                has_position=loaded_state.has_position()
            )

        # Give state to order flow
        self.order_flow.set_state(self._state)

        # =====================================================================
        # START CSV FEED
        # =====================================================================
        self.csv_feed.start()

        # =====================================================================
        # INITIAL RENDER
        # =====================================================================
        self.refresh()

        log.info("[Panel2Main] Initialized successfully")

    # =========================================================================
    # UI BUILDING
    # =========================================================================

    def _build_ui(self) -> None:
        """Build Panel2 UI widgets."""
        self.setObjectName("Panel2")
        self.setStyleSheet(f"QWidget#Panel2 {{ background:{THEME.get('bg_panel', '#0B0F14')}; }}")

        # Outer column layout
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        # ---- Timeframe pills (top, centered)
        from widgets.timeframe_pills import InvestingTimeframePills

        self.pills = InvestingTimeframePills()
        if hasattr(self.pills, "timeframeChanged"):
            try:
                self.pills.timeframeChanged.connect(
                    self._on_timeframe_changed,
                    type=QtCore.Qt.ConnectionType.UniqueConnection,
                )
            except Exception:
                self.pills.timeframeChanged.connect(self._on_timeframe_changed)

        pills_row = QtWidgets.QHBoxLayout()
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(0)
        pills_row.addStretch(1)
        pills_row.addWidget(self.pills, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        pills_row.addStretch(1)
        outer.addLayout(pills_row)

        # Initialize live dot
        with contextlib.suppress(Exception):
            if hasattr(self.pills, "set_live_dot_visible"):
                self.pills.set_live_dot_visible(True)
            if hasattr(self.pills, "set_live_dot_pulsing"):
                self.pills.set_live_dot_pulsing(self._tf == "LIVE")

        # ---- Header banners (symbol and price)
        hdr = QtWidgets.QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 4)
        hdr.setSpacing(20)

        # Symbol label
        self.symbol_banner = QtWidgets.QLabel("--", self)
        self.symbol_banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.symbol_banner.setFont(
            ColorTheme.heading_qfont(
                int(THEME.get("title_font_weight", 500)),
                int(THEME.get("title_font_size", 16)),
            )
        )
        self.symbol_banner.setStyleSheet(f"color: {THEME.get('ink', '#E5E7EB')};")

        # Live price label
        self.live_banner = QtWidgets.QLabel("FLAT", self)
        self.live_banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.live_banner.setFont(
            ColorTheme.heading_qfont(
                int(THEME.get("title_font_weight", 500)),
                int(THEME.get("title_font_size", 16)),
            )
        )
        self.live_banner.setStyleSheet(f"color: {THEME.get('ink', '#E5E7EB')};")

        # Center header items
        hdr.addStretch(1)
        hdr.addWidget(self.symbol_banner)
        hdr.addWidget(self.live_banner)
        hdr.addStretch(1)
        outer.addLayout(hdr)

        # ---- Metric grid (3 rows x 5 columns)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        outer.addLayout(grid, 1)

        # Row 1
        self.c_price = MetricCell("Price")
        self.c_heat = MetricCell("Heat")
        self.c_time = MetricCell("Time")
        self.c_target = MetricCell("Target")
        self.c_stop = MetricCell("Stop")

        # Row 2
        self.c_risk = MetricCell("Planned Risk")
        self.c_rmult = MetricCell("R-Multiple")
        self.c_range = MetricCell("Range")
        self.c_mae = MetricCell("MAE")
        self.c_mfe = MetricCell("MFE")

        # Row 3
        self.c_vwap = MetricCell("VWAP")
        self.c_delta = MetricCell("Delta")
        self.c_poc = MetricCell("POC")
        self.c_eff = MetricCell("Efficiency")
        self.c_pts = MetricCell("Pts")

        # Add cells to grid
        cells = [
            (0, 0, self.c_price),
            (0, 1, self.c_heat),
            (0, 2, self.c_time),
            (0, 3, self.c_target),
            (0, 4, self.c_stop),
            (1, 0, self.c_risk),
            (1, 1, self.c_rmult),
            (1, 2, self.c_range),
            (1, 3, self.c_mae),
            (1, 4, self.c_mfe),
            (2, 0, self.c_vwap),
            (2, 1, self.c_delta),
            (2, 2, self.c_poc),
            (2, 3, self.c_eff),
            (2, 4, self.c_pts),
        ]
        for r, c, w in cells:
            grid.addWidget(w, r, c)

    # =========================================================================
    # SIGNAL WIRING
    # =========================================================================

    def _connect_signals(self) -> None:
        """Wire all module signals together."""
        # CSV feed → Update state → Update display
        self.csv_feed.feedUpdated.connect(self._on_feed_updated)

        # Order flow → Update state → Save → Update display
        self.order_flow.positionOpened.connect(self._on_position_opened)
        self.order_flow.positionClosed.connect(self._on_position_closed)
        self.order_flow.stateUpdated.connect(self._on_order_flow_state_updated)

        # Indicators → Log alerts (optional handlers)
        self.indicators.heatWarning.connect(self._on_heat_warning)
        self.indicators.heatAlert.connect(self._on_heat_alert)
        self.indicators.heatCritical.connect(self._on_heat_critical)
        self.indicators.stopProximity.connect(self._on_stop_proximity)

        log.debug("[Panel2Main] Signals connected")

    # =========================================================================
    # SIGNAL HANDLERS
    # =========================================================================

    def _on_feed_updated(self, market_data: dict) -> None:
        """
        Handle CSV feed update.

        Updates state with market data, recalculates metrics, updates display.

        Args:
            market_data: Dict with keys: last, high, low, vwap, cum_delta, poc
        """
        try:
            # Update state with market data
            self._state = self._state.with_market_data(**market_data)

            # Update trade extremes (for MAE/MFE)
            if self._state.has_position() and market_data.get("last"):
                last_price = float(market_data["last"])
                self._state = self._state.with_trade_extremes(last_price)

                # Persist extremes to database
                self.persistence.save_position_to_database(self._state)

            # Calculate metrics
            metrics = MetricsCalculator.calculate_all(
                self._state,
                current_epoch=int(time.time())
            )

            # Update indicators (heat/proximity detection)
            self.indicators.update(self._state, current_epoch=int(time.time()))

            # Update display
            self.display.update(self._state, metrics, current_epoch=int(time.time()))

            # Persist state (JSON)
            self.persistence.save_state(self._state)

        except Exception as e:
            log.error("[Panel2Main] Error handling feed update", error=str(e), exc_info=True)

    def _on_position_opened(self, state: PositionState) -> None:
        """
        Handle position opened signal from OrderFlow.

        Args:
            state: New position state
        """
        try:
            log.info(
                "[Panel2Main] Position opened",
                symbol=state.symbol,
                qty=state.entry_qty,
                price=state.entry_price
            )

            # Update state
            self._state = state

            # Persist to database
            self.persistence.save_position_to_database(state)

            # Refresh display
            self.refresh()

        except Exception as e:
            log.error("[Panel2Main] Error handling position opened", error=str(e), exc_info=True)

    def _on_position_closed(self, trade: dict) -> None:
        """
        Handle position closed signal from OrderFlow.

        Args:
            trade: Trade dict with P&L and metrics
        """
        try:
            log.info(
                "[Panel2Main] Position closed",
                symbol=trade.get("symbol"),
                pnl=trade.get("realized_pnl")
            )

            # Clear position state
            self._state = PositionState.flat(
                mode=self._state.current_mode,
                account=self._state.current_account
            )

            # Close position in database
            self.persistence.close_position_in_database()

            # Refresh display
            self.refresh()

            # Emit legacy signal for backwards compatibility
            try:
                payload = dict(trade)
                payload["ok"] = True
                self.tradesChanged.emit(payload)
            except Exception as e:
                log.error("[Panel2Main] Error emitting legacy signal", error=str(e))

        except Exception as e:
            log.error("[Panel2Main] Error handling position closed", error=str(e), exc_info=True)

    def _on_order_flow_state_updated(self, state: PositionState) -> None:
        """
        Handle state update from OrderFlow (e.g., stop/target detected).

        Args:
            state: Updated position state
        """
        try:
            # Update state
            self._state = state

            # Refresh display
            self.refresh()

        except Exception as e:
            log.error("[Panel2Main] Error handling state update", error=str(e), exc_info=True)

    def _on_heat_warning(self) -> None:
        """Handle heat warning (3:00m threshold)."""
        log.warning("[Panel2Main] Heat WARNING: 3:00m threshold reached")

    def _on_heat_alert(self) -> None:
        """Handle heat alert (4:30m threshold)."""
        log.warning("[Panel2Main] Heat ALERT: 4:30m threshold reached (flashing)")

    def _on_heat_critical(self) -> None:
        """Handle heat critical (5:00m threshold)."""
        log.error("[Panel2Main] Heat CRITICAL: 5:00m threshold reached")

    def _on_stop_proximity(self) -> None:
        """Handle stop proximity alert."""
        log.warning("[Panel2Main] Stop proximity detected - price within 1pt of stop")

    @QtCore.pyqtSlot(str)
    def _on_timeframe_changed(self, tf: str) -> None:
        """
        Handle timeframe pill change.

        Args:
            tf: New timeframe
        """
        self._tf = tf
        log.debug("[Panel2Main] Timeframe changed", timeframe=tf)

        # Update live dot pulsing
        with contextlib.suppress(Exception):
            if hasattr(self.pills, "set_live_dot_pulsing"):
                self.pills.set_live_dot_pulsing(tf == "LIVE")

    # =========================================================================
    # BACKWARDS-COMPATIBLE PUBLIC API
    # =========================================================================

    def on_order_update(self, payload: dict) -> None:
        """
        Handle DTC order update (backwards-compatible API).

        Delegates to OrderFlow handler.

        Args:
            payload: Normalized order update dict from DTC
        """
        self.order_flow.on_order_update(payload)

    def on_position_update(self, payload: dict) -> None:
        """
        Handle DTC position update (backwards-compatible API).

        Delegates to OrderFlow handler.

        Args:
            payload: Normalized position update dict from DTC
        """
        self.order_flow.on_position_update(payload)

    def set_trading_mode(self, mode: str, account: str) -> None:
        """
        Switch trading mode (backwards-compatible API).

        Args:
            mode: Trading mode (SIM/LIVE/DEBUG)
            account: Account identifier
        """
        try:
            log.info(
                "[Panel2Main] Switching trading mode",
                old_mode=self.current_mode,
                new_mode=mode,
                old_account=self.current_account,
                new_account=account
            )

            # Update mode/account
            self.current_mode = mode
            self.current_account = account

            # Create new persistence layer
            self.persistence = StatePersistence(mode=mode, account=account)

            # Load state for new mode
            loaded_state = self.persistence.load_state()
            if loaded_state:
                self._state = loaded_state
                log.info("[Panel2Main] Loaded state for new mode", has_position=loaded_state.has_position())
            else:
                # Start with flat state
                self._state = PositionState.flat(mode=mode, account=account)

            # Update order flow state
            self.order_flow.set_state(self._state)

            # Refresh display
            self.refresh()

        except Exception as e:
            log.error("[Panel2Main] Error switching mode", error=str(e), exc_info=True)

    def set_position(self, qty: int, entry_price: float, is_long: Optional[bool]) -> None:
        """
        Manually set position (backwards-compatible API for tests).

        Args:
            qty: Position quantity (unsigned)
            entry_price: Entry price
            is_long: True if long, False if short, None if flat
        """
        try:
            if qty > 0 and entry_price is not None and is_long is not None:
                # Opening position
                self._state = self._state.with_position(
                    entry_qty=abs(qty),
                    entry_price=entry_price,
                    is_long=is_long
                )
                self._state = self._state.with_entry_time(int(time.time()))

                log.info(
                    "[Panel2Main] Position set manually",
                    qty=qty,
                    price=entry_price,
                    is_long=is_long
                )
            else:
                # Closing position
                self._state = PositionState.flat(
                    mode=self._state.current_mode,
                    account=self._state.current_account
                )

                log.info("[Panel2Main] Position cleared manually")

            # Update order flow
            self.order_flow.set_state(self._state)

            # Refresh display
            self.refresh()

        except Exception as e:
            log.error("[Panel2Main] Error setting position", error=str(e), exc_info=True)

    def set_targets(self, target_price: Optional[float], stop_price: Optional[float]) -> None:
        """
        Manually set targets (backwards-compatible API for tests).

        Args:
            target_price: Target price (optional)
            stop_price: Stop price (optional)
        """
        try:
            # Update state
            if target_price is not None:
                self._state = self._state.with_target(target_price)
            if stop_price is not None:
                self._state = self._state.with_stop(stop_price)

            # Refresh display
            self.refresh()

        except Exception as e:
            log.error("[Panel2Main] Error setting targets", error=str(e), exc_info=True)

    def set_symbol(self, symbol: str) -> None:
        """
        Update symbol (backwards-compatible API).

        Args:
            symbol: Trading symbol
        """
        try:
            # Update state
            self._state = self._state.with_symbol(symbol)

            # Update banner
            if hasattr(self, "symbol_banner"):
                self.symbol_banner.setText(symbol)

        except Exception as e:
            log.error("[Panel2Main] Error setting symbol", error=str(e), exc_info=True)

    def refresh(self) -> None:
        """
        Public refresh method (backwards-compatible API for tests).

        Recalculates metrics and updates display.
        """
        try:
            # Calculate metrics
            metrics = MetricsCalculator.calculate_all(
                self._state,
                current_epoch=int(time.time())
            )

            # Update display
            self.display.update(self._state, metrics, current_epoch=int(time.time()))

        except Exception as e:
            log.error("[Panel2Main] Error refreshing display", error=str(e), exc_info=True)

    def get_current_trade_data(self) -> Optional[dict]:
        """
        Get current trade data (backwards-compatible API).

        Returns:
            Dict with position info, or None if flat
        """
        if self._state.is_flat():
            return None

        return {
            "symbol": self._state.symbol,
            "qty": self._state.entry_qty,
            "entry_price": self._state.entry_price,
            "is_long": self._state.is_long,
            "target_price": self._state.target_price,
            "stop_price": self._state.stop_price,
            "last_price": self._state.last_price,
        }

    # =========================================================================
    # THEME REFRESH (ThemeAwareMixin)
    # =========================================================================

    def _build_theme_stylesheet(self) -> str:
        """Build Panel2 stylesheet."""
        return f"QWidget#Panel2 {{ background:{THEME.get('bg_panel', '#000000')}; }}"

    def _get_theme_children(self) -> list:
        """Return child widgets to refresh on theme change."""
        children = []

        # Add metric cells
        for cell in [
            self.c_price, self.c_heat, self.c_time, self.c_target, self.c_stop,
            self.c_risk, self.c_rmult, self.c_range, self.c_mae, self.c_mfe,
            self.c_vwap, self.c_delta, self.c_poc, self.c_eff, self.c_pts
        ]:
            children.append(cell)

        # Add pills
        if hasattr(self, "pills"):
            children.append(self.pills)

        return children
