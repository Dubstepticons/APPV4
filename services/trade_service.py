"""
Unified Trade Management Service

Consolidates:
- Trade logging (position opens/closes)
- Trade storage (database persistence)

Note: For trading statistics (historical analysis), use services.stats_service
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
import threading
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from utils.trade_mode import detect_mode_from_account  # CONSOLIDATION FIX: Single source of truth


log = get_logger(__name__)


class TradeManager:
    """
    Unified trade management service with mode-aware recording.
    Handles logging, storage, and analysis of trades.

    CRITICAL FIX: Thread-safe database writes with serialization lock.
    """

    # Class-level lock for serializing database writes (CRITICAL: prevents race conditions)
    _db_write_lock = threading.Lock()

    def __init__(self, state_manager=None):
        self._open_positions: dict[str, dict[str, Any]] = {}
        self._account = "UNKNOWN"
        self.state = state_manager  # StateManager for mode tracking

    def set_account(self, account: str) -> None:
        """Set the current trading account."""
        self._account = account
        log.info(f"trade_manager.account.{account}")

    def on_position_update(self, payload: dict[str, Any]) -> None:
        """
        Called when a position update (Type 306) arrives from DTC.
        Logs opens when qty goes from 0 to N.
        Logs closes when qty goes from N to 0.
        """

        symbol = payload.get("symbol")
        qty = payload.get("qty", 0)
        avg_entry = payload.get("avg_entry")
        trade_account = payload.get("TradeAccount")


        if not symbol:
            return

        current_pos = self._open_positions.get(symbol)

        # OPEN: qty increased (or went from 0 to qty)
        if qty > 0 and (not current_pos or current_pos["qty"] == 0):
            log.info(
                "trade.open",
                symbol=symbol,
                qty=qty,
                entry_price=avg_entry,
                account=self._account,
            )
            self._open_positions[symbol] = {
                "qty": qty,
                "entry_price": avg_entry,
                "entry_time": datetime.utcnow(),
                "trade_account": trade_account,
                "account": self._account,
            }

        # CLOSE: qty went to 0
        elif qty == 0 and current_pos and current_pos["qty"] > 0:
            log.info(
                "trade.close",
                symbol=symbol,
                original_qty=current_pos["qty"],
                entry_price=current_pos["entry_price"],
                account=self._account,
            )
            print(f"  current_pos keys: {list(current_pos.keys())}")
            print(f"  current_pos: {current_pos}")
            print(f"  [WARNING] Position qty-0 detected, but NOT recording trade here!")
            print(f"  [INFO] Panel2.notify_trade_closed() will handle the record_closed_trade() call\n")

            #  DO NOT call record_closed_trade() here!
            # Panel2.notify_trade_closed() will call it with full exit price data
            # Calling it here would:
            # 1. Create duplicate trade records
            # 2. Update balance twice with wrong values
            # 3. Have no exit_price, so PnL can't be calculated

            self._open_positions.pop(symbol, None)

        # UPDATE: qty changed but didn't close
        elif qty > 0 and current_pos:
            if qty != current_pos["qty"]:
                log.debug("trade.partial_close", symbol=symbol, old_qty=current_pos["qty"], new_qty=qty)
                self._open_positions[symbol]["qty"] = qty

    def on_order_fill(self, payload: dict[str, Any]) -> None:
        """
        Called when an order fill (Type 307) arrives.
        Can be used to supplement position tracking with fill prices.
        """
        symbol = payload.get("Symbol")
        filled_qty = payload.get("FilledQuantity", 0)
        fill_price = payload.get("Price") or payload.get("AverageFillPrice")

        if symbol and filled_qty > 0 and fill_price:
            log.debug(
                "trade.fill",
                symbol=symbol,
                qty=filled_qty,
                price=fill_price,
                account=self._account,
            )

    def record_closed_trade(
        self,
        symbol: str,
        pos_info: dict[str, Any],
        exit_price: Optional[float] = None,
        realized_pnl: Optional[float] = None,
        commissions: Optional[float] = None,
        r_multiple: Optional[float] = None,
        mae: Optional[float] = None,
        mfe: Optional[float] = None,
        efficiency: Optional[float] = None,
        mode: Optional[str] = None,
        entry_vwap: Optional[float] = None,
        entry_cum_delta: Optional[float] = None,
        exit_vwap: Optional[float] = None,
        exit_cum_delta: Optional[float] = None,
    ) -> bool:
        """
        Save a closed trade to the database for historical analysis.

        Args:
            symbol: Trade symbol
            pos_info: Position info dict from _open_positions
            exit_price: Exit price
            realized_pnl: Realized P&L
            commissions: Commission amount
            r_multiple: Risk multiple
            mae: Maximum adverse excursion
            mfe: Maximum favorable excursion
            efficiency: Capture ratio (realized_pnl / mfe, 0.0-1.0+)
            mode: "SIM" or "LIVE" (detected from account if not provided)
            entry_vwap: Entry VWAP snapshot
            entry_cum_delta: Entry cumulative delta
            exit_vwap: Exit VWAP snapshot
            exit_cum_delta: Exit cumulative delta
        """
        # CLEANUP FIX: Use structured logging instead of print()
        log.debug(
            "trade_manager.record_closed_trade.start",
            symbol=symbol,
            realized_pnl=realized_pnl,
            exit_price=exit_price,
            commissions=commissions,
            has_pos_info=bool(pos_info)
        )

        try:
            from data.db_engine import get_session
            from data.schema import TradeRecord
        except Exception as e:
            log.error(f"trade_manager.db_import_failed: {str(e)}")
            return False

        try:
            entry_price = pos_info.get("entry_price", 0.0)
            entry_time = pos_info.get("entry_time", datetime.utcnow())
            exit_time = datetime.utcnow()
            qty = pos_info.get("qty", 0)
            # Account can come from pos_info (preferred) or fallback to self._account
            account = pos_info.get("account") or self._account

            log.debug(
                "trade_manager.trade_params",
                entry_price=entry_price,
                qty=qty,
                account=account
            )

            # Calculate P&L if not provided
            if realized_pnl is None and exit_price is not None:
                realized_pnl = (exit_price - entry_price) * qty
                log.debug(
                    "trade_manager.pnl_calculated",
                    formula="(exit-entry)*qty",
                    result=realized_pnl
                )
            else:
                log.debug(
                    "trade_manager.pnl_provided",
                    pnl=realized_pnl,
                    exit_price=exit_price
                )

            # Detect mode if not provided
            if mode is None:
                if self.state:
                    mode = self.state.detect_and_set_mode(account)
                else:
                    # CONSOLIDATION FIX: Use canonical mode detection (single source of truth)
                    mode = detect_mode_from_account(account)


            # ARCHITECTURE FIX (Step 1): Update balance for the mode
            # StateManager is the ONLY place where balances are updated
            new_balance = None  # Initialize to None for later use
            if self.state and realized_pnl is not None:
                current_balance = self.state.get_balance_for_mode(mode)
                new_balance = current_balance + realized_pnl

                # CLEANUP FIX: Use structured logging
                log.info(
                    f"balance.updated.{mode}",
                    old_balance=current_balance,
                    new_balance=new_balance,
                    pnl=realized_pnl
                )

                self.state.set_balance_for_mode(mode, new_balance)
            else:
                # CRITICAL: Balance updates should ALWAYS happen for closed trades
                # Missing state or pnl indicates a problem in the trade closure pipeline
                if mode == "SIM" and not self.state:
                    log.error(
                        "trade_manager.balance_update_failed",
                        reason="StateManager not available",
                        mode=mode,
                        pnl=realized_pnl,
                        message="SIM balance NOT updated - StateManager missing!"
                    )
                elif realized_pnl is None:
                    log.warning(
                        "trade_manager.balance_skip",
                        reason="realized_pnl is None",
                        has_state=bool(self.state)
                    )
                else:
                    log.debug(
                        "trade_manager.balance_skip",
                        has_state=bool(self.state),
                        has_pnl=realized_pnl is not None
                    )

            # CLEANUP FIX: Use structured logging for trade details
            log.debug(
                "trade_manager.trade_details",
                symbol=symbol,
                qty=int(abs(qty)),
                mode=mode,
                entry_price=entry_price,
                exit_price=exit_price,
                realized_pnl=realized_pnl,
                account=account
            )

            trade = TradeRecord(
                symbol=symbol,
                side="LONG",  # Will be refined based on qty sign later
                qty=int(abs(qty)),
                mode=mode,  # <-- KEY: Record the trade mode
                entry_price=float(entry_price),
                entry_time=entry_time,
                entry_vwap=float(entry_vwap) if entry_vwap else None,
                entry_cum_delta=float(entry_cum_delta) if entry_cum_delta else None,
                exit_price=float(exit_price) if exit_price else None,
                exit_time=exit_time,
                exit_vwap=float(exit_vwap) if exit_vwap else None,
                exit_cum_delta=float(exit_cum_delta) if exit_cum_delta else None,
                is_closed=True,
                realized_pnl=float(realized_pnl) if realized_pnl else None,
                commissions=float(commissions) if commissions else None,
                r_multiple=float(r_multiple) if r_multiple else None,
                mae=float(mae) if mae else None,
                mfe=float(mfe) if mfe else None,
                efficiency=float(efficiency) if efficiency is not None else None,
                account=account,
            )

            # CRITICAL FIX: Serialize database writes to prevent race conditions
            with self._db_write_lock:
                with get_session() as s:
                    s.add(trade)
                    s.commit()

                    # CLEANUP FIX: Use structured logging
                    pnl_str = f"{realized_pnl:+,.2f}" if realized_pnl is not None else "N/A"
                    log.info(
                        f"trade.recorded: {symbol} | PnL={pnl_str} | Mode={mode} | ID={trade.id}",
                        trade_id=trade.id,
                        symbol=symbol,
                        mode=mode,
                        pnl=realized_pnl,
                        entry=entry_price,
                        exit=exit_price,
                        qty=int(abs(qty)),
                        new_balance=new_balance
                    )

            # CRITICAL FIX: Invalidate stats cache when new trade recorded
            try:
                from services.stats_service import invalidate_stats_cache
                invalidate_stats_cache()
            except Exception as e:
                log.warning(f"Failed to invalidate stats cache: {e}")

            return True

        except Exception as e:
            import traceback
            # CLEANUP FIX: Use structured logging for errors
            log.error(
                f"trade_manager.db_write_failed for {symbol}: {str(e)}",
                error_type=type(e).__name__,
                symbol=symbol,
                traceback=traceback.format_exc()
            )
            return False

    # REMOVED: compute_trading_stats_for_timeframe
    # This method was duplicate of services.stats_service.compute_trading_stats_for_timeframe
    # Panel 3 now uses stats_service directly for comprehensive formatted statistics
    # If you need raw statistics, use stats_service.compute_trading_stats_for_timeframe()

    # REMOVED: _timeframe_start() duplicate function
    # CONSOLIDATION FIX: Use utils.timeframe_helpers.timeframe_start() instead
    # This function was never called in trade_service.py - it was dead code
