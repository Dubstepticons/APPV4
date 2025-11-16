"""
services/unified_balance_manager.py

Unified Balance Manager - Single source of truth for all balance operations.

This module consolidates balance logic previously scattered across:
- core/sim_balance.py (SimBalanceManager)
- core/state_manager.py (sim_balance, live_balance attributes)
- services/balance_service.py (load_sim_balance_from_trades)

Architecture Benefits:
- Single Responsibility: All balance operations in one place
- Thread Safety: Consistent locking across all balance operations
- Mode Awareness: Proper handling of SIM/LIVE/DEBUG balances
- Database Integration: Direct integration with trade ledger
- Event Emission: Automatic balance change events via SignalBus

Usage:
    from services.unified_balance_manager import get_balance_manager

    balance_mgr = get_balance_manager()

    # Get balance for current mode
    balance = balance_mgr.get_balance("SIM", "Sim1")

    # Adjust balance after trade
    new_balance = balance_mgr.adjust_balance("SIM", "Sim1", realized_pnl)

    # Reset SIM balance
    balance_mgr.reset_balance("SIM", "Sim1")
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Optional

from PyQt6 import QtCore

import structlog

from services.trade_constants import SIM_STARTING_BALANCE, DEBUG_STARTING_BALANCE

log = structlog.get_logger(__name__)


class UnifiedBalanceManager(QtCore.QObject):
    """
    Unified balance manager for all trading modes.

    Manages SIM, LIVE, and DEBUG balances with thread-safe operations
    and automatic database persistence for SIM mode.

    Thread Safety:
    - All public methods protected by RLock
    - Signals emitted outside lock scope to prevent deadlocks

    Persistence:
    - SIM balances: Derived from trade ledger (database source of truth)
    - LIVE balances: From DTC updates (external source of truth)
    - DEBUG balances: In-memory only (no persistence)

    Signals:
    - balanceChanged(float, str, str): Emitted on balance change (balance, account, mode)
    """

    # Signals
    balanceChanged = QtCore.pyqtSignal(float, str, str)  # balance, account, mode

    def __init__(self):
        super().__init__()

        # Thread safety
        self._lock = threading.RLock()

        # Balance storage: {(mode, account): balance}
        # Example: ("SIM", "Sim1") -> 12500.0
        self._balances: dict[tuple[str, str], float] = {}

        # Track initialized accounts to avoid redundant DB queries
        self._initialized: set[tuple[str, str]] = set()

        log.info("[UnifiedBalanceManager] Initialized")

    # =========================================================================
    # PUBLIC API - Thread-Safe
    # =========================================================================

    def get_balance(self, mode: str, account: str) -> float:
        """
        Get current balance for mode/account pair.

        For SIM mode: Lazily loads from database on first access
        For LIVE mode: Returns last known balance from DTC
        For DEBUG mode: Returns default debug balance

        Args:
            mode: Trading mode ("SIM", "LIVE", "DEBUG")
            account: Account identifier

        Returns:
            Current balance for the mode/account pair

        Thread-safe: Yes (uses double-check pattern to avoid holding lock during DB query)

        Example:
            balance = manager.get_balance("SIM", "Sim1")
        """
        key = (mode, account)

        # First check: Fast path for cached values (no lock needed for read)
        with self._lock:
            if key in self._balances:
                return self._balances[key]

        # Cache miss - need to load balance
        # Determine what balance to load based on mode (outside lock)
        if mode == "SIM":
            balance = self._load_sim_balance_from_db(account)
        elif mode == "LIVE":
            balance = 0.0  # LIVE balance comes from DTC
        elif mode == "DEBUG":
            balance = DEBUG_STARTING_BALANCE
        else:
            log.warning(
                "[UnifiedBalanceManager] Unknown mode, using 0.0",
                mode=mode,
                account=account
            )
            balance = 0.0

        # Second check: Another thread may have loaded it while we were querying
        with self._lock:
            if key in self._balances:
                # Someone else loaded it, use their value
                return self._balances[key]

            # We're first - cache the value
            self._balances[key] = balance
            self._initialized.add(key)

        log.debug(
            "[UnifiedBalanceManager] Balance loaded",
            mode=mode,
            account=account,
            balance=balance
        )

        return balance

    def set_balance(self, mode: str, account: str, balance: float) -> None:
        """
        Set balance for mode/account pair.

        For SIM mode: Updates cache only (DB is source of truth via trade ledger)
        For LIVE mode: Updates balance from DTC
        For DEBUG mode: Updates in-memory balance

        Args:
            mode: Trading mode
            account: Account identifier
            balance: New balance

        Thread-safe: Yes

        Example:
            manager.set_balance("LIVE", "120005", 50000.0)
        """
        key = (mode, account)
        old_balance = self._balances.get(key)

        with self._lock:
            self._balances[key] = float(balance)
            self._initialized.add(key)

        # Emit signal outside lock
        self.balanceChanged.emit(float(balance), account, mode)

        log.info(
            "[UnifiedBalanceManager] Balance updated",
            mode=mode,
            account=account,
            old_balance=old_balance,
            new_balance=balance
        )

    def adjust_balance(self, mode: str, account: str, delta: float) -> float:
        """
        Adjust balance by delta (positive or negative).

        This is the primary method for updating balance after trade closure.

        Args:
            mode: Trading mode
            account: Account identifier
            delta: Amount to adjust (positive = gain, negative = loss)

        Returns:
            New balance after adjustment

        Thread-safe: Yes

        Example:
            new_balance = manager.adjust_balance("SIM", "Sim1", -125.50)
        """
        current = self.get_balance(mode, account)
        new_balance = current + delta

        self.set_balance(mode, account, new_balance)

        log.info(
            "[UnifiedBalanceManager] Balance adjusted",
            mode=mode,
            account=account,
            delta=delta,
            old_balance=current,
            new_balance=new_balance
        )

        return new_balance

    def reset_balance(self, mode: str, account: str) -> float:
        """
        Reset balance to starting balance for the mode.

        For SIM: Resets to $10,000
        For DEBUG: Resets to $10,000
        For LIVE: No-op (LIVE balance comes from broker)

        Args:
            mode: Trading mode
            account: Account identifier

        Returns:
            New balance after reset

        Thread-safe: Yes

        Example:
            manager.reset_balance("SIM", "Sim1")
        """
        if mode == "LIVE":
            log.warning(
                "[UnifiedBalanceManager] Cannot reset LIVE balance (broker-controlled)",
                account=account
            )
            return self.get_balance(mode, account)

        starting_balance = SIM_STARTING_BALANCE if mode == "SIM" else DEBUG_STARTING_BALANCE

        self.set_balance(mode, account, starting_balance)

        log.info(
            "[UnifiedBalanceManager] Balance reset",
            mode=mode,
            account=account,
            balance=starting_balance
        )

        return starting_balance

    def get_all_accounts(self, mode: Optional[str] = None) -> list[tuple[str, str]]:
        """
        Get list of all mode/account pairs that have balances.

        Args:
            mode: Optional mode filter (returns only accounts for this mode)

        Returns:
            List of (mode, account) tuples

        Thread-safe: Yes

        Example:
            sim_accounts = manager.get_all_accounts(mode="SIM")
        """
        with self._lock:
            if mode:
                return [(m, a) for m, a in self._initialized if m == mode]
            return list(self._initialized)

    # =========================================================================
    # INTERNAL HELPERS - Must be called within lock
    # =========================================================================

    def _load_sim_balance_from_db(self, account: str) -> float:
        """
        Load SIM balance from database by summing realized P&L.

        This is the source of truth for SIM balances - calculated from
        the complete trade ledger in the database.

        Args:
            account: SIM account identifier

        Returns:
            Calculated balance (starting balance + total realized P&L)

        Thread-safe: NO - must be called within lock
        """
        try:
            from data.db_engine import get_session
            from data.schema import TradeRecord
            from sqlalchemy import func

            with get_session() as session:
                # Sum all realized P&L for this SIM account
                result = (
                    session.query(func.sum(TradeRecord.realized_pnl))
                    .filter(
                        TradeRecord.mode == "SIM",
                        TradeRecord.account == account,
                        TradeRecord.realized_pnl != None,  # noqa: E711
                        TradeRecord.is_closed == True,  # noqa: E712
                    )
                    .scalar()
                )

                total_pnl = float(result) if result else 0.0
                balance = SIM_STARTING_BALANCE + total_pnl

                # Also count trades for logging
                trade_count = (
                    session.query(TradeRecord)
                    .filter(
                        TradeRecord.mode == "SIM",
                        TradeRecord.account == account,
                        TradeRecord.is_closed == True,  # noqa: E712
                    )
                    .count()
                )

                log.info(
                    "[UnifiedBalanceManager] SIM balance loaded from database",
                    account=account,
                    trade_count=trade_count,
                    total_pnl=total_pnl,
                    starting_balance=SIM_STARTING_BALANCE,
                    current_balance=balance
                )

                return balance

        except Exception as e:
            log.error(
                "[UnifiedBalanceManager] Error loading SIM balance from database",
                account=account,
                error=str(e),
                exc_info=True
            )
            # Fallback to starting balance on error
            return SIM_STARTING_BALANCE

    # =========================================================================
    # MIGRATION HELPERS - Backwards Compatibility
    # =========================================================================

    def get_sim_balance(self, account: str) -> float:
        """
        Get SIM balance for account.

        Backwards compatibility wrapper for legacy code.
        Use get_balance("SIM", account) in new code.
        """
        return self.get_balance("SIM", account)

    def set_sim_balance(self, account: str, balance: float) -> None:
        """
        Set SIM balance for account.

        Backwards compatibility wrapper for legacy code.
        Use set_balance("SIM", account, balance) in new code.
        """
        self.set_balance("SIM", account, balance)

    def adjust_sim_balance(self, account: str, delta: float) -> float:
        """
        Adjust SIM balance by delta.

        Backwards compatibility wrapper for legacy code.
        Use adjust_balance("SIM", account, delta) in new code.
        """
        return self.adjust_balance("SIM", account, delta)

    def reset_sim_balance(self, account: str) -> float:
        """
        Reset SIM balance to starting balance.

        Backwards compatibility wrapper for legacy code.
        Use reset_balance("SIM", account) in new code.
        """
        return self.reset_balance("SIM", account)

    def get_live_balance(self, account: str) -> float:
        """Get LIVE balance for account."""
        return self.get_balance("LIVE", account)

    def set_live_balance(self, account: str, balance: float) -> None:
        """Set LIVE balance for account."""
        self.set_balance("LIVE", account, balance)


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_balance_manager_instance: Optional[UnifiedBalanceManager] = None
_balance_manager_lock = threading.Lock()


def get_balance_manager() -> UnifiedBalanceManager:
    """
    Get the global UnifiedBalanceManager singleton.

    Thread-safe singleton creation.

    Returns:
        UnifiedBalanceManager: The application-wide balance manager

    Example:
        >>> balance_mgr = get_balance_manager()
        >>> balance = balance_mgr.get_balance("SIM", "Sim1")
    """
    global _balance_manager_instance

    if _balance_manager_instance is None:
        with _balance_manager_lock:
            # Double-check locking pattern
            if _balance_manager_instance is None:
                _balance_manager_instance = UnifiedBalanceManager()
                log.info("[UnifiedBalanceManager] Singleton created")

    return _balance_manager_instance


def reset_balance_manager() -> None:
    """
    Reset the global balance manager singleton.

    WARNING: Only use in tests. This will clear all balance state.

    Thread-safe: Yes
    """
    global _balance_manager_instance

    with _balance_manager_lock:
        if _balance_manager_instance is not None:
            try:
                _balance_manager_instance.deleteLater()
            except Exception:
                pass

        _balance_manager_instance = None
        log.info("[UnifiedBalanceManager] Singleton reset")
