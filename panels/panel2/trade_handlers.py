"""
Trade Handlers Module

Handles trade notifications, order updates, and position updates for Panel2 (Trading panel).
Extracted from panels/panel2.py for modularity.

Functions:
- notify_trade_closed(): Handle trade closure and persistence
- on_order_update(): Handle DTC order status messages
- on_position_update(): Handle DTC position updates

Features:
- Automatic trade persistence to database
- Signal emission for trade closures
- P&L calculations with MAE/MFE/R-multiple
- Position state synchronization
- Mode detection (SIM/LIVE) from account
"""

from datetime import datetime, UTC
from typing import Optional
from config.theme import THEME
from services.trade_constants import COMM_PER_CONTRACT, DOLLARS_PER_POINT
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

    Persists closed trades automatically and resets per-trade trackers.
    Seeds position from fill data when in SIM mode (Sierra Chart doesn't send non-zero PositionUpdate).
    Auto-detects stop and target orders from sell orders based on price relative to entry.

    Args:
        panel: Panel2 instance
        payload: Normalized order update dict from data_bridge (not raw DTC)
    """
    try:
        order_status = payload.get("OrderStatus")
        side = payload.get("BuySell")  # 1=Buy, 2=Sell
        price1 = payload.get("Price1")

        # Auto-detect stop/target from sell orders (regardless of fill status)
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

        # Process fills (Status 3=Filled, 7=Filled)
        if order_status not in (3, 7):
            return

        # SIM mode workaround: Seed position from fill if we don't have one yet
        # (Sierra Chart in SIM mode never sends non-zero PositionUpdate, only qty=0)
        qty = payload.get("FilledQuantity") or 0
        price = payload.get("AverageFillPrice") or payload.get("Price1")
        is_long = side == 1

        if qty > 0 and price is not None:
            # Only seed if we're currently flat (no existing position)
            if not (panel.entry_qty and panel.entry_price is not None and panel.is_long is not None):
                from panels.panel2 import live_panel
                live_panel.set_position(panel, qty, price, is_long)
                log.info(f"[panel2] Seeded position from fill: qty={qty}, price={price}, long={is_long}")
                return  # Early exit - don't process as close since we just opened

        # Require we have an active position context for closing logic
        if not (panel.entry_qty and panel.entry_price is not None and panel.is_long is not None):
            return

        # CRITICAL FIX: Only process as a CLOSE if quantity is DECREASING
        # If qty stayed the same or increased, this is NOT a close - skip it!
        current_qty = panel.entry_qty if panel.entry_qty else 0

        # If incoming qty >= current qty, this is adding to or maintaining position, not closing
        if qty >= current_qty:
            return

        # If we reach here, it's a CLOSE
        print(f"  CLOSE DETECTED: qty decreased from {current_qty} to {qty}")

        # Extract exit price from payload
        exit_price = (
            payload.get("LastFillPrice")
            or payload.get("AverageFillPrice")
            or payload.get("Price1")
            or panel.last_price
        )
        if exit_price is None:
            log.warning("[panel2] Fill detected but no exit price available")
            return
        exit_price = float(exit_price)

        qty = int(abs(panel.entry_qty))
        side = "long" if panel.is_long else "short"
        entry_price = float(panel.entry_price)

        # Use centralized trading constants
        sign = 1.0 if panel.is_long else -1.0
        realized_pnl = (exit_price - entry_price) * sign * qty * DOLLARS_PER_POINT
        commissions = COMM_PER_CONTRACT * qty

        # r-multiple if stop available
        r_multiple = None
        if panel.stop_price is not None and float(panel.stop_price) > 0:
            risk_per_contract = abs(entry_price - float(panel.stop_price)) * DOLLARS_PER_POINT
            if risk_per_contract > 0:
                r_multiple = realized_pnl / (risk_per_contract * qty)

        # MAE/MFE using TradeMath
        mae = None
        mfe = None
        efficiency = None
        mae_pts, mfe_pts = TradeMath.calculate_mae_mfe(
            entry_price=entry_price,
            trade_min_price=panel._trade_min_price,
            trade_max_price=panel._trade_max_price,
            is_long=panel.is_long,
        )
        if mae_pts is not None and mfe_pts is not None:
            mae = mae_pts * DOLLARS_PER_POINT * qty
            mfe = mfe_pts * DOLLARS_PER_POINT * qty

            # Calculate efficiency: (realized PnL / MFE) if MFE > 0
            if mfe > 0 and realized_pnl is not None:
                # Efficiency = realized profit / maximum potential profit
                # Expressed as decimal (0.0 to 1.0, where 1.0 = 100% efficient)
                # Can exceed 1.0 if trail added profit beyond max seen during trade
                efficiency = realized_pnl / mfe

        # entry/exit times
        entry_time = datetime.fromtimestamp(panel.entry_time_epoch, tz=UTC) if panel.entry_time_epoch else None
        # Use DTC timestamp from payload
        exit_ts = payload.get("DateTime")
        exit_time = datetime.fromtimestamp(float(exit_ts), tz=UTC) if exit_ts else datetime.now(tz=UTC)

        # Get account for mode detection (SIM vs LIVE)
        account = payload.get("TradeAccount") or ""

        trade = {
            "symbol": payload.get("Symbol") or "",
            "side": side,
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "commissions": commissions,
            "r_multiple": r_multiple,
            "mae": mae,
            "mfe": mfe,
            "efficiency": efficiency,
            "account": account,  # <- Include account for mode detection (SIM/LIVE)
        }

        notify_trade_closed(panel, trade)

        # Reset position context after close
        from panels.panel2 import live_panel
        live_panel.set_position(panel, 0, 0.0, None)
    except Exception as e:
        log.error(f"[panel2] on_order_update error: {e}")


def on_position_update(panel, payload: dict) -> None:
    """
    Handle normalized PositionUpdate from DTC and mirror into local state.

    Detects trade closure when position goes from non-zero to zero.

    Args:
        panel: Panel2 instance
        payload: Normalized position update dict from MessageRouter (lowercase keys)
    """
    try:
        # Extract from normalized payload (lowercase keys from data_bridge normalization)
        qty = int(payload.get("qty", 0))
        avg_price = payload.get("avg_entry")

        # CRITICAL: Extract symbol from PositionUpdate payload (NOT from quote feed)
        # Try both lowercase (normalized) and uppercase (raw DTC) keys
        symbol = payload.get("symbol") or payload.get("Symbol") or ""

        # Convert to float if not None
        if avg_price is not None:
            avg_price = float(avg_price)

        # CRITICAL: Reject positions without valid price data (avoid cached stale data)
        if qty != 0 and avg_price is None:
            log.warning(
                f"[panel2] Rejecting position with qty={qty} but missing price"
            )
            return

        # Determine direction
        is_long = None if qty == 0 else (qty > 0)

        # CRITICAL: Update symbol from PositionUpdate payload (BEFORE set_position)
        # This ensures symbol comes from the live position, not the quote feed
        if symbol:
            panel.symbol = extract_symbol_display(symbol)
            log.info(f"[panel2] Symbol updated from PositionUpdate: {symbol} -> {panel.symbol}")

            # Immediately update header banner to show new symbol
            if hasattr(panel, "symbol_banner"):
                panel.symbol_banner.setText(panel.symbol)

        # CRITICAL: Detect trade closure - position went from non-zero to zero
        if qty == 0 and panel.entry_qty and panel.entry_qty > 0 and panel.entry_price is not None and panel.is_long is not None:
            pass

            # Use last price as exit price (position already closed, we don't have fill price here)
            exit_price = panel.last_price if panel.last_price else panel.entry_price

            # Build trade dict
            entry_time = datetime.fromtimestamp(panel.entry_time_epoch, tz=UTC) if panel.entry_time_epoch else None
            exit_time = datetime.now(tz=UTC)

            qty_val = int(abs(panel.entry_qty))
            side = "long" if panel.is_long else "short"
            entry_price_val = float(panel.entry_price)

            # Calculate P&L
            sign = 1.0 if panel.is_long else -1.0
            realized_pnl = (exit_price - entry_price_val) * sign * qty_val * DOLLARS_PER_POINT
            commissions = COMM_PER_CONTRACT * qty_val

            # r-multiple if stop available
            r_multiple = None
            if panel.stop_price is not None and float(panel.stop_price) > 0:
                risk_per_contract = abs(entry_price_val - float(panel.stop_price)) * DOLLARS_PER_POINT
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
                mae = mae_pts * DOLLARS_PER_POINT * qty_val
                mfe = mfe_pts * DOLLARS_PER_POINT * qty_val

            # Get account for mode detection
            account = payload.get("TradeAccount") or ""

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

        # Update position state (ONLY if we have valid data)
        if qty == 0 or avg_price is not None:
            # Store entry price and quantity explicitly
            panel.entry_price = avg_price if qty != 0 else None
            panel.entry_qty = abs(qty) if qty != 0 else 0

            # Call set_position to update timers and capture snapshots
            from panels.panel2 import live_panel
            live_panel.set_position(panel, abs(qty), avg_price, is_long)
            log.info(f"[panel2] Position update accepted: symbol={panel.symbol}, qty={qty}, avg={avg_price}, long={is_long}")

            # Ensure UI refresh happens
            from panels.panel2 import metrics_updater
            metrics_updater.refresh_all_cells(panel)
        else:
            log.warning(f"[panel2] Invalid position data - skipping: qty={qty}, avg={avg_price}")
    except Exception as e:
        log.error(f"[panel2] on_position_update error: {e}", exc_info=True)
