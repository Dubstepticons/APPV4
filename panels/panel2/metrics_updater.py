"""
Metrics Updater Module

Handles live metrics calculation and cell updates for Panel2 (Trading panel).
Extracted from panels/panel2.py for modularity.

Functions:
- refresh_all_cells(): Orchestrate all cell updates
- update_price_cell(): Update qty @ entry display
- update_time_and_heat_cells(): Duration and heat state machine
- update_target_stop_cells(): Target and stop prices with proximity alerts
- update_secondary_metrics(): Complex metrics (R-multiple, MAE/MFE, efficiency, etc.)
- update_live_banner(): Symbol and live price banner
- update_proximity_alerts(): Proximity warnings
- update_heat_state_transitions(): Heat state machine transitions

Constants:
- HEAT_WARN_SEC: 3 minutes (warning threshold)
- HEAT_ALERT_FLASH_SEC: 4:30 minutes (start flashing)
- HEAT_ALERT_SOLID_SEC: 5 minutes (solid red + flash)
"""

import time
from typing import Optional
from config.theme import THEME, ColorTheme
from services.trade_constants import COMM_PER_CONTRACT, DOLLARS_PER_POINT
from services.trade_math import TradeMath
from utils.logger import get_logger

log = get_logger(__name__)

# Heat thresholds
HEAT_WARN_SEC = 3 * 60  # 3:00 m
HEAT_ALERT_FLASH_SEC = 4 * 60 + 30  # 4:30 m (start flashing)
HEAT_ALERT_SOLID_SEC = 5 * 60  # 5:00 m (red + flash remain)


def refresh_all_cells(panel, initial: bool = False) -> None:
    """
    Orchestrate refresh of all metric cells.

    If flat (no position), sets all cells to dashes.
    If in position, calculates and updates all metrics.

    Args:
        panel: Panel2 instance
        initial: True if this is the initial UI setup
    """
    # If flat (no position), set all cells to dashes and exit
    if not (getattr(panel, "entry_qty", 0) and panel.entry_price is not None):
        dim_color = THEME.get("text_dim", "#5B6C7A")
        # Set all 15 cells to "--"
        panel.c_price.set_value_text("--")
        panel.c_price.set_value_color(dim_color)
        panel.c_heat.set_value_text("--")
        panel.c_heat.set_value_color(dim_color)
        panel.c_heat.stop_flashing()
        panel.c_time.set_value_text("--")
        panel.c_time.set_value_color(dim_color)
        panel.c_target.set_value_text("--")
        panel.c_target.set_value_color(dim_color)
        panel.c_stop.set_value_text("--")
        panel.c_stop.set_value_color(dim_color)
        panel.c_stop.stop_flashing()
        panel.c_risk.set_value_text("--")
        panel.c_risk.set_value_color(dim_color)
        panel.c_rmult.set_value_text("--")
        panel.c_rmult.set_value_color(dim_color)
        panel.c_range.set_value_text("--")
        panel.c_range.set_value_color(dim_color)
        panel.c_mae.set_value_text("--")
        panel.c_mae.set_value_color(dim_color)
        panel.c_mfe.set_value_text("--")
        panel.c_mfe.set_value_color(dim_color)
        panel.c_vwap.set_value_text("--")
        panel.c_vwap.set_value_color(dim_color)
        panel.c_delta.set_value_text("--")
        panel.c_delta.set_value_color(dim_color)
        panel.c_poc.set_value_text("--")
        panel.c_poc.set_value_color(dim_color)
        panel.c_eff.set_value_text("--")
        panel.c_eff.set_value_color(dim_color)
        panel.c_pts.set_value_text("--")
        panel.c_pts.set_value_color(dim_color)

        # Update banner to show "LIVE POSITION" and "FLAT"
        update_live_banner(panel)
        return

    # Only calculate values if we have a position
    # Price cell: "QTY @ ENTRY" all green/red by direction
    update_price_cell(panel)

    # Time & Heat (text & color thresholds)
    update_time_and_heat_cells(panel)

    # Target / Stop (and stop flashing if within 1.0 pt)
    update_target_stop_cells(panel)

    # Risk, R, Range, MAE, MFE, VWAP, Delta, Efficiency, Pts, $PnL
    update_secondary_metrics(panel)

    # Keep the banner in sync with the latest price
    update_live_banner(panel)

    if initial:
        log.info("[panel2] UI initialized -- metrics grid active")


def update_price_cell(panel) -> None:
    """
    Update price cell with qty @ entry price.

    Color: Green for long, red for short.

    Args:
        panel: Panel2 instance
    """
    # Position guaranteed to exist when this is called
    txt = f"{panel.entry_qty} @ {panel.entry_price:.2f}"
    color = ColorTheme.pnl_color_from_direction(panel.is_long)
    panel.c_price.set_value_text(txt)
    panel.c_price.set_value_color(color)


def update_time_and_heat_cells(panel) -> None:
    """
    Update duration and heat cells.

    Duration: Time since entry
    Heat: Time spent in drawdown (below entry for long, above for short)

    Heat state machine:
    - OFF (< 3:00): dim color, no flash
    - WARNING (3:00 - 4:30): orange color, no flash
    - ALERT FLASH (4:30 - 5:00): orange color, flashing border
    - ALERT SOLID (>= 5:00): red color, flashing border

    Args:
        panel: Panel2 instance
    """
    # Duration
    if panel.entry_time_epoch:
        dur_sec = int(time.time() - panel.entry_time_epoch)
        panel.c_time.set_value_text(TradeMath.fmt_time_human(dur_sec))
        panel.c_time.set_value_color(THEME.get("text_primary", "#E6F6FF"))
    else:
        panel.c_time.set_value_text("--")
        panel.c_time.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # Heat: measured only when in drawdown relative to entry
    has_position = bool(getattr(panel, "entry_qty", 0) and panel.entry_qty > 0)

    if not has_position:
        # No position - show "--"
        panel.c_heat.set_value_text("--")
        panel.c_heat.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        panel.c_heat.stop_flashing()
    else:
        # In position - calculate and display heat
        heat_sec = 0
        if panel.entry_price is not None and panel.last_price is not None and panel.is_long is not None:
            in_dd = (panel.last_price < panel.entry_price) if panel.is_long else (panel.last_price > panel.entry_price)
            if in_dd:
                if panel.heat_start_epoch is None:
                    panel.heat_start_epoch = int(time.time())
                    log.info("[panel2] Heat timer started (drawdown detected)")
            else:
                if panel.heat_start_epoch is not None:
                    log.info("[panel2] Heat timer paused (drawdown ended)")
                panel.heat_start_epoch = None

        if panel.heat_start_epoch is not None:
            heat_sec = int(time.time() - panel.heat_start_epoch)

        panel.c_heat.set_value_text(TradeMath.fmt_time_human(heat_sec))

        # Heat color/flash thresholds
        if heat_sec == 0 or heat_sec < HEAT_WARN_SEC:
            panel.c_heat.set_value_color(THEME.get("text_dim", "#5B6C7A"))
            panel.c_heat.stop_flashing()
        elif heat_sec < HEAT_ALERT_FLASH_SEC:
            panel.c_heat.set_value_color(THEME.get("accent_warning", "#F59E0B"))
            panel.c_heat.stop_flashing()
        else:
            # Flash with border color matching text color
            if heat_sec >= HEAT_ALERT_SOLID_SEC:
                flash_color = THEME.get("accent_alert", "#DC2626")
                panel.c_heat.set_value_color(flash_color)
                panel.c_heat.start_flashing(border_color=flash_color)
            else:
                flash_color = THEME.get("accent_warning", "#F59E0B")
                panel.c_heat.set_value_color(flash_color)
                panel.c_heat.start_flashing(border_color=flash_color)


def update_target_stop_cells(panel) -> None:
    """
    Update target and stop cells with proximity alerts.

    Target: Show target price
    Stop: Show stop price, flash red when within 1.0 point

    Args:
        panel: Panel2 instance
    """
    # Target
    if panel.target_price is not None:
        panel.c_target.set_value_text(f"{panel.target_price:.2f}")
        panel.c_target.set_value_color(THEME.get("text_primary", "#E6F6FF"))
    else:
        panel.c_target.set_value_text("--")
        panel.c_target.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # Stop (flash when price within 1.0 point of stop)
    if panel.stop_price is not None:
        panel.c_stop.set_value_text(f"{panel.stop_price:.2f}")
        near = False
        if panel.last_price is not None and abs(panel.last_price - panel.stop_price) <= 1.0:
            near = True
        if near:
            panel.c_stop.set_value_color(THEME.get("accent_alert", "#DC2626"))
            panel.c_stop.start_flashing()
        else:
            panel.c_stop.set_value_color(THEME.get("text_primary", "#E6F6FF"))
            panel.c_stop.stop_flashing()
    else:
        panel.c_stop.set_value_text("--")
        panel.c_stop.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        panel.c_stop.stop_flashing()


def update_secondary_metrics(panel) -> None:
    """
    Update all secondary metrics cells.

    Metrics calculated:
    - Risk: Planned risk in dollars (|entry - stop| * $50/pt * qty + commission)
    - R-Multiple: Current R-multiple ((current - entry) / (entry - stop))
    - Range: Distance to target in points
    - MAE/MFE: Maximum adverse/favorable excursion in points
    - VWAP: Volume-weighted average price at entry
    - Delta: Cumulative delta at entry
    - Efficiency: P&L / MFE (how much of potential was captured)
    - Points P&L: P&L in points
    - POC: Point of control at entry

    Args:
        panel: Panel2 instance
    """
    # Position guaranteed to exist when this is called

    # CRITICAL: Validate that we have all necessary data from PositionUpdate
    # before calculating risk metrics (entry_price, stop_price, target_price)
    if panel.entry_price is None:
        # No entry price from PositionUpdate - cannot calculate risk
        panel.c_risk.set_value_text("--")
        panel.c_risk.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        panel.c_rmult.set_value_text("--")
        panel.c_rmult.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        return

    # Planned Risk (always red, no negative sign shown)
    # Formula: |entry - stop| * $50/point * qty + commission
    if panel.stop_price is not None:
        dist_pts = abs(panel.entry_price - panel.stop_price)
        dollars = dist_pts * DOLLARS_PER_POINT * panel.entry_qty
        comm = COMM_PER_CONTRACT * panel.entry_qty
        planned = dollars + comm
        panel.c_risk.set_value_text(f"${planned:,.2f}")
        panel.c_risk.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
    else:
        panel.c_risk.set_value_text("--")
        panel.c_risk.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # R-Multiple = (Current - Entry) / (Entry - Stop)
    # Only calculate if we have all required values from PositionUpdate
    if panel.stop_price is not None and panel.last_price is not None and panel.entry_price is not None:
        denom = panel.entry_price - panel.stop_price
        if abs(denom) > 1e-9:
            r_mult = (panel.last_price - panel.entry_price) / denom
            panel.c_rmult.set_value_text(f"{r_mult:.2f} R")
            if r_mult > 0:
                panel.c_rmult.set_value_color(THEME.get("pnl_pos_color", "#22C55E"))
            elif r_mult < 0:
                panel.c_rmult.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
            else:
                panel.c_rmult.set_value_color(THEME.get("pnl_neu_color", "#C9CDD0"))
        else:
            panel.c_rmult.set_value_text("--")
            panel.c_rmult.set_value_color(THEME.get("text_dim", "#5B6C7A"))
    else:
        panel.c_rmult.set_value_text("--")
        panel.c_rmult.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # Range = distance from target compared to live price (signed with +/−)
    if panel.target_price is not None and panel.last_price is not None:
        dist = (panel.target_price - panel.last_price) * (1 if panel.is_long else -1)
        sign_char = "+" if dist >= 0 else "-"
        panel.c_range.set_value_text(f"{sign_char}{abs(dist):.2f} pt")
        panel.c_range.set_value_color(THEME.get("text_primary", "#E6F6FF"))
    else:
        panel.c_range.set_value_text("--")
        panel.c_range.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # MAE / MFE using TradeMath
    mae_pts, mfe_pts = TradeMath.calculate_mae_mfe(
        entry_price=panel.entry_price,
        trade_min_price=panel._trade_min_price,
        trade_max_price=panel._trade_max_price,
        is_long=panel.is_long,
    )
    if mae_pts is not None and mfe_pts is not None:
        panel.c_mae.set_value_text(f"{mae_pts:.2f} pt")
        panel.c_mae.set_value_color(THEME.get("pnl_neg_color", "#EF4444") if mae_pts < 0 else THEME.get("pnl_neu_color", "#C9CDD0"))

        panel.c_mfe.set_value_text(f"{mfe_pts:.2f} pt")
        panel.c_mfe.set_value_color(THEME.get("pnl_pos_color", "#22C55E") if mfe_pts > 0 else THEME.get("pnl_neu_color", "#C9CDD0"))
    else:
        panel.c_mae.set_value_text("--")
        panel.c_mae.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        panel.c_mfe.set_value_text("--")
        panel.c_mfe.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # VWAP (static snapshot from entry) - only show when in position
    has_position = bool(getattr(panel, "entry_qty", 0) and panel.entry_qty > 0)
    if has_position and panel.entry_vwap is not None:
        panel.c_vwap.set_value_text(f"{panel.entry_vwap:.2f}")
        color = THEME.get("text_primary", "#E6F6FF")
        if panel.entry_price is not None and panel.is_long is not None:
            if panel.is_long:
                color = (
                    THEME.get("pnl_neg_color", "#EF4444") if panel.entry_vwap > panel.entry_price else THEME.get("pnl_pos_color", "#22C55E")
                )
            else:
                color = (
                    THEME.get("pnl_pos_color", "#22C55E") if panel.entry_vwap > panel.entry_price else THEME.get("pnl_neg_color", "#EF4444")
                )
        panel.c_vwap.set_value_color(color)
    else:
        panel.c_vwap.set_value_text("--")
        panel.c_vwap.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # Delta (static snapshot from entry) - only show when in position
    if has_position and panel.entry_delta is not None:
        panel.c_delta.set_value_text(f"{panel.entry_delta:,.0f}")
        if panel.entry_delta > 0:
            panel.c_delta.set_value_color(THEME.get("pnl_pos_color", "#22C55E"))
        elif panel.entry_delta < 0:
            panel.c_delta.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
        else:
            panel.c_delta.set_value_color(THEME.get("pnl_neu_color", "#C9CDD0"))
    else:
        panel.c_delta.set_value_text("--")
        panel.c_delta.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # Efficiency = PnL / MFE_value; show 0 if MFE <= 0
    # Position guaranteed, so entry_price, last_price, is_long exist
    # Uses TRADE max price (not session high) for accurate MFE
    eff_val: Optional[float] = None
    if panel.last_price is not None:
        # Calculate current P&L in points
        pnl_pts = (panel.last_price - panel.entry_price) if panel.is_long else (panel.entry_price - panel.last_price)

        # Get MFE using TradeMath
        _, mfe_pts = TradeMath.calculate_mae_mfe(
            entry_price=panel.entry_price,
            trade_min_price=panel._trade_min_price,
            trade_max_price=panel._trade_max_price,
            is_long=panel.is_long,
        )

        # Calculate efficiency if MFE is positive
        if mfe_pts is not None and mfe_pts > 1e-9:
            eff_val = pnl_pts / mfe_pts

    if eff_val is None:
        panel.c_eff.set_value_text("--")
        panel.c_eff.set_value_color(THEME.get("text_dim", "#5B6C7A"))
    else:
        panel.c_eff.set_value_text(f"{eff_val:.2f}")
        if eff_val > 0.6:
            panel.c_eff.set_value_color(THEME.get("pnl_pos_color", "#22C55E"))
        elif eff_val >= 0.3:
            panel.c_eff.set_value_color(THEME.get("accent_warning", "#F59E0B"))
        else:
            panel.c_eff.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))

    # Points PnL
    # Position guaranteed, so entry_price, is_long exist
    if panel.last_price is not None:
        pnl_pts = (panel.last_price - panel.entry_price) * (1 if panel.is_long else -1)
        sign_char = "+" if pnl_pts >= 0 else "-"
        panel.c_pts.set_value_text(f"{sign_char}{abs(pnl_pts):.2f} pt")
        panel.c_pts.set_value_color(ColorTheme.pnl_color_from_value(pnl_pts))
    else:
        panel.c_pts.set_value_text("--")
        panel.c_pts.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    # POC (static snapshot from entry) - only show when in position
    # Uses same color logic as VWAP (quality signal based on entry vs POC)
    if has_position and panel.entry_poc is not None:
        panel.c_poc.set_value_text(f"{panel.entry_poc:.2f}")
        color = THEME.get("text_primary", "#E6F6FF")
        if panel.entry_price is not None and panel.is_long is not None:
            if panel.is_long:
                color = (
                    THEME.get("pnl_neg_color", "#EF4444") if panel.entry_poc > panel.entry_price else THEME.get("pnl_pos_color", "#22C55E")
                )
            else:
                color = (
                    THEME.get("pnl_pos_color", "#22C55E") if panel.entry_poc > panel.entry_price else THEME.get("pnl_neg_color", "#EF4444")
                )
        panel.c_poc.set_value_color(color)
    else:
        panel.c_poc.set_value_text("--")
        panel.c_poc.set_value_color(THEME.get("text_dim", "#5B6C7A"))


def update_live_banner(panel) -> None:
    """
    Update symbol and live price display in banner.

    Symbol: Shows "--" when flat, symbol when in position
    Live Price: Shows "FLAT" when not in position, current price when in position

    Args:
        panel: Panel2 instance
    """
    if not hasattr(panel, "live_banner") or not hasattr(panel, "symbol_banner"):
        return

    # Check if we have an active position
    has_position = bool(panel.entry_qty and panel.entry_qty > 0)

    # Symbol (left) - shows "--" when flat, symbol when in position
    if has_position:
        panel.symbol_banner.setText(panel.symbol)
    else:
        panel.symbol_banner.setText("--")

    # Live price (right) - shows "FLAT" when not in position, current market price when in position
    if has_position:
        if panel.last_price is not None:
            panel.live_banner.setText(f"{panel.last_price:.2f}")
        else:
            panel.live_banner.setText("--")
    else:
        panel.live_banner.setText("FLAT")


def update_proximity_alerts(panel) -> None:
    """
    Update proximity alerts for stop loss.

    Logs when price transitions into/out of proximity range (within 1.0 point).

    Args:
        panel: Panel2 instance
    """
    # Stop proximity already handled in update_target_stop_cells;
    # here we only emit logs on transitions to reduce noise.
    if panel.stop_price is None or panel.last_price is None:
        return
    near = abs(panel.last_price - panel.stop_price) <= 1.0
    prev_key = "_stop_near_prev"
    was_near = getattr(panel, prev_key, None)
    if was_near is None or was_near != near:
        setattr(panel, prev_key, near)
        if near:
            log.warning("[panel2] Stop proximity detected -- flashing active")
        else:
            log.info("[panel2] Stop proximity cleared -- flashing off")


def update_heat_state_transitions(panel, _prev_last: Optional[float], new_last: Optional[float]) -> None:
    """
    Update heat state machine transitions.

    Logs when position transitions into/out of drawdown state.

    Args:
        panel: Panel2 instance
        _prev_last: Previous last price (unused, for signature compatibility)
        new_last: New last price
    """
    if panel.entry_price is None or getattr(panel, "entry_qty", 0) == 0 or panel.is_long is None or new_last is None:
        return
    in_drawdown = (new_last < panel.entry_price) if panel.is_long else (new_last > panel.entry_price)
    prev_drawdown = None
    key = "_prev_drawdown_state"
    if hasattr(panel, key):
        prev_drawdown = getattr(panel, key)
    setattr(panel, key, in_drawdown)

    if prev_drawdown is None:
        return  # first sample

    if prev_drawdown != in_drawdown:
        if in_drawdown:
            log.info("[panel2] Heat state: drawdown entered")
        else:
            log.info("[panel2] Heat state: drawdown exited")
