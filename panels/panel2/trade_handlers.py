"""
Trade Handlers Module

DTC MESSAGE NORMALIZATION ONLY - forwards to state_manager.

Architecture Contract:
- NO business logic (no PnL, MAE/MFE, R-multiple calculations)
- ONLY normalize DTC messages
- Forward normalized data to state_manager
- Let metrics_updater compute everything for display

Functions:
- notify_trade_closed(): Handle trade closure and persistence
- on_order_update(): Normalize OrderUpdate (TARGETS/STOPS ONLY)
- on_position_update(): Normalize PositionUpdate (SINGLE SOURCE OF TRUTH FOR POSITIONS)

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
        state_mgr = get_state_manager()
        account = trade.get("account", "")
        # CONSOLIDATION FIX: Use canonical mode detection (single source of truth)
        mode = detect_mode_from_account(account)
        balance_before = state_mgr.get_balance_for_mode(mode) if state_mgr else None
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

        state_mgr = get_state_manager()
        trade_manager = TradeManager(state_manager=state_mgr)
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

    CRITICAL: This function ONLY detects stop/target prices and captures close fills.
    It does NOT open or close positions - that's handled exclusively by on_position_update().

    Args:
        panel: Panel2 instance
        payload: Normalized order update dict from data_bridge (not raw DTC)
    """
    try:
        # Get state manager from panel
        if not hasattr(panel, '_state_manager'):
            log.error("[panel2] No state manager found")
            return

        sm = panel._state_manager
        state = sm.get_state()

        # MODE FILTERING (Phase 2 - Option A): Only process orders for active mode
        payload_mode = payload.get("mode")
        if payload_mode and payload_mode != state.mode:
            log.debug(f"[panel2] Skipping OrderUpdate for mode={payload_mode} (current={state.mode})")
            return

        side = payload.get("BuySell")  # 1=Buy, 2=Sell
        price1 = payload.get("Price1")
        order_status = payload.get("OrderStatus")  # 7=Fully Filled
        filled_qty = payload.get("FilledQuantity")
        avg_fill_price = payload.get("AverageFillPrice")

        # ONLY detect stop/target from sell orders (for UI display)
        # Do NOT modify position state - PositionUpdate handles that
        if side == 2 and state.entry_price is not None and price1 is not None:
            price1 = float(price1)
            if price1 < state.entry_price:
                # Lower price = Stop loss
                state.stop_price = price1
                log.info(f"[panel2] Stop detected @ {price1:.2f}")
            elif price1 > state.entry_price:
                # Higher price = Target
                state.target_price = price1
                log.info(f"[panel2] Target detected @ {price1:.2f}")

        # CRITICAL: Capture the exit fill price from closing orders
        # When we have a position and get a fully-filled order, save it for the next PositionUpdate
        if (state.entry_qty and state.entry_qty > 0 and
            side == 2 and order_status == 7 and filled_qty and avg_fill_price):
            # This is a fully-filled SELL order (side=2) while we have a position
            try:
                filled_qty = int(filled_qty) if isinstance(filled_qty, (int, float, str)) else 0
                avg_fill_price = float(avg_fill_price) if isinstance(avg_fill_price, (int, float, str)) else None

                # Store it if it matches our position qty (closing order)
                if filled_qty > 0 and avg_fill_price is not None and avg_fill_price > 0:
                    if abs(filled_qty) == abs(state.entry_qty):
                        state._last_exit_fill_price = avg_fill_price
                        log.info(f"[panel2] Captured exit fill price from OrderUpdate: {avg_fill_price:.2f}")
            except (ValueError, TypeError):
                pass

        # NO POSITION OPENS/CLOSES HERE - PositionUpdate is the single source of truth

    except Exception as e:
        log.error(f"[panel2] on_order_update error: {e}")


def on_position_update(panel, payload: dict) -> None:
    """
    Handle normalized PositionUpdate from DTC and update state_manager.

    CRITICAL: This is the SINGLE SOURCE OF TRUTH for all position opens/closes/updates.

    Logic:
    - qty > 0 and flat → OPEN position
    - qty = 0 and has position → CLOSE position (record trade)
    - qty changed but > 0 → UPDATE position (partial close/scale)

    Args:
        panel: Panel2 instance
        payload: Normalized position update dict from MessageRouter (lowercase keys)
    """
    try:
        # Get state manager from panel
        if not hasattr(panel, '_state_manager'):
            log.error("[panel2] No state manager found")
            return

        sm = panel._state_manager
        state = sm.get_state()

        # MODE FILTERING (Phase 2 - Option A): Only process positions for active mode
        payload_mode = payload.get("mode")
        if payload_mode and payload_mode != state.mode:
            log.debug(f"[panel2] Skipping PositionUpdate for mode={payload_mode} (current={state.mode})")
            return

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

        # CRITICAL: Update symbol from PositionUpdate payload (BEFORE position logic)
        # This ensures symbol comes from the live position, not the quote feed
        if symbol:
            state.symbol = extract_symbol_display(symbol)
            log.info(f"[panel2] Symbol updated from PositionUpdate: {symbol} -> {state.symbol}")

        # Check current state
        current_qty = state.entry_qty if state.entry_qty else 0
        was_flat = state.is_flat()
        has_position = state.has_position()

        # DEBUG: Log every PositionUpdate with current state
        log.info(f"[panel2] PositionUpdate: new_qty={new_qty}, current_qty={current_qty}, entry_price={state.entry_price}, is_long={state.is_long}, has_position={has_position}")

        # ===========================================
        # CASE 1: CLOSE - Position went to zero
        # ===========================================
        if new_qty == 0 and has_position:
            log.info(f"[panel2] CLOSE detected via PositionUpdate: qty {current_qty} → 0")

            # CRITICAL: Use the captured exit fill price from the OrderUpdate
            # If not available, fall back to CSV last_price, then entry_price
            exit_price = None
            if state._last_exit_fill_price:
                exit_price = state._last_exit_fill_price
                log.info(f"[panel2] Using captured exit fill price from OrderUpdate: {exit_price:.2f}")
                # Clear it after use so we don't use stale data
                state._last_exit_fill_price = None
            elif state.last_price:
                exit_price = state.last_price
                log.info(f"[panel2] Using CSV last_price (fill price not captured): {exit_price:.2f}")
            else:
                exit_price = state.entry_price
                log.info(f"[panel2] Using entry_price as fallback: {exit_price:.2f}")

            # Build trade dict using state_manager data
            entry_time = datetime.fromtimestamp(state.entry_time_epoch, tz=UTC) if state.entry_time_epoch else None
            exit_time = datetime.now(tz=UTC)

            qty_val = int(abs(state.entry_qty))
            side = "long" if state.is_long else "short"
            entry_price_val = float(state.entry_price)

            # Calculate P&L using symbol-aware constants
            spec = match_spec(state.symbol)
            sign = 1.0 if state.is_long else -1.0
            realized_pnl = (exit_price - entry_price_val) * sign * qty_val * spec["pt_value"]
            commissions = spec["rt_fee"] * qty_val

            # r-multiple if stop available
            r_multiple = None
            if state.stop_price is not None and float(state.stop_price) > 0:
                risk_per_contract = abs(entry_price_val - float(state.stop_price)) * spec["pt_value"]
                if risk_per_contract > 0:
                    r_multiple = realized_pnl / (risk_per_contract * qty_val)

            # MAE/MFE using TradeMath (single calculation path)
            mae = None
            mfe = None
            mae_pts, mfe_pts = TradeMath.calculate_mae_mfe(
                entry_price=entry_price_val,
                trade_min_price=state.trade_min_price,
                trade_max_price=state.trade_max_price,
                is_long=state.is_long,
            )
            if mae_pts is not None and mfe_pts is not None:
                mae = mae_pts * spec["pt_value"] * qty_val
                mfe = mfe_pts * spec["pt_value"] * qty_val

            trade = {
                "symbol": state.symbol or "",
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

            # Reset state to flat (single source of truth)
            sm.reset_position()
            log.info(f"[panel2] Position closed and reset to flat")

            # Refresh UI
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel, state)

        # ===========================================
        # CASE 2: OPEN - Went from flat to position
        # ===========================================
        elif new_qty > 0 and was_flat and avg_price is not None:
            log.info(f"[panel2] OPEN detected via PositionUpdate: qty 0 → {new_qty} @ {avg_price}")

            # Update state_manager (single source of truth)
            state.entry_qty = abs(new_qty)
            state.entry_price = float(avg_price)
            state.is_long = is_long

            # Initialize timers and extremes
            import time
            if not state.entry_time_epoch:
                state.entry_time_epoch = int(time.time())

                # Capture entry snapshots from current CSV feed
                state.entry_vwap = state.vwap
                state.entry_delta = state.cum_delta
                state.entry_poc = state.poc

                # Initialize trade extremes to entry price (prevents premature MAE/MFE)
                state.trade_min_price = state.entry_price
                state.trade_max_price = state.entry_price

                log.info(f"[panel2] Entry snapshots captured: vwap={state.entry_vwap}, delta={state.entry_delta}, poc={state.entry_poc}")

            log.info(f"[panel2] Position opened: symbol={state.symbol}, qty={new_qty}, avg={avg_price}, long={is_long}")

            # Save state to persistence
            sm.save_state()

            # Refresh UI
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel, state)

        # ===========================================
        # CASE 3: UPDATE - Qty changed but still in position
        # ===========================================
        elif new_qty > 0 and has_position and new_qty != current_qty and avg_price is not None:
            if new_qty < current_qty:
                log.info(f"[panel2] PARTIAL CLOSE detected via PositionUpdate: qty {current_qty} → {new_qty}")
                # TODO: In future, could record partial close as separate trade
            else:
                log.info(f"[panel2] SCALE IN detected via PositionUpdate: qty {current_qty} → {new_qty}")

            # Update state_manager (single source of truth)
            state.entry_qty = abs(new_qty)
            state.entry_price = float(avg_price)
            state.is_long = is_long

            log.info(f"[panel2] Position updated: symbol={state.symbol}, qty={new_qty}, avg={avg_price}")

            # Save state to persistence
            sm.save_state()

            # Refresh UI
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel, state)

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
