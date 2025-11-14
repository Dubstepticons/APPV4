"""
panels/panel2/position_display.py

Position display rendering for Panel2 - Pure UI layer.

This module handles rendering the 3x5 grid of metric cells and banners.
It's a pure rendering layer with no business logic - just takes state
and metrics and updates the UI.

Architecture:
- Input: PositionState + metrics dict
- Output: UI updates (MetricCell instances)
- No business logic (pure rendering)
- No state mutations (read-only)
- Theme-aware styling

Grid Layout (3 rows × 5 columns):
    Row 1: Price, Heat, Time, Target, Stop
    Row 2: Risk, R-Mult, Range, MAE, MFE
    Row 3: VWAP, Delta, POC, Efficiency, Pts

Usage:
    from panels.panel2.position_display import PositionDisplay
    from panels.panel2.position_state import PositionState
    from panels.panel2.metrics_calculator import MetricsCalculator

    display = PositionDisplay(metric_cells, banners)

    # Update display from state
    state = PositionState(...)
    metrics = MetricsCalculator.calculate_all(state)
    display.update(state, metrics, current_epoch=time.time())
"""

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from config.theme import THEME, ColorTheme

import structlog

if TYPE_CHECKING:
    from panels.panel2.position_state import PositionState
    from widgets.metric_cell import MetricCell

log = structlog.get_logger(__name__)


class PositionDisplay:
    """
    Pure rendering layer for Panel2 metrics display.

    Takes PositionState and metrics dict, updates UI cells.
    No business logic, no state mutations.
    """

    def __init__(
        self,
        # Row 1
        c_price: "MetricCell",
        c_heat: "MetricCell",
        c_time: "MetricCell",
        c_target: "MetricCell",
        c_stop: "MetricCell",
        # Row 2
        c_risk: "MetricCell",
        c_rmult: "MetricCell",
        c_range: "MetricCell",
        c_mae: "MetricCell",
        c_mfe: "MetricCell",
        # Row 3
        c_vwap: "MetricCell",
        c_delta: "MetricCell",
        c_poc: "MetricCell",
        c_eff: "MetricCell",
        c_pts: "MetricCell",
        # Banners
        symbol_banner=None,
        live_banner=None,
    ):
        """
        Initialize position display.

        Args:
            c_price, c_heat, c_time, c_target, c_stop: Row 1 cells
            c_risk, c_rmult, c_range, c_mae, c_mfe: Row 2 cells
            c_vwap, c_delta, c_poc, c_eff, c_pts: Row 3 cells
            symbol_banner: Symbol label (optional)
            live_banner: Live price label (optional)
        """
        # Row 1
        self.c_price = c_price
        self.c_heat = c_heat
        self.c_time = c_time
        self.c_target = c_target
        self.c_stop = c_stop

        # Row 2
        self.c_risk = c_risk
        self.c_rmult = c_rmult
        self.c_range = c_range
        self.c_mae = c_mae
        self.c_mfe = c_mfe

        # Row 3
        self.c_vwap = c_vwap
        self.c_delta = c_delta
        self.c_poc = c_poc
        self.c_eff = c_eff
        self.c_pts = c_pts

        # Banners
        self.symbol_banner = symbol_banner
        self.live_banner = live_banner

        log.info("[PositionDisplay] Initialized with 15 metric cells")

    def update(
        self,
        state: "PositionState",
        metrics: dict,
        current_epoch: Optional[int] = None
    ) -> None:
        """
        Update all cells from position state and metrics.

        This is the main entry point - takes state and metrics,
        updates all UI cells.

        Args:
            state: Position state snapshot
            metrics: Metrics dict from MetricsCalculator
            current_epoch: Current Unix timestamp (for time calculations)
        """
        if state.is_flat():
            self._render_flat()
        else:
            self._render_position(state, metrics, current_epoch)

        # Always update banners
        self._update_banners(state)

    def _render_flat(self) -> None:
        """
        Render flat state (no position) - all cells show "--".
        """
        dim_color = THEME.get("text_dim", "#5B6C7A")

        # Set all 15 cells to "--"
        cells = [
            self.c_price, self.c_heat, self.c_time, self.c_target, self.c_stop,
            self.c_risk, self.c_rmult, self.c_range, self.c_mae, self.c_mfe,
            self.c_vwap, self.c_delta, self.c_poc, self.c_eff, self.c_pts
        ]

        for cell in cells:
            cell.set_value_text("--")
            cell.set_value_color(dim_color)
            if hasattr(cell, 'stop_flashing'):
                cell.stop_flashing()

    def _render_position(
        self,
        state: "PositionState",
        metrics: dict,
        current_epoch: Optional[int]
    ) -> None:
        """
        Render active position state.

        Args:
            state: Position state
            metrics: Calculated metrics
            current_epoch: Current Unix timestamp
        """
        # Row 1
        self._update_price_cell(state)
        self._update_heat_cell(state, current_epoch)
        self._update_time_cell(state, current_epoch)
        self._update_target_cell(state)
        self._update_stop_cell(state)

        # Row 2
        self._update_risk_cell(state, metrics)
        self._update_rmult_cell(state, metrics)
        self._update_range_cell(state)
        self._update_mae_cell(state, metrics)
        self._update_mfe_cell(state, metrics)

        # Row 3
        self._update_vwap_cell(state, metrics)
        self._update_delta_cell(state)
        self._update_poc_cell(state)
        self._update_efficiency_cell(state, metrics)
        self._update_pts_cell(state)

    # =========================================================================
    # ROW 1: Price, Heat, Time, Target, Stop
    # =========================================================================

    def _update_price_cell(self, state: "PositionState") -> None:
        """Update price cell: "QTY @ ENTRY"."""
        text = f"{state.entry_qty} @ {state.entry_price:.2f}"
        color = ColorTheme.pnl_color_from_direction(state.is_long)

        self.c_price.set_value_text(text)
        self.c_price.set_value_color(color)

    def _update_heat_cell(
        self,
        state: "PositionState",
        current_epoch: Optional[int]
    ) -> None:
        """
        Update heat cell with time in drawdown.

        Heat thresholds:
        - < 3:00m: Dim (no heat)
        - >= 3:00m: Yellow warning
        - >= 4:30m: Red + flashing alert
        - >= 5:00m: Red + flashing critical
        """
        from panels.panel2.visual_indicators import VisualIndicators, format_heat_time

        heat_duration = None
        if current_epoch and state.heat_start_epoch:
            heat_duration = current_epoch - state.heat_start_epoch

        # Format text
        text = format_heat_time(heat_duration)
        self.c_heat.set_value_text(text)

        # Determine color and flashing
        indicators = VisualIndicators()
        color_name = indicators.get_heat_color(heat_duration)
        should_flash = indicators.should_flash_heat(heat_duration)

        # Map color name to theme color
        if color_name == "yellow":
            color = THEME.get("accent_warning", "#F59E0B")
        elif color_name == "red":
            color = THEME.get("accent_alert", "#DC2626")
        else:  # white/dim
            color = THEME.get("text_dim", "#5B6C7A")

        self.c_heat.set_value_color(color)

        if should_flash:
            self.c_heat.start_flashing(border_color=color)
        else:
            self.c_heat.stop_flashing()

    def _update_time_cell(
        self,
        state: "PositionState",
        current_epoch: Optional[int]
    ) -> None:
        """Update time cell with duration in trade."""
        from panels.panel2.metrics_calculator import format_time

        time_in_trade = None
        if current_epoch and state.entry_time_epoch:
            time_in_trade = current_epoch - state.entry_time_epoch

        text = format_time(time_in_trade)
        color = THEME.get("text_primary", "#E6F6FF") if time_in_trade else THEME.get("text_dim", "#5B6C7A")

        self.c_time.set_value_text(text)
        self.c_time.set_value_color(color)

    def _update_target_cell(self, state: "PositionState") -> None:
        """Update target cell."""
        if state.target_price is not None:
            self.c_target.set_value_text(f"{state.target_price:.2f}")
            self.c_target.set_value_color(THEME.get("text_primary", "#E6F6FF"))
        else:
            self.c_target.set_value_text("--")
            self.c_target.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_stop_cell(self, state: "PositionState") -> None:
        """
        Update stop cell.

        Flashes red when price within 1pt of stop (proximity alert).
        """
        from panels.panel2.visual_indicators import VisualIndicators, get_stop_proximity_color

        if state.stop_price is not None:
            self.c_stop.set_value_text(f"{state.stop_price:.2f}")

            # Check proximity
            indicators = VisualIndicators()
            should_flash = indicators.should_flash_stop(state)
            color_name = get_stop_proximity_color(state)

            if color_name == "red":
                color = THEME.get("accent_alert", "#DC2626")
                self.c_stop.set_value_color(color)
                if should_flash:
                    self.c_stop.start_flashing()
            else:
                color = THEME.get("text_primary", "#E6F6FF")
                self.c_stop.set_value_color(color)
                self.c_stop.stop_flashing()
        else:
            self.c_stop.set_value_text("--")
            self.c_stop.set_value_color(THEME.get("text_dim", "#5B6C7A"))
            self.c_stop.stop_flashing()

    # =========================================================================
    # ROW 2: Risk, R-Mult, Range, MAE, MFE
    # =========================================================================

    def _update_risk_cell(self, state: "PositionState", metrics: dict) -> None:
        """Update risk cell (planned risk in dollars)."""
        from panels.panel2.metrics_calculator import format_pnl

        risk = metrics.get("risk_amount")

        if risk is not None:
            # Risk is always shown as red (negative)
            self.c_risk.set_value_text(f"${risk:,.2f}")
            self.c_risk.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
        else:
            self.c_risk.set_value_text("--")
            self.c_risk.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_rmult_cell(self, state: "PositionState", metrics: dict) -> None:
        """Update R-multiple cell."""
        from panels.panel2.metrics_calculator import format_r_multiple

        r_mult = metrics.get("r_multiple")

        if r_mult is not None:
            text = format_r_multiple(r_mult)
            self.c_rmult.set_value_text(text)

            # Color by sign
            if r_mult > 0:
                color = THEME.get("pnl_pos_color", "#22C55E")
            elif r_mult < 0:
                color = THEME.get("pnl_neg_color", "#EF4444")
            else:
                color = THEME.get("pnl_neu_color", "#C9CDD0")

            self.c_rmult.set_value_color(color)
        else:
            self.c_rmult.set_value_text("--")
            self.c_rmult.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_range_cell(self, state: "PositionState") -> None:
        """Update range cell (distance to target in points)."""
        from panels.panel2.metrics_calculator import format_points

        if state.target_price is not None and state.last_price:
            # Distance to target (signed)
            dist = (state.target_price - state.last_price) * (1 if state.is_long else -1)

            text = format_points(dist, show_sign=True) + " pt"
            self.c_range.set_value_text(text)

            # Color by sign (green if positive distance, red if negative)
            if dist > 0:
                color = THEME.get("pnl_pos_color", "#22C55E")
            elif dist < 0:
                color = THEME.get("pnl_neg_color", "#EF4444")
            else:
                color = THEME.get("pnl_neu_color", "#C9CDD0")

            self.c_range.set_value_color(color)
        else:
            self.c_range.set_value_text("--")
            self.c_range.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_mae_cell(self, state: "PositionState", metrics: dict) -> None:
        """Update MAE cell (Maximum Adverse Excursion)."""
        from panels.panel2.metrics_calculator import format_pnl

        mae = metrics.get("mae")

        if mae is not None:
            text = format_pnl(mae)
            self.c_mae.set_value_text(text)
            # MAE is always red (adverse)
            self.c_mae.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
        else:
            self.c_mae.set_value_text("--")
            self.c_mae.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_mfe_cell(self, state: "PositionState", metrics: dict) -> None:
        """Update MFE cell (Maximum Favorable Excursion)."""
        from panels.panel2.metrics_calculator import format_pnl

        mfe = metrics.get("mfe")

        if mfe is not None:
            text = format_pnl(mfe)
            self.c_mfe.set_value_text(text)
            # MFE is always green (favorable)
            self.c_mfe.set_value_color(THEME.get("pnl_pos_color", "#22C55E"))
        else:
            self.c_mfe.set_value_text("--")
            self.c_mfe.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # =========================================================================
    # ROW 3: VWAP, Delta, POC, Efficiency, Pts
    # =========================================================================

    def _update_vwap_cell(self, state: "PositionState", metrics: dict) -> None:
        """Update VWAP cell (distance from VWAP)."""
        from panels.panel2.metrics_calculator import format_points

        vwap_dist = metrics.get("vwap_distance")

        if vwap_dist is not None and state.vwap != 0:
            text = format_points(vwap_dist, show_sign=True)
            self.c_vwap.set_value_text(text)

            # Color by position relative to VWAP
            if state.is_long:
                # Long: want to be above VWAP (positive distance = green)
                color = THEME.get("pnl_pos_color", "#22C55E") if vwap_dist > 0 else THEME.get("pnl_neg_color", "#EF4444")
            else:
                # Short: want to be below VWAP (negative distance = green)
                color = THEME.get("pnl_pos_color", "#22C55E") if vwap_dist < 0 else THEME.get("pnl_neg_color", "#EF4444")

            self.c_vwap.set_value_color(color)
        else:
            self.c_vwap.set_value_text("--")
            self.c_vwap.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_delta_cell(self, state: "PositionState") -> None:
        """Update cumulative delta cell."""
        if state.cum_delta != 0:
            # Format with sign
            text = f"{state.cum_delta:+,.0f}"
            self.c_delta.set_value_text(text)

            # Color by delta sign
            if state.cum_delta > 0:
                color = THEME.get("pnl_pos_color", "#22C55E")
            elif state.cum_delta < 0:
                color = THEME.get("pnl_neg_color", "#EF4444")
            else:
                color = THEME.get("pnl_neu_color", "#C9CDD0")

            self.c_delta.set_value_color(color)
        else:
            self.c_delta.set_value_text("--")
            self.c_delta.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_poc_cell(self, state: "PositionState") -> None:
        """Update POC cell (Point of Control)."""
        if state.poc != 0:
            self.c_poc.set_value_text(f"{state.poc:.2f}")

            # Color based on position relative to POC
            if state.last_price and state.last_price > state.poc:
                # Above POC
                color = THEME.get("pnl_pos_color", "#22C55E") if state.is_long else THEME.get("pnl_neg_color", "#EF4444")
            elif state.last_price and state.last_price < state.poc:
                # Below POC
                color = THEME.get("pnl_neg_color", "#EF4444") if state.is_long else THEME.get("pnl_pos_color", "#22C55E")
            else:
                color = THEME.get("pnl_neu_color", "#C9CDD0")

            self.c_poc.set_value_color(color)
        else:
            self.c_poc.set_value_text("--")
            self.c_poc.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_efficiency_cell(self, state: "PositionState", metrics: dict) -> None:
        """Update efficiency cell (Current P&L / MFE)."""
        from panels.panel2.metrics_calculator import format_efficiency

        efficiency = metrics.get("efficiency")

        if efficiency is not None:
            text = format_efficiency(efficiency)
            self.c_eff.set_value_text(text)

            # Color by efficiency (green if high, red if low)
            if efficiency >= 75:
                color = THEME.get("pnl_pos_color", "#22C55E")
            elif efficiency <= 25:
                color = THEME.get("pnl_neg_color", "#EF4444")
            else:
                color = THEME.get("pnl_neu_color", "#C9CDD0")

            self.c_eff.set_value_color(color)
        else:
            self.c_eff.set_value_text("--")
            self.c_eff.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def _update_pts_cell(self, state: "PositionState") -> None:
        """Update points cell (points moved from entry)."""
        from panels.panel2.metrics_calculator import format_points

        if state.last_price and state.entry_price:
            # Points moved (signed)
            direction = 1 if state.is_long else -1
            pts = (state.last_price - state.entry_price) * direction

            text = format_points(pts, show_sign=True)
            self.c_pts.set_value_text(text)

            # Color by sign
            if pts > 0:
                color = THEME.get("pnl_pos_color", "#22C55E")
            elif pts < 0:
                color = THEME.get("pnl_neg_color", "#EF4444")
            else:
                color = THEME.get("pnl_neu_color", "#C9CDD0")

            self.c_pts.set_value_color(color)
        else:
            self.c_pts.set_value_text("--")
            self.c_pts.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # =========================================================================
    # BANNERS (Symbol & Live Price)
    # =========================================================================

    def _update_banners(self, state: "PositionState") -> None:
        """Update symbol and live price banners."""
        if not self.symbol_banner or not self.live_banner:
            return

        # Symbol banner
        if state.has_position():
            self.symbol_banner.setText(state.symbol)
        else:
            self.symbol_banner.setText("--")

        # Live price banner
        if state.has_position():
            if state.last_price:
                self.live_banner.setText(f"{state.last_price:.2f}")
            else:
                self.live_banner.setText("--")
        else:
            self.live_banner.setText("FLAT")
