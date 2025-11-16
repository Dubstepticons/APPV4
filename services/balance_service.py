"""
services/balance_service.py

Balance service for loading and reconciling account balances from the database.

Architecture:
- UnifiedBalanceManager is the single source of truth for balances
- This service provides initialization logic for balance loading at startup

This module provides:
- load_sim_balance_from_trades(account): Initialize SIM balance at startup
  by loading from UnifiedBalanceManager (which queries the trade ledger)
"""

from __future__ import annotations

from typing import Optional

from services.unified_balance_manager import get_balance_manager
from services.trade_constants import SIM_STARTING_BALANCE
from utils.logger import get_logger


log = get_logger(__name__)


def load_sim_balance_from_trades(account: str = "Sim1") -> float:
    """
    Load the SIM balance from UnifiedBalanceManager.

    This is called on app startup to restore the balance if the app was restarted.
    UnifiedBalanceManager will query the database and calculate the balance
    from the trade ledger (starting balance + total realized P&L).

    Args:
        account: SIM account identifier (default: "Sim1")

    Returns:
        The loaded SIM balance.
    """
    try:
        balance_manager = get_balance_manager()

        # UnifiedBalanceManager will load from database on first access
        balance = balance_manager.get_balance("SIM", account)

        log.info(
            "[BalanceService] SIM balance loaded",
            account=account,
            balance=balance,
        )

        print("\n[INITIAL BALANCE] SIM Account Loaded")
        print(f"  Account: {account}")
        print(f"  Starting Balance: ${SIM_STARTING_BALANCE:,.2f}")
        print(f"  Current Balance: ${balance:,.2f}")
        print(f"  Total P&L from Trades: ${balance - SIM_STARTING_BALANCE:+,.2f}\n")

        return balance
    except Exception as e:  # pragma: no cover - defensive fallback
        log.error(f"[BalanceService] Error loading SIM balance: {e}")
        # Fall back to starting balance
        return SIM_STARTING_BALANCE

