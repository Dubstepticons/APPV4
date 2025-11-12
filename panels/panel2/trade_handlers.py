"""
Trade Handlers Module

Handles trade notifications, order updates, and position updates for Panel2 (Trading panel).
Extracted from panels/panel2.py for modularity.

Functions:
- notify_trade_closed(): Handle trade closure and persistence
- on_order_update(): Handle DTC order status messages (TARGETS/STOPS ONLY)
- on_position_update(): Handle DTC position updates (SINGLE SOURCE OF TRUTH FOR POSITIONS)

Features:
- Automatic trade persistence to database
- Signal emission for trade closures
- P&L calculations with MAE/MFE/R-multiple
- Position state synchronization
- Mode detection (SIM/LIVE) from account

CRITICAL DESIGN PRINCIPLE:
- on_position_update() is the ONLY function that opens/closes positions
- on_order_update() ONLY detects stop/target prices, NEVER modifies position state
- DTC PositionUpdate messages are the single source of truth for qty/entry/direction
"""

from datetime import datetime, UTC
from typing import Optional
from config.theme import THEME
from config.trading_specs import match_spec
from services.trade_math import TradeMath
from utils.format_utils import extract_symbol_display
from utils.logger import get_logger
from utils.trade_mode import detect_mode_from_account

log = get_logger(__name__)


def notify_trade_closed(panel, trade: dict) -> None:
    """
    External hook to persist a closed trade and notify listeners.

    Args:
        panel: Panel2 instance
        trade: Trade dict with keys:
            - symbol, side, qty, entry_price, exit_price, realized_pnl
            - entry_time, exit_time, commissions, r_multiple, mae, mfe, account (optional)
    """
    # Get current balance BEFORE processing
    try:
        from core.app_state import get_state_manager
        state = get_state_manager()
        account = trade.get("account", "")
        # CONSOLIDATION FIX: Use canonical mode detection (single source of truth)
        mode = detect_mode_from_account(account)
        balance_before = state.get_balance_for_mode(mode) if state else None
    except Exception:
        balance_before = None
        mode = "UNKNOWN"

    # Log trade close summary
    symbol = trade.get("symbol", "UNKNOWN")
    pnl = trade.get("realized_pnl", 0)
    pnl_sign = "+" if pnl >= 0 else ""
    entry = trade.get("entry_price", "?")
    exit_p = trade.get("exit_price", "?")
    qty = trade.get("qty", "?")

    # Simple one-line trade close notification
    print(f"[TRADE CLOSE] {symbol} {qty} @ {entry} -> {exit_p} | P&L: {pnl_sign}${abs(pnl):,.2f} | Mode: {mode}")

    try:
        from services.trade_service import TradeManager
        from core.app_state import get_state_manager

        state = get_state_manager()
        trade_manager = TradeManager(state_manager=state)
    except Exception as e:
        trade_manager = None

    ok = False
    try:
        if trade_manager:
            # Extract account from trade dict for mode detection
            account = trade.get("account", "")

            # Create pos_info dict from trade data
            pos_info = {
                "qty": trade.get("qty", 0),
                "entry_price": trade.get("entry_price", 0),
                "entry_time": trade.get("entry_time"),
                "account": account,
            }

            # Call record_closed_trade with proper signature
            try:
                ok = trade_manager.record_closed_trade(
                    symbol=trade.get("symbol", ""),
                    pos_info=pos_info,
                    exit_price=trade.get("exit_price"),
                    realized_pnl=trade.get("realized_pnl"),
                    commissions=trade.get("commissions"),
                    r_multiple=trade.get("r_multiple"),
                    mae=trade.get("mae"),
                    mfe=trade.get("mfe"),
                    efficiency=trade.get("efficiency"),
                    # Account will be auto-detected in record_closed_trade
                )
            except Exception as method_error:
                import traceback
                traceback.print_exc()
                ok = False
    except Exception as e:
        log.error(f"[panel2] Error recording closed trade: {e}", exc_info=True)
        ok = False

    # Emit regardless; consumers may refresh their views
    try:
        payload = dict(trade)
        payload["ok"] = ok
        panel.tradesChanged.emit(payload)
    except Exception as e:
        pass


def on_order_update(panel, payload: dict) -> None:
    """
    Handle normalized OrderUpdate from DTC (via data_bridge).

    CRITICAL: This function ONLY detects stop/target prices from order placement.
    It does NOT open or close positions - that's handled exclusively by on_position_update().

    Args:
        panel: Panel2 instance
        payload: Normalized order update dict from data_bridge (not raw DTC)
    """
    try:
        side = payload.get("BuySell")  # 1=Buy, 2=Sell
        price1 = payload.get("Price1")

        # ONLY detect stop/target from sell orders (for UI display)
        # Do NOT modify position state - PositionUpdate handles that
        if side == 2 and panel.entry_price is not None and price1 is not None:
            price1 = float(price1)
            if price1 < panel.entry_price:
                # Lower price = Stop loss
                panel.stop_price = price1
                panel.c_stop.set_value_text(f"{price1:.2f}")
                panel.c_stop.set_value_color(THEME.get("text_primary", "#E6F6FF"))
                log.info(f"[panel2] Stop detected @ {price1:.2f}")
            elif price1 > panel.entry_price:
                # Higher price = Target
                panel.target_price = price1
                panel.c_target.set_value_text(f"{price1:.2f}")
                panel.c_target.set_value_color(THEME.get("text_primary", "#E6F6FF"))
                log.info(f"[panel2] Target detected @ {price1:.2f}")

        # NO POSITION OPENS/CLOSES HERE - PositionUpdate is the single source of truth

    except Exception as e:
        log.error(f"[panel2] on_order_update error: {e}")


def on_position_update(panel, payload: dict) -> None:
    """
    Handle normalized PositionUpdate from DTC and mirror into local state.

    CRITICAL: This is the SINGLE SOURCE OF TRUTH for all position opens/closes/updates.

    Logic:
    - qty > 0 and panel flat → OPEN position
    - qty = 0 and panel has position → CLOSE position (record trade)
    - qty changed but > 0 → UPDATE position (partial close/scale)

    Args:
        panel: Panel2 instance
        payload: Normalized position update dict from MessageRouter (lowercase keys)
    """
    try:
        # Extract from normalized payload (lowercase keys from data_bridge normalization)
        new_qty = int(payload.get("qty", 0))
        avg_price = payload.get("avg_entry")

        # CRITICAL: Extract symbol from PositionUpdate payload (NOT from quote feed)
        # Try both lowercase (normalized) and uppercase (raw DTC) keys
        symbol = payload.get("symbol") or payload.get("Symbol") or ""
        account = payload.get("TradeAccount") or ""

        # Convert to float if not None
        if avg_price is not None:
            avg_price = float(avg_price)

        # CRITICAL: Reject positions without valid price data (avoid cached stale data)
        if new_qty != 0 and avg_price is None:
            log.warning(f"[panel2] Rejecting position with qty={new_qty} but missing price")
            return

        # Determine direction
        is_long = None if new_qty == 0 else (new_qty > 0)

        # CRITICAL: Update symbol from PositionUpdate payload (BEFORE set_position)
        # This ensures symbol comes from the live position, not the quote feed
        if symbol:
            panel.symbol = extract_symbol_display(symbol)
            log.info(f"[panel2] Symbol updated from PositionUpdate: {symbol} -> {panel.symbol}")

            # Immediately update header banner to show new symbol
            if hasattr(panel, "symbol_banner"):
                panel.symbol_banner.setText(panel.symbol)

        # Check current panel state
        current_qty = panel.entry_qty if panel.entry_qty else 0
        was_flat = (current_qty == 0)
        has_position = (current_qty > 0 and panel.entry_price is not None and panel.is_long is not None)

        # ===========================================
        # CASE 1: CLOSE - Position went to zero
        # ===========================================
        if new_qty == 0 and has_position:
            log.info(f"[panel2] CLOSE detected via PositionUpdate: qty {current_qty} → 0")

            # Use last price as exit price (position already closed, we don't have fill price here)
            exit_price = panel.last_price if panel.last_price else panel.entry_price

            # Build trade dict
            entry_time = datetime.fromtimestamp(panel.entry_time_epoch, tz=UTC) if panel.entry_time_epoch else None
            exit_time = datetime.now(tz=UTC)

            qty_val = int(abs(panel.entry_qty))
            side = "long" if panel.is_long else "short"
            entry_price_val = float(panel.entry_price)

            # Calculate P&L using symbol-aware constants
            spec = match_spec(panel.symbol)
            sign = 1.0 if panel.is_long else -1.0
            realized_pnl = (exit_price - entry_price_val) * sign * qty_val * spec["pt_value"]
            commissions = spec["rt_fee"] * qty_val

            # r-multiple if stop available
            r_multiple = None
            if panel.stop_price is not None and float(panel.stop_price) > 0:
                risk_per_contract = abs(entry_price_val - float(panel.stop_price)) * spec["pt_value"]
                if risk_per_contract > 0:
                    r_multiple = realized_pnl / (risk_per_contract * qty_val)

            # MAE/MFE using TradeMath
            mae = None
            mfe = None
            mae_pts, mfe_pts = TradeMath.calculate_mae_mfe(
                entry_price=entry_price_val,
                trade_min_price=panel._trade_min_price,
                trade_max_price=panel._trade_max_price,
                is_long=panel.is_long,
            )
            if mae_pts is not None and mfe_pts is not None:
                mae = mae_pts * spec["pt_value"] * qty_val
                mfe = mfe_pts * spec["pt_value"] * qty_val

            trade = {
                "symbol": panel.symbol or "",
                "side": side,
                "qty": qty_val,
                "entry_price": entry_price_val,
                "exit_price": exit_price,
                "realized_pnl": realized_pnl,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "commissions": commissions,
                "r_multiple": r_multiple,
                "mae": mae,
                "mfe": mfe,
                "account": account,
            }

            # Persist the trade
            notify_trade_closed(panel, trade)

            # Reset position to flat
            panel.set_position(0, 0.0, None)
            log.info(f"[panel2] Position closed and reset to flat")

            # Ensure UI refresh happens
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel)

        # ===========================================
        # CASE 2: OPEN - Went from flat to position
        # ===========================================
        elif new_qty > 0 and was_flat and avg_price is not None:
            log.info(f"[panel2] OPEN detected via PositionUpdate: qty 0 → {new_qty} @ {avg_price}")

            # Open new position
            panel.set_position(abs(new_qty), avg_price, is_long)
            log.info(f"[panel2] Position opened: symbol={panel.symbol}, qty={new_qty}, avg={avg_price}, long={is_long}")

            # Ensure UI refresh happens
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel)

        # ===========================================
        # CASE 3: UPDATE - Qty changed but still in position
        # ===========================================
        elif new_qty > 0 and has_position and new_qty != current_qty and avg_price is not None:
            if new_qty < current_qty:
                log.info(f"[panel2] PARTIAL CLOSE detected via PositionUpdate: qty {current_qty} → {new_qty}")
                # TODO: In future, could record partial close as separate trade
            else:
                log.info(f"[panel2] SCALE IN detected via PositionUpdate: qty {current_qty} → {new_qty}")

            # Update position with new qty/avg
            panel.set_position(abs(new_qty), avg_price, is_long)
            log.info(f"[panel2] Position updated: symbol={panel.symbol}, qty={new_qty}, avg={avg_price}")

            # Ensure UI refresh happens
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel)

        # ===========================================
        # CASE 4: NO CHANGE - Redundant update
        # ===========================================
        elif new_qty == current_qty:
            log.debug(f"[panel2] Redundant PositionUpdate: qty unchanged at {new_qty}")
            # No action needed

        # ===========================================
        # CASE 5: Invalid state
        # ===========================================
        else:
            log.warning(f"[panel2] Unexpected PositionUpdate state: new_qty={new_qty}, current_qty={current_qty}, avg={avg_price}")

    except Exception as e:
        log.error(f"[panel2] on_position_update error: {e}", exc_info=True)
