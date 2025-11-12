"""
Live Panel Module

Main Panel2 class for live trading metrics display.
Extracted from panels/panel2.py for modularity.

Architecture:
- Panel2: Main QWidget class
- Delegation to helper modules:
  * helpers: Utility functions
  * state_manager: State persistence
  * trade_handlers: Trade notifications
  * metrics_updater: Cell calculations

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
from services.trade_constants import COMM_PER_CONTRACT, DOLLARS_PER_POINT
from services.trade_math import TradeMath
from utils.format_utils import extract_symbol_display
from utils.logger import get_logger
from utils.theme_mixin import ThemeAwareMixin
from widgets.metric_cell import MetricCell

# Import helper modules
from panels.panel2 import state_manager, trade_handlers, metrics_updater

log = get_logger(__name__)

# -------------------- Constants & Config (start)
CSV_FEED_PATH = r"C:\Users\cgrah\Desktop\APPSIERRA\data\snapshot.csv"

CSV_REFRESH_MS = 500
TIMER_TICK_MS = 1000

HEAT_WARN_SEC = 3 * 60  # 3:00 m
HEAT_ALERT_FLASH_SEC = 4 * 60 + 30  # 4:30 m (start flashing)
HEAT_ALERT_SOLID_SEC = 5 * 60  # 5:00 m (red + flash remain)
# -------------------- Constants & Config (end)


# -------------------- Panel 2 Main (start)
class Panel2(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Panel 2 -- Live trading metrics, 3x5 grid layout. Live CSV feed (500 ms),
    Duration/Heat timers with persistence, state-change logging.
    """

    tradesChanged = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # CRITICAL: (mode, account) scoping
        self.current_mode: str = "SIM"
        self.current_account: str = ""

        self.symbol: str = "ES"  # Default symbol, updated via set_symbol()
        self.entry_price: Optional[float] = None  # NEVER pre-populated from cache
        self.entry_qty: int = 0  # NEVER pre-populated from cache
        self.is_long: Optional[bool] = None  # NEVER pre-populated from cache
        self.target_price: Optional[float] = None
        self.stop_price: Optional[float] = None

        # Feed state (live, continuously updated from CSV)
        self.last_price: Optional[float] = None
        self.session_high: Optional[float] = None
        self.session_low: Optional[float] = None
        self.vwap: Optional[float] = None
        self.cum_delta: Optional[float] = None
        self.poc: Optional[float] = None

        # Entry snapshots (captured once at position entry, static)
        self.entry_vwap: Optional[float] = None
        self.entry_delta: Optional[float] = None
        self.entry_poc: Optional[float] = None

        # Timer state (persisted)
        self.entry_time_epoch: Optional[int] = None  # when trade began
        self.heat_start_epoch: Optional[int] = None  # when drawdown began
        # Per-trade extremes for MAE/MFE
        self._trade_min_price: Optional[float] = None
        self._trade_max_price: Optional[float] = None

        # Timeframe state (for pills & pulsing dot)
        self._tf: str = "LIVE"
        self._pnl_up: Optional[bool] = None  # optional hint for pill color

        # Build UI and timers
        self._build()
        self._setup_timers()

        # Load scoped state after UI is built
        try:
            state_manager.load_state(self)
        except Exception as e:
            log.warning(f"[Panel2] Failed to load initial state: {e}")

        # First paint
        metrics_updater.refresh_all_cells(self, initial=True)

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

    def on_position_update(self, payload: dict) -> None:
        """
        Handle normalized PositionUpdate from DTC and mirror into local state.
        Delegates to trade_handlers module.

        Args:
            payload: Normalized position update dict from MessageRouter (lowercase keys)
        """
        trade_handlers.on_position_update(self, payload)

    # -------------------- Trade persistence hooks (end)

    # -------------------- UI Build (start)
    def _build(self):
        self.setObjectName("Panel2")
        self.setStyleSheet(f"QWidget#Panel2 {{ background:{THEME.get('bg_panel', '#0B0F14')}; }}")

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
        self.symbol_banner.setStyleSheet(f"color: {THEME.get('ink', '#E5E7EB')};")

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
        self.live_banner.setStyleSheet(f"color: {THEME.get('ink', '#E5E7EB')};")

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
        prev = (self.last_price, self.session_high, self.session_low, self.vwap, self.cum_delta)
        updated = self._read_snapshot_csv()
        if not updated:
            return

        # Log state changes only
        if self.vwap != prev[3]:
            log.info(f"[panel2] Feed updated -- VWAP changed: {self.vwap}")
        if self.cum_delta != prev[4]:
            log.info(f"[panel2] Feed updated -- Delta changed: {self.cum_delta}")

        # Track per-trade min/max while in position for MAE/MFE
        try:
            if self.entry_qty and self.last_price is not None:
                p = float(self.last_price)
                if self._trade_min_price is None or p < self._trade_min_price:
                    self._trade_min_price = p
                if self._trade_max_price is None or p > self._trade_max_price:
                    self._trade_max_price = p
        except Exception:
            pass

        # UI update
        metrics_updater.refresh_all_cells(self)

        # Proximity alerts
        metrics_updater.update_proximity_alerts(self)

        # Update the non-cell banner
        metrics_updater.update_live_banner(self)

    def _on_clock_tick(self):
        # Just update time/heat text and color thresholds every second
        metrics_updater.update_time_and_heat_cells(self)

    def _read_snapshot_csv(self) -> bool:
        """
        Header-aware CSV reader:
          - Expects header row: last,high,low,vwap,cum_delta,poc
          - Uses FIRST data row after the header (row 2)
          - Robust to BOM and column re-ordering
        """
        try:
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

                self.last_price = fnum("last")
                self.session_high = fnum("high")
                self.session_low = fnum("low")
                self.vwap = fnum("vwap")
                self.cum_delta = fnum("cum_delta")
                self.poc = fnum("poc")
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
        self.entry_qty = max(0, int(qty))

        # Start duration timer if entering a position
        if self.entry_qty > 0 and entry_price is not None:
            self.entry_price = float(entry_price)
            self.is_long = is_long
            if not self.entry_time_epoch:
                self.entry_time_epoch = int(time.time())
                # Capture VWAP, Delta, and POC snapshots at entry (static values)
                self.entry_vwap = self.vwap
                self.entry_delta = self.cum_delta
                self.entry_poc = self.poc
                # Initialize trade extremes to entry price (prevents premature MAE/MFE)
                self._trade_min_price = self.entry_price
                self._trade_max_price = self.entry_price

                # DEBUG: Comprehensive logging for entry snapshots
                log.info(f"[panel2] Position opened - Entry snapshots captured:")
                log.info(f"  Entry Price: {self.entry_price}")
                log.info(f"  Entry Qty: {self.entry_qty} ({'LONG' if self.is_long else 'SHORT'})")
                log.info(f"  Entry VWAP: {self.entry_vwap} (live vwap: {self.vwap})")
                log.info(f"  Entry Delta: {self.entry_delta} (live cum_delta: {self.cum_delta})")
                log.info(f"  Entry POC: {self.entry_poc} (live poc: {self.poc})")
                log.info(f"  Last Price: {self.last_price}")

                # CRITICAL: Warn if any snapshot is None
                if self.entry_vwap is None:
                    log.warning("[panel2] WARNING: entry_vwap is None - VWAP cell will not display!")
                if self.entry_delta is None:
                    log.warning("[panel2] WARNING: entry_delta is None - Delta cell will not display!")
                if self.entry_poc is None:
                    log.warning("[panel2] WARNING: entry_poc is None - POC cell will not display!")
        else:
            # No position - clear all position-specific data
            self.entry_price = None
            self.is_long = None
            self.target_price = None
            self.stop_price = None
            self.entry_vwap = None
            self.entry_delta = None
            self.entry_poc = None
            self.entry_time_epoch = None
            self.heat_start_epoch = None
            # Clear trade extremes (MAE/MFE tracking)
            self._trade_min_price = None
            self._trade_max_price = None
            log.info("[panel2] Position closed -- all position data cleared")
        state_manager.save_state(self)
        metrics_updater.refresh_all_cells(self)
        metrics_updater.update_live_banner(self)

    def set_targets(self, target_price: Optional[float], stop_price: Optional[float]):
        self.target_price = float(target_price) if target_price is not None else None
        self.stop_price = float(stop_price) if stop_price is not None else None
        metrics_updater.refresh_all_cells(self)
        metrics_updater.update_live_banner(self)

    def set_symbol(self, symbol: str):
        """
        Update the symbol label (called from DTC handshake or external source).
        Extracts 3-letter display symbol from full DTC symbol.
        Example: 'F.US.MESZ25' -> 'MES'
        """
        self.symbol = symbol.strip().upper() if symbol else "ES"
        # Extract display symbol (3 letters after "US.")
        display_sym = extract_symbol_display(self.symbol)
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
            metrics_updater.refresh_all_cells(self)
        except Exception:
            pass

    def get_current_trade_data(self) -> dict:
        """
        Expose current trade metrics for Panel 3 to grab directly.
        Returns all live trading data including P&L, MAE, MFE, R-multiple, etc.
        Panel 3 uses this for real-time statistical analysis before storage.
        """
        data = {
            "symbol": self.symbol,
            "entry_qty": self.entry_qty,
            "entry_price": self.entry_price,
            "is_long": self.is_long,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "last_price": self.last_price,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "vwap": self.vwap,
            "cum_delta": self.cum_delta,
            "entry_time_epoch": self.entry_time_epoch,
            "heat_start_epoch": self.heat_start_epoch,
            "trade_min_price": self._trade_min_price,
            "trade_max_price": self._trade_max_price,
        }

        # Calculate derived metrics if we have an active position
        if self.entry_qty and self.entry_price is not None and self.last_price is not None:
            # P&L calculation
            sign = 1 if self.is_long else -1
            pnl_pts = (self.last_price - self.entry_price) * sign
            gross_pnl = pnl_pts * DOLLARS_PER_POINT * self.entry_qty
            comm = COMM_PER_CONTRACT * self.entry_qty
            net_pnl = gross_pnl - comm

            data["pnl_points"] = pnl_pts
            data["gross_pnl"] = gross_pnl
            data["commissions"] = comm
            data["net_pnl"] = net_pnl

            # MAE/MFE from TRADE extremes (not session extremes)
            # LONG: MAE from min (adverse), MFE from max (favorable)
            # SHORT: MAE from max (adverse), MFE from min (favorable)
            # These track min/max SINCE position entry, not session-wide
            if self._trade_min_price is not None and self._trade_max_price is not None:
                # Use centralized TradeMath calculation
                mae_pts, mfe_pts = TradeMath.calculate_mae_mfe(
                    entry_price=self.entry_price,
                    trade_min_price=self._trade_min_price,
                    trade_max_price=self._trade_max_price,
                    is_long=self.is_long,
                )

                if mae_pts is not None and mfe_pts is not None:
                    data["mae_points"] = mae_pts
                    data["mfe_points"] = mfe_pts
                    data["mae_dollars"] = mae_pts * DOLLARS_PER_POINT * self.entry_qty
                    data["mfe_dollars"] = mfe_pts * DOLLARS_PER_POINT * self.entry_qty

                # Calculate efficiency: (realized PnL / MFE) if MFE > 0
                if mfe_pts > 0 and "net_pnl" in data:
                    # Efficiency = realized profit / maximum potential profit
                    # Expressed as percentage (0.0 to 1.0, where 1.0 = 100% efficient)
                    efficiency = min(1.0, max(0.0, data["net_pnl"] / (mfe_pts * DOLLARS_PER_POINT * self.entry_qty)))
                    data["efficiency"] = efficiency
                else:
                    data["efficiency"] = None

            # R-multiple
            if self.stop_price is not None and float(self.stop_price) > 0:
                risk_per_contract = abs(self.entry_price - float(self.stop_price)) * DOLLARS_PER_POINT
                if risk_per_contract > 0:
                    r_multiple = net_pnl / (risk_per_contract * self.entry_qty)
                    data["r_multiple"] = r_multiple

            # Duration
            if self.entry_time_epoch:
                data["duration_seconds"] = int(time.time() - self.entry_time_epoch)

            # Heat duration
            if self.heat_start_epoch:
                data["heat_seconds"] = int(time.time() - self.heat_start_epoch)

        return data

    def get_live_feed_data(self) -> dict:
        """
        Expose current CSV feed data for Panel 3 analysis.
        Returns live market data: price, high, low, vwap, delta.
        """
        return {
            "last_price": self.last_price,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "vwap": self.vwap,
            "cum_delta": self.cum_delta,
        }

    def get_trade_state(self) -> dict:
        """
        Expose position state for Panel 3 queries.
        Returns basic position information: qty, entry, direction, targets.
        """
        return {
            "symbol": self.symbol,
            "qty": self.entry_qty,
            "entry_price": self.entry_price,
            "is_long": self.is_long,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "has_position": bool(self.entry_qty and self.entry_qty > 0),
        }

    def has_active_position(self) -> bool:
        """Quick check if there's an active trade for Panel 3 to analyze."""
        return bool(self.entry_qty and self.entry_qty > 0 and self.entry_price is not None)

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
        state_manager.save_state(self)
        super().closeEvent(ev)
