"""
services/balance_service.py

Balance service for loading and reconciling account balances from the database.

Architecture:
- Services own business rules and persistence.
- StateManager is an in-memory cache and should not talk directly to the DB.

This module currently provides:
- load_sim_balance_from_trades(state_manager): Initialize SIM balance at startup
  by summing realized P&L from closed SIM trades in the ledger.
"""

from __future__ import annotations

from typing import Any

from utils.logger import get_logger


log = get_logger(__name__)


def load_sim_balance_from_trades(state_manager: Any) -> float:
    """
    Load the SIM balance from the database by summing all realized P&L trades.

    This is called on app startup to restore the balance if the app was restarted.
    The computed balance is written into the provided StateManager instance.

    Args:
        state_manager: StateManager-like object with a `sim_balance` attribute.

    Returns:
        The loaded SIM balance.
    """
    try:
        from data.db_engine import get_session
        from data.schema import TradeRecord
        from sqlalchemy import func

        log.debug("[BalanceService] Loading SIM balance from database...")

        with get_session() as session:
            # Query all closed trades in SIM mode and sum their realized P&L
            result = (
                session.query(func.sum(TradeRecord.realized_pnl))
                .filter(
                    TradeRecord.mode == "SIM",
                    TradeRecord.realized_pnl != None,  # noqa: E711
                    TradeRecord.is_closed == True,  # noqa: E712
                )
                .scalar()
            )

            # Also count how many trades we have
            trade_count = (
                session.query(TradeRecord)
                .filter(
                    TradeRecord.mode == "SIM",
                    TradeRecord.is_closed == True,  # noqa: E712
                )
                .count()
            )

            total_pnl = float(result) if result else 0.0

            # Update StateManager cache
            state_manager.sim_balance = 10000.0 + total_pnl
            new_balance = state_manager.sim_balance

        log.info(
            "[BalanceService] SIM balance restored from trades",
            trades=trade_count,
            base_balance=10000.0,
            total_pnl=total_pnl,
            current_balance=new_balance,
        )

        print("\n[INITIAL BALANCE] SIM Account Loaded")
        print("  Starting Balance: $10,000.00")
        print(f"  Loaded Balance: ${new_balance:,.2f}")
        print(f"  Total P&L from Trades: ${new_balance - 10000.0:+,.2f}\n")

        return new_balance
    except Exception as e:  # pragma: no cover - defensive fallback
        log.error(f"[BalanceService] Error loading SIM balance: {e}")
        # Fall back to default 10k
        try:
            state_manager.sim_balance = 10000.0
            return state_manager.sim_balance
        except Exception:
            # In extreme failure, just return default
            return 10000.0

