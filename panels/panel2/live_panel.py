"""
Live Panel Module

READ-ONLY UI LAYER for Panel2 live trading metrics display.

Architecture Contract:
- NO state storage (all state in state_manager)
- NO mutations (read-only access to state via state_manager.get_state())
- NO calculations (delegates to metrics_updater)
- ONLY UI updates and timer management

Panel2 Architecture:
- state_manager: Single source of truth for ALL state
- metrics_updater: Pure calculation module (no mutations)
- trade_handlers: DTC message normalization only
- live_panel: Read-only UI layer (this file)

Features:
- 3x5 grid layout with 15 MetricCell widgets
- CSV feed integration (500ms refresh)
- Timer-based updates (duration, heat)
- State persistence with mode scoping
- Theme integration
- Public API for external control
"""

from __future__ import annotations

import csv
import time
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from config.theme import THEME, ColorTheme
from config.trading_specs import match_spec
from services.trade_math import TradeMath
from utils.format_utils import extract_symbol_display
from utils.logger import get_logger
from utils.theme_mixin import ThemeAwareMixin
from widgets.metric_cell import MetricCell

# Import helper modules
from panels.panel2 import state_manager, trade_handlers, metrics_updater
from panels.panel2.state_manager import StateManager

log = get_logger(__name__)

# -------------------- Constants & Config (start)
CSV_FEED_PATH = r"C:\Users\cgrah\Desktop\APPSIERRA\data\snapshot.csv"

CSV_REFRESH_MS = 500
TIMER_TICK_MS = 1000
# -------------------- Constants & Config (end)


# -------------------- Panel 2 Main (start)
class Panel2(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Panel 2 -- Live trading metrics, 3x5 grid layout. Live CSV feed (500 ms),
    Duration/Heat timers with persistence, state-change logging.

    Architecture: READ-ONLY UI - all state in StateManager.
    """

    tradesChanged = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # CRITICAL: StateManager is the SINGLE SOURCE OF TRUTH
        # Panel stores NO state - all data lives in state_manager
        self._state_manager = StateManager()

        # Timeframe state (for pills & pulsing dot)
        self._tf: str = "LIVE"
        self._pnl_up: Optional[bool] = None  # optional hint for pill color

        # Build UI and timers
        self._build()
        self._setup_timers()

        # Load scoped state after UI is built
        try:
            self._state_manager.load_state()
        except Exception as e:
            log.warning(f"[Panel2] Failed to load initial state: {e}")

        # First paint
        state = self._state_manager.get_state()
        metrics_updater.refresh_all_cells(self, state, initial=True)

        # Apply current theme colors (in case theme was switched before this panel was created)
        self.refresh_theme()

    # -------------------- Trade persistence hooks (start)
    def notify_trade_closed(self, trade: dict) -> None:
        """
        External hook to persist a closed trade and notify listeners.
        Delegates to trade_handlers module.

        Args:
            trade: Trade dict with keys:
                - symbol, side, qty, entry_price, exit_price, realized_pnl
                - entry_time, exit_time, commissions, r_multiple, mae, mfe, account (optional)
        """
        trade_handlers.notify_trade_closed(self, trade)

    def on_order_update(self, payload: dict) -> None:
        """
        Handle normalized OrderUpdate from DTC (via data_bridge).
        Delegates to trade_handlers module.

        Args:
            payload: Normalized order update dict from data_bridge (not raw DTC)
        """
        trade_handlers.on_order_update(self, payload)

        # Refresh UI after handler updates state
        state = self._state_manager.get_state()
        metrics_updater.refresh_all_cells(self, state)

    def on_position_update(self, payload: dict) -> None:
        """
        Handle normalized PositionUpdate from DTC and mirror into state_manager.
        Delegates to trade_handlers module.

        Args:
            payload: Normalized position update dict from MessageRouter (lowercase keys)
        """
        trade_handlers.on_position_update(self, payload)

        # UI refresh already handled by trade_handlers

    # -------------------- Trade persistence hooks (end)

    # -------------------- UI Build (start)
    def _build(self):
        self.setObjectName("Panel2")
        # NOTE: Stylesheet set by refresh_theme() via ThemeAwareMixin
        # Do NOT set here - it will override theme changes!

        # Outer column layout for header + grid
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        # ---- Timeframe pills (top, centered)
        from widgets.timeframe_pills import InvestingTimeframePills  # type: ignore

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

        # Initialize live dot state/color
        try:
            if hasattr(self.pills, "set_live_dot_visible"):
                self.pills.set_live_dot_visible(True)
            if hasattr(self.pills, "set_live_dot_pulsing"):
                self.pills.set_live_dot_pulsing(self._tf == "LIVE")
            if hasattr(self.pills, "set_active_color"):
                color = (
                    ColorTheme.pnl_color_from_direction(self._pnl_up)
                    if self._pnl_up is not None
                    else THEME.get("pnl_neu_color", "#C9CDD0")
                )
                self.pills.set_active_color(color)
        except Exception:
            pass

        # ---- Live Position header (horizontal layout: title, symbol, and price on same row)
        hdr = QtWidgets.QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 4)
        hdr.setSpacing(20)

        # Symbol label (left) - shows "--" when flat, populated from DTC order update
        # Uses heading font (Lato in LIVE/SIM)
        self.symbol_banner = QtWidgets.QLabel("--", self)
        self.symbol_banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.symbol_banner.setFont(
            ColorTheme.heading_qfont(
                int(THEME.get("title_font_weight", 500)),
                int(THEME.get("title_font_size", 16)),
            )
        )
        # NOTE: Color set in _on_theme_refresh()

        # Live price label (right) - shows "FLAT" when not in position, current market price when in position
        # Uses heading font (Lato in LIVE/SIM)
        self.live_banner = QtWidgets.QLabel("FLAT", self)
        self.live_banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.live_banner.setFont(
            ColorTheme.heading_qfont(
                int(THEME.get("title_font_weight", 500)),
                int(THEME.get("title_font_size", 16)),
            )
        )
        # NOTE: Color set in _on_theme_refresh()

        # Center both header items in a single row
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

    # -------------------- UI Build (end)

    # -------------------- Timers & Feed (start)
    def _setup_timers(self):
        # CSV feed timer - provides live market data for calculations
        # CSV contains: last (live price), high, low, vwap, cum_delta
        # Used for: P&L, MAE, MFE, heat tracking, VWAP analysis
        self._csv_timer = QtCore.QTimer(self)
        self._csv_timer.setInterval(CSV_REFRESH_MS)
        self._csv_timer.timeout.connect(self._on_csv_tick)
        self._csv_timer.start()

        # Duration/Heat tick
        self._clock_timer = QtCore.QTimer(self)
        self._clock_timer.setInterval(TIMER_TICK_MS)
        self._clock_timer.timeout.connect(self._on_clock_tick)
        self._clock_timer.start()

        # Flash is per-cell (handled internally by MetricCell)

    def _on_csv_tick(self):
        """
        CSV feed tick handler.

        DATA SOURCE CLARIFICATION:
        - CSV file (snapshot.csv) provides: last, high, low, vwap, cum_delta
          * 'last' = live market price (for P&L and heat calculations)
          * 'high'/'low' = session extremes (for MAE/MFE)
          * 'vwap' = volume-weighted average price
          * 'cum_delta' = cumulative delta
        - DTC messages provide: entry price, position qty, order status
          * Price cell shows entry price from DTC (e.g., "2 @ 5800.25")
          * Live price from CSV is NOT displayed but used for calculations
        """
        updated = self._read_snapshot_csv()
        if not updated:
            return

        # Get state from state_manager (read-only)
        state = self._state_manager.get_state()

        # Track per-trade min/max while in position for MAE/MFE
        # CRITICAL: Update state_manager, not panel fields
        try:
            if state.entry_qty and state.last_price is not None:
                p = float(state.last_price)
                if state.trade_min_price is None or p < state.trade_min_price:
                    state.trade_min_price = p
                if state.trade_max_price is None or p > state.trade_max_price:
                    state.trade_max_price = p
        except Exception:
            pass

        # UI update
        metrics_updater.refresh_all_cells(self, state)

        # Proximity alerts
        metrics_updater.update_proximity_alerts(self, state)

        # Update the non-cell banner
        metrics_updater.update_live_banner(self, state)

    def _on_clock_tick(self):
        """
        Timer tick for duration/heat updates.

        CRITICAL: Handle heat timer start/stop signals from metrics_updater.
        """
        # Get state from state_manager
        state = self._state_manager.get_state()

        # Update time/heat display (this sets _heat_should_start/_heat_should_stop signals)
        metrics_updater.update_time_and_heat_cells(self, state)

        # Handle heat timer signals (bridge until we refactor timer to state-manager)
        if hasattr(self, '_heat_should_start') and self._heat_should_start:
            # Start heat timer
            state.heat_start_epoch = int(time.time())
            self._heat_should_start = False
            log.info("[panel2] Heat timer STARTED")

        if hasattr(self, '_heat_should_stop') and self._heat_should_stop:
            # Stop heat timer
            if state.heat_start_epoch is not None:
                elapsed = int(time.time() - state.heat_start_epoch)
                log.info(f"[panel2] Heat timer PAUSED (was underwater for {elapsed}s)")
            state.heat_start_epoch = None
            self._heat_should_stop = False

    def _read_snapshot_csv(self) -> bool:
        """
        Header-aware CSV reader:
          - Expects header row: last,high,low,vwap,cum_delta,poc
          - Uses FIRST data row after the header (row 2)
          - Robust to BOM and column re-ordering

        CRITICAL: Updates state_manager, NOT panel fields.
        """
        try:
            # Get state from state_manager
            state = self._state_manager.get_state()

            with open(CSV_FEED_PATH, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                row = next(reader, None)  # first data row after header
                if not row:
                    return False

                def fnum(key: str) -> float:
                    val = (row.get(key, "") or "").strip()
                    if not val:
                        return 0.0  # Default to 0.0 for empty values
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0

                # Update state_manager, NOT panel fields
                state.last_price = fnum("last")
                state.session_high = fnum("high")
                state.session_low = fnum("low")
                state.vwap = fnum("vwap")
                state.cum_delta = fnum("cum_delta")
                state.poc = fnum("poc")

                return True

        except FileNotFoundError:
            static_key = "_missing_csv_logged"
            if not getattr(self, static_key, False):
                log.warning(f"[panel2] Snapshot CSV not found at: {CSV_FEED_PATH}")
                setattr(self, static_key, True)
            return False
        except StopIteration:
            # Header exists but no data rows yet
            return False
        except Exception as e:
            log.error(f"[panel2] CSV read error: {e}")
            return False

    # -------------------- Timers & Feed (end)

    # -------------------- Position Interface (start)
    def set_position(self, qty: int, entry_price: float, is_long: Optional[bool]):
        """
        DEPRECATED: Use state_manager directly.
        Kept for backward compatibility with tests.
        """
        # Get state from state_manager
        state = self._state_manager.get_state()

        state.entry_qty = max(0, int(qty))

        # Start duration timer if entering a position
        if state.entry_qty > 0 and entry_price is not None:
            state.entry_price = float(entry_price)
            state.is_long = is_long
            if not state.entry_time_epoch:
                state.entry_time_epoch = int(time.time())
                # Capture VWAP, Delta, and POC snapshots at entry (static values)
                state.entry_vwap = state.vwap
                state.entry_delta = state.cum_delta
                state.entry_poc = state.poc
                # Initialize trade extremes to entry price (prevents premature MAE/MFE)
                state.trade_min_price = state.entry_price
                state.trade_max_price = state.entry_price

                log.info(f"[panel2] Position opened via set_position(): vwap={state.entry_vwap}, delta={state.entry_delta}, poc={state.entry_poc}")
        else:
            # No position - reset state via state_manager
            self._state_manager.reset_position()
            log.info("[panel2] Position closed -- all position data cleared")

        self._state_manager.save_state()
        metrics_updater.refresh_all_cells(self, state)
        metrics_updater.update_live_banner(self, state)

    def set_targets(self, target_price: Optional[float], stop_price: Optional[float]):
        """
        DEPRECATED: Use state_manager directly.
        Kept for backward compatibility with tests.
        """
        state = self._state_manager.get_state()
        state.target_price = float(target_price) if target_price is not None else None
        state.stop_price = float(stop_price) if stop_price is not None else None
        metrics_updater.refresh_all_cells(self, state)
        metrics_updater.update_live_banner(self, state)

    def set_symbol(self, symbol: str):
        """
        Update the symbol label (called from DTC handshake or external source).
        Extracts 3-letter display symbol from full DTC symbol.
        Example: 'F.US.MESZ25' -> 'MES'
        """
        state = self._state_manager.get_state()
        state.symbol = symbol.strip().upper() if symbol else "ES"
        # Extract display symbol (3 letters after "US.")
        display_sym = extract_symbol_display(state.symbol)
        if hasattr(self, "symbol_banner"):
            self.symbol_banner.setText(display_sym)

    def set_trading_mode(self, mode: str, account: Optional[str] = None) -> None:
        """
        Update trading mode for this panel.
        Delegates to state_manager module.

        Args:
            mode: Trading mode ("SIM", "LIVE", "DEBUG")
            account: Account identifier (optional, defaults to empty string)
        """
        state_manager.set_trading_mode(self, mode, account)

    # -------------------- Position Interface (end)

    # -------------------- Timeframe handling (start)
    @QtCore.pyqtSlot(str)
    def _on_timeframe_changed(self, tf: str) -> None:
        if tf not in ("LIVE", "1D", "1W", "1M", "3M", "YTD"):
            return
        self._tf = tf
        # Update LIVE dot/pulse and color
        try:
            if hasattr(self.pills, "set_live_dot_visible"):
                self.pills.set_live_dot_visible(True)
            if hasattr(self.pills, "set_live_dot_pulsing"):
                self.pills.set_live_dot_pulsing(tf == "LIVE")
            if hasattr(self.pills, "set_active_color"):
                color = (
                    ColorTheme.pnl_color_from_direction(self._pnl_up)
                    if self._pnl_up is not None
                    else THEME.get("pnl_neu_color", "#C9CDD0")
                )
                self.pills.set_active_color(color)
        except Exception:
            pass

    def refresh_pill_colors(self) -> None:
        """
        Force timeframe pills to refresh their colors from THEME.
        Called when trading mode switches (DEBUG/SIM/LIVE) to update pill colors.
        """
        try:
            if hasattr(self.pills, "set_active_color"):
                # Clear cached color to force refresh
                if hasattr(self.pills, "_last_active_hex"):
                    delattr(self.pills, "_last_active_hex")
                # Re-read color from THEME and apply
                color = (
                    ColorTheme.pnl_color_from_direction(self._pnl_up)
                    if self._pnl_up is not None
                    else THEME.get("pnl_neu_color", "#C9CDD0")
                )
                self.pills.set_active_color(color)
        except Exception:
            pass

    # -------------------- Timeframe handling (end)

    # -------------------- Public API (start)
    def refresh(self) -> None:
        """Public refresh method to align with tests and other panels."""
        try:
            state = self._state_manager.get_state()
            metrics_updater.refresh_all_cells(self, state)
        except Exception:
            pass

    def get_current_trade_data(self) -> dict:
        """
        Expose current trade metrics for Panel 3 to grab directly.
        Returns all live trading data including P&L, MAE, MFE, R-multiple, etc.
        Panel 3 uses this for real-time statistical analysis before storage.

        CRITICAL: Read from state_manager, not panel fields.
        """
        state = self._state_manager.get_state()

        data = {
            "symbol": state.symbol,
            "entry_qty": state.entry_qty,
            "entry_price": state.entry_price,
            "is_long": state.is_long,
            "target_price": state.target_price,
            "stop_price": state.stop_price,
            "last_price": state.last_price,
            "session_high": state.session_high,
            "session_low": state.session_low,
            "vwap": state.vwap,
            "cum_delta": state.cum_delta,
            "entry_time_epoch": state.entry_time_epoch,
            "heat_start_epoch": state.heat_start_epoch,
            "trade_min_price": state.trade_min_price,
            "trade_max_price": state.trade_max_price,
        }

        # Calculate derived metrics if we have an active position
        if state.entry_qty and state.entry_price is not None and state.last_price is not None:
            # P&L calculation using symbol-aware constants
            spec = match_spec(state.symbol)
            sign = 1 if state.is_long else -1
            pnl_pts = (state.last_price - state.entry_price) * sign
            gross_pnl = pnl_pts * spec["pt_value"] * state.entry_qty
            comm = spec["rt_fee"] * state.entry_qty
            net_pnl = gross_pnl - comm

            data["pnl_points"] = pnl_pts
            data["gross_pnl"] = gross_pnl
            data["commissions"] = comm
            data["net_pnl"] = net_pnl

            # MAE/MFE from TRADE extremes (not session extremes)
            if state.trade_min_price is not None and state.trade_max_price is not None:
                # Use centralized TradeMath calculation
                mae_pts, mfe_pts = TradeMath.calculate_mae_mfe(
                    entry_price=state.entry_price,
                    trade_min_price=state.trade_min_price,
                    trade_max_price=state.trade_max_price,
                    is_long=state.is_long,
                )

                if mae_pts is not None and mfe_pts is not None:
                    data["mae_points"] = mae_pts
                    data["mfe_points"] = mfe_pts
                    data["mae_dollars"] = mae_pts * spec["pt_value"] * state.entry_qty
                    data["mfe_dollars"] = mfe_pts * spec["pt_value"] * state.entry_qty

                # Calculate efficiency: (realized PnL / MFE) if MFE > 0
                if mfe_pts > 0 and "net_pnl" in data:
                    efficiency = min(1.0, max(0.0, data["net_pnl"] / (mfe_pts * spec["pt_value"] * state.entry_qty)))
                    data["efficiency"] = efficiency
                else:
                    data["efficiency"] = None

            # R-multiple
            if state.stop_price is not None and float(state.stop_price) > 0:
                risk_per_contract = abs(state.entry_price - float(state.stop_price)) * spec["pt_value"]
                if risk_per_contract > 0:
                    r_multiple = net_pnl / (risk_per_contract * state.entry_qty)
                    data["r_multiple"] = r_multiple

            # Duration
            if state.entry_time_epoch:
                data["duration_seconds"] = int(time.time() - state.entry_time_epoch)

            # Heat duration
            if state.heat_start_epoch:
                data["heat_seconds"] = int(time.time() - state.heat_start_epoch)

        return data

    def get_live_feed_data(self) -> dict:
        """
        Expose current CSV feed data for Panel 3 analysis.
        Returns live market data: price, high, low, vwap, delta.

        CRITICAL: Read from state_manager, not panel fields.
        """
        state = self._state_manager.get_state()
        return {
            "last_price": state.last_price,
            "session_high": state.session_high,
            "session_low": state.session_low,
            "vwap": state.vwap,
            "cum_delta": state.cum_delta,
        }

    def get_trade_state(self) -> dict:
        """
        Expose position state for Panel 3 queries.
        Returns basic position information: qty, entry, direction, targets.

        CRITICAL: Read from state_manager, not panel fields.
        """
        state = self._state_manager.get_state()
        return {
            "symbol": state.symbol,
            "qty": state.entry_qty,
            "entry_price": state.entry_price,
            "is_long": state.is_long,
            "target_price": state.target_price,
            "stop_price": state.stop_price,
            "has_position": state.has_position(),
        }

    def has_active_position(self) -> bool:
        """Quick check if there's an active trade for Panel 3 to analyze."""
        state = self._state_manager.get_state()
        return state.has_position()

    def seed_demo_position(
        self,
        qty: int = 2,
        entry: float = 4000.00,
        is_long: bool = True,
        target: float | None = None,
        stop: float | None = None,
    ):
        """Optional helper for quick manual testing."""
        self.set_position(qty, entry, is_long)
        self.set_targets(target, stop)

    # -------------------- Public API (end)

    # -------------------- Theme refresh (start) -----------------------------------
    def _build_theme_stylesheet(self) -> str:
        """Build Panel2 stylesheet."""
        return f"QWidget#Panel2 {{ background:{THEME.get('bg_panel', '#000000')}; }}"

    def _get_theme_children(self) -> list:
        """Return child widgets to refresh."""
        cells = [
            self.c_price,
            self.c_heat,
            self.c_time,
            self.c_target,
            self.c_stop,
            self.c_risk,
            self.c_rmult,
            self.c_range,
            self.c_mae,
            self.c_mfe,
            self.c_vwap,
            self.c_delta,
            self.c_poc,
            self.c_eff,
            self.c_pts,
        ]
        if hasattr(self, "pills") and self.pills:
            cells.append(self.pills)
        return cells

    def _on_theme_refresh(self) -> None:
        """Update banners after theme refresh."""
        # Update banners
        if hasattr(self, "symbol_banner") and self.symbol_banner:
            self.symbol_banner.setStyleSheet(f"color: {THEME.get('ink', '#E5E7EB')};")
        if hasattr(self, "live_banner") and self.live_banner:
            self.live_banner.setStyleSheet(f"color: {THEME.get('ink', '#E5E7EB')};")

    # -------------------- Theme refresh (end) -------------------------------------

    # Ensure timers persisted on close
    def closeEvent(self, ev: QtGui.QCloseEvent) -> None:
        self._state_manager.save_state()
        super().closeEvent(ev)


    # -------------------- Properties for backward compatibility (start) ----------
    # These provide read-only access to state for tests and external code
    # DO NOT use these internally - use state_manager.get_state() instead

    @property
    def current_mode(self) -> str:
        """Current trading mode (read from state_manager)."""
        return self._state_manager.get_active_scope()[0]

    @current_mode.setter
    def current_mode(self, value: str) -> None:
        """Set current mode (updates state_manager)."""
        _, account = self._state_manager.get_active_scope()
        self._state_manager.set_active_scope(value, account)

    @property
    def current_account(self) -> str:
        """Current account (read from state_manager)."""
        return self._state_manager.get_active_scope()[1]

    @current_account.setter
    def current_account(self, value: str) -> None:
        """Set current account (updates state_manager)."""
        mode, _ = self._state_manager.get_active_scope()
        self._state_manager.set_active_scope(mode, value)

    # Direct state field access for backward compatibility
    # All of these are READ-ONLY properties that read from state_manager

    @property
    def symbol(self) -> str:
        return self._state_manager.get_state().symbol

    @property
    def entry_price(self) -> Optional[float]:
        return self._state_manager.get_state().entry_price

    @property
    def entry_qty(self) -> int:
        return self._state_manager.get_state().entry_qty

    @property
    def is_long(self) -> Optional[bool]:
        return self._state_manager.get_state().is_long

    @property
    def target_price(self) -> Optional[float]:
        return self._state_manager.get_state().target_price

    @property
    def stop_price(self) -> Optional[float]:
        return self._state_manager.get_state().stop_price

    @property
    def last_price(self) -> Optional[float]:
        return self._state_manager.get_state().last_price

    @property
    def session_high(self) -> Optional[float]:
        return self._state_manager.get_state().session_high

    @property
    def session_low(self) -> Optional[float]:
        return self._state_manager.get_state().session_low

    @property
    def vwap(self) -> Optional[float]:
        return self._state_manager.get_state().vwap

    @property
    def cum_delta(self) -> Optional[float]:
        return self._state_manager.get_state().cum_delta

    @property
    def entry_vwap(self) -> Optional[float]:
        return self._state_manager.get_state().entry_vwap

    @property
    def entry_delta(self) -> Optional[float]:
        return self._state_manager.get_state().entry_delta

    @property
    def entry_poc(self) -> Optional[float]:
        return self._state_manager.get_state().entry_poc

    @property
    def entry_time_epoch(self) -> Optional[int]:
        return self._state_manager.get_state().entry_time_epoch

    @property
    def heat_start_epoch(self) -> Optional[int]:
        return self._state_manager.get_state().heat_start_epoch

    # -------------------- Properties for backward compatibility (end) ------------
