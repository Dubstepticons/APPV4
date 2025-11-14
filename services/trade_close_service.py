"""
services/trade_close_service.py

Trade Closure Service - Orchestrates position closing via event-driven architecture.

ARCHITECTURE (Step 7): Service-layer trade lifecycle
================================================================================
This service implements the target architecture:
  UI → Intent Signal → Service → Repository + StateManager → Outcome Signal → UI

TradeCloseService responsibilities:
  1. Subscribe to SignalBus.tradeCloseRequested (INTENT from Panel2)
  2. Validate mode/account consistency with StateManager
  3. Call PositionRepository.close_position() (single DB writer)
  4. Update balances via StateManager (single balance cache)
  5. Emit SignalBus.positionClosed and tradeClosedForAnalytics (OUTCOMES)

Benefits:
  - Panel2 no longer calls repository directly (decoupled)
  - Service layer owns business rules (not UI)
  - StateManager is the coordination point
  - Database remains single source of truth
  - Testable without UI
================================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any
from PyQt6 import QtCore

from utils.logger import get_logger

log = get_logger(__name__)


class TradeCloseService(QtCore.QObject):
    """
    Service for handling trade closure requests.

    Subscribes to tradeCloseRequested and orchestrates the closure pipeline:
    validate → close in DB → update StateManager → emit outcomes
    """

    def __init__(self):
        super().__init__()
        self.state_manager = None
        self.signal_bus = None

    def initialize(self, state_manager, signal_bus):
        """
        Initialize with dependencies and wire up signals.

        Args:
            state_manager: StateManager instance for mode/balance coordination
            signal_bus: SignalBus instance for event communication
        """
        self.state_manager = state_manager
        self.signal_bus = signal_bus

        # Subscribe to trade close requests from UI
        signal_bus.tradeCloseRequested.connect(
            self._on_trade_close_requested,
            QtCore.Qt.ConnectionType.QueuedConnection
        )

        log.info("[TradeCloseService] Initialized and subscribed to tradeCloseRequested")

    def _on_trade_close_requested(self, trade: dict) -> None:
        """
        Handle trade close request from UI (Panel2).

        Args:
            trade: Trade dict with exit context from Panel2
                Required: exit_price, symbol, account
                Optional: exit_time, mae, mfe, efficiency, entry_vwap, etc.
        """
        try:
            log.info(
                f"[TradeCloseService] Trade close requested: "
                f"symbol={trade.get('symbol')}, account={trade.get('account')}, exit_price={trade.get('exit_price')}"
            )

            # Validate required fields
            exit_price = trade.get("exit_price")
            if exit_price is None:
                log.error("[TradeCloseService] Missing exit_price in trade close request")
                self._emit_error("Trade close failed: missing exit_price")
                return

            account = trade.get("account")
            if not account:
                log.error("[TradeCloseService] Missing account in trade close request")
                self._emit_error("Trade close failed: missing account")
                return

            # Determine mode from StateManager (single source of truth)
            if not self.state_manager:
                log.error("[TradeCloseService] StateManager not initialized")
                self._emit_error("Trade close failed: StateManager not available")
                return

            # CRITICAL FIX: Always derive mode from account first (most reliable)
            from utils.trade_mode import detect_mode_from_account
            derived_mode = detect_mode_from_account(account)

            # Use StateManager's mode/account when available; otherwise fall back to trade data.
            mode = self.state_manager.current_mode
            canonical_account = self.state_manager.current_account

            # Check for mode mismatch: if trade's account implies a different mode, trust the account
            # This handles the case where StateManager is still at default but trade is from SIM
            if mode != derived_mode:
                log.info(
                    "[TradeCloseService] Mode mismatch detected: "
                    f"state_mode={mode}, account_derived_mode={derived_mode}, account={account} "
                    f"-> Using account-derived mode {derived_mode}"
                )
                mode = derived_mode

            # Use canonical account from StateManager if available
            if canonical_account:
                if account != canonical_account:
                    log.warning(
                        "[TradeCloseService] Account mismatch: "
                        f"trade_account={account}, state_account={canonical_account}, using_state_account=True"
                    )
                    account = canonical_account

            log.debug(
                f"[TradeCloseService] Closing position: mode={mode}, account={account}, symbol={trade.get('symbol')}"
            )

            # Close position in database (via repository - only writer to DB)
            closed_position = self._close_position_in_db(mode, account, trade)
            if not closed_position:
                log.error("[TradeCloseService] Failed to close position in database")
                self._emit_error("Trade close failed: database error")
                return

            # Update balances in StateManager (single balance cache)
            realized_pnl = closed_position.get("realized_pnl", 0.0)
            if realized_pnl is not None and mode == "SIM":
                current_balance = self.state_manager.get_balance_for_mode(mode)
                new_balance = current_balance + realized_pnl

                log.info(
                    f"[TradeCloseService] Updating {mode} balance: "
                    f"old_balance={current_balance}, pnl={realized_pnl}, new_balance={new_balance}"
                )

                self.state_manager.set_balance_for_mode(mode, new_balance)

            # Clear position state in StateManager
            self.state_manager.close_position()

            # Emit outcome events for UI updates
            self._emit_position_closed(closed_position)
            self._emit_trade_for_analytics(closed_position)

            log.info(
                f"[TradeCloseService] Trade closed successfully: mode={mode}, account={account}, pnl={realized_pnl}"
            )

        except Exception as e:
            log.error(f"[TradeCloseService] Error closing trade: {e}", exc_info=True)
            self._emit_error(f"Trade close failed: {str(e)}")

    def _close_position_in_db(self, mode: str, account: str, trade: dict) -> Optional[dict]:
        """
        Close position in database via PositionRepository.

        Returns:
            dict with closed position details, or None if failed
        """
        try:
            from data.position_repository import get_position_repository

            position_repo = get_position_repository()

            # Extract exit data from trade dict
            exit_price = trade.get("exit_price")
            exit_time = trade.get("exit_time")
            if exit_time is None:
                exit_time = datetime.now(timezone.utc)

            # Optional analytics data
            mae = trade.get("mae")
            mfe = trade.get("mfe")
            efficiency = trade.get("efficiency")
            commissions = trade.get("commissions")
            r_multiple = trade.get("r_multiple")

            # Entry/exit snapshots
            entry_vwap = trade.get("entry_vwap")
            entry_cum_delta = trade.get("entry_cum_delta")
            exit_vwap = trade.get("exit_vwap")
            exit_cum_delta = trade.get("exit_cum_delta")
            # For SIM mode, the historical schema uses empty-string account as the key.
            # Map SIM accounts like "Sim1" to "" for repository calls, but keep the
            # original account on the closed_position payload for UI/analytics.
            repo_account = account
            if mode == "SIM" and account and account.lower().startswith("sim"):
                repo_account = ""

            # Close position in DB (atomic operation)
            trade_id = position_repo.close_position(
                mode=mode,
                account=repo_account,
                exit_price=exit_price,
                exit_time=exit_time,
                realized_pnl=trade.get("realized_pnl"),
                commissions=commissions,
                exit_vwap=exit_vwap,
                exit_cum_delta=exit_cum_delta,
            )

            if not trade_id:
                log.error(
                    f"[TradeCloseService] PositionRepository.close_position returned no trade_id "
                    f"for mode={mode}, account={account}"
                )
                return None

            # Build closed position payload for UI and analytics signals.
            # Use the original trade dict as a base, but ensure canonical mode/account
            # and include the trade_id returned from the repository.
            closed_position: dict[str, Any] = dict(trade)
            closed_position["trade_id"] = trade_id
            closed_position["mode"] = mode
            closed_position["account"] = account

            # Ensure realized_pnl is present for balance updates; fall back to 0.0
            if closed_position.get("realized_pnl") is None:
                closed_position["realized_pnl"] = 0.0

            log.info(
                f"[TradeCloseService] Position closed in DB: "
                f"mode={mode}, account={account}, trade_id={trade_id}, "
                f"pnl={closed_position.get('realized_pnl')}"
            )

            return closed_position

        except Exception as e:
            log.error(f"[TradeCloseService] DB close failed: {e}", exc_info=True)
            return None

    def _emit_position_closed(self, closed_position: dict) -> None:
        """Emit positionClosed signal for UI updates (Panel2)."""
        try:
            if self.signal_bus:
                self.signal_bus.positionClosed.emit(closed_position)
                log.debug("[TradeCloseService] Emitted positionClosed signal")
        except Exception as e:
            log.error(f"[TradeCloseService] Failed to emit positionClosed: {e}")

    def _emit_trade_for_analytics(self, closed_position: dict) -> None:
        """Emit tradeClosedForAnalytics signal for Panel3 updates."""
        try:
            if self.signal_bus:
                self.signal_bus.tradeClosedForAnalytics.emit(closed_position)
                log.debug("[TradeCloseService] Emitted tradeClosedForAnalytics signal")
        except Exception as e:
            log.error(f"[TradeCloseService] Failed to emit tradeClosedForAnalytics: {e}")

    def _emit_error(self, message: str) -> None:
        """Emit error message to UI (status bar)."""
        try:
            if self.signal_bus:
                self.signal_bus.errorMessagePosted.emit(message)
                log.debug(f"[TradeCloseService] Emitted error: {message}")
        except Exception as e:
            log.error(f"[TradeCloseService] Failed to emit error: {e}")


# Singleton instance
_trade_close_service: Optional[TradeCloseService] = None


def get_trade_close_service() -> TradeCloseService:
    """Get singleton TradeCloseService instance."""
    global _trade_close_service
    if _trade_close_service is None:
        _trade_close_service = TradeCloseService()
    return _trade_close_service
