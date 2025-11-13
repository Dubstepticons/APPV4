"""
services/position_recovery.py

Position recovery service for crash/restart scenarios.

This module handles restoring open positions from database to application state
after crashes, restarts, or unexpected shutdowns.

Key Operations:
- recover_positions_on_startup(): Main entry point for app startup
- restore_position_to_state_manager(): Sync DB → StateManager
- restore_position_to_panel2(): Sync DB → Panel2 UI
- reconcile_stale_positions(): Handle positions older than threshold

Thread Safety: All operations are thread-safe via repository pattern.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from data.position_repository import get_position_repository
from utils.logger import get_logger

log = get_logger(__name__)


class PositionRecoveryService:
    """
    Service for recovering open positions from database on startup.

    Implements crash recovery strategy:
    1. Query all open positions from database
    2. Restore to StateManager (in-memory cache)
    3. Restore to Panel2 (UI display) if mode matches
    4. Log recovery summary for observability
    """

    def __init__(self):
        self.position_repo = get_position_repository()

    def recover_positions_on_startup(
        self,
        state_manager,
        panel2=None,
        max_age_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Recover all open positions from database on app startup.

        Main entry point for position recovery. Should be called from
        app_manager.py after StateManager and Panel2 are initialized.

        Args:
            state_manager: StateManager instance (required)
            panel2: Panel2 instance (optional, for UI display)
            max_age_hours: Maximum age in hours for valid positions (default: 24)
                          Positions older than this are flagged as potentially stale

        Returns:
            Recovery summary dict with:
            - recovered_count: Number of positions recovered
            - stale_count: Number of positions older than max_age_hours
            - restored_to_panel2: Boolean, True if position restored to Panel2
            - positions: List of recovered position dicts

        Thread-Safe: Yes (via repository)
        """
        try:
            log.info("[PositionRecovery] Starting position recovery from database...")

            # 1. Query all open positions from database
            positions = self.position_repo.recover_all_open_positions()

            if not positions:
                log.info("[PositionRecovery] No open positions to recover")
                return {
                    "recovered_count": 0,
                    "stale_count": 0,
                    "restored_to_panel2": False,
                    "positions": []
                }

            # 2. Classify positions (fresh vs stale)
            now_utc = datetime.now(timezone.utc)
            stale_threshold = timedelta(hours=max_age_hours)

            fresh_positions = []
            stale_positions = []

            for pos in positions:
                # Calculate age
                age = now_utc - pos["updated_at"]

                if age > stale_threshold:
                    stale_positions.append(pos)
                    log.warning(
                        f"[PositionRecovery] Stale position detected: "
                        f"{pos['mode']}/{pos['account']} {pos['symbol']} "
                        f"age={age.total_seconds()/3600:.1f}h"
                    )
                else:
                    fresh_positions.append(pos)

            # 3. Restore fresh positions to StateManager
            for pos in fresh_positions:
                self._restore_position_to_state_manager(state_manager, pos)

            # 4. Restore position to Panel2 if mode matches
            restored_to_panel2 = False
            if panel2 and fresh_positions:
                current_mode = state_manager.current_mode
                current_account = state_manager.current_account or ""

                # Find position matching current mode/account
                matching_position = None
                for pos in fresh_positions:
                    if pos["mode"] == current_mode and pos["account"] == current_account:
                        matching_position = pos
                        break

                if matching_position:
                    self._restore_position_to_panel2(panel2, matching_position)
                    restored_to_panel2 = True

            # 5. Log recovery summary
            total_recovered = len(fresh_positions)
            total_stale = len(stale_positions)

            log.info(
                f"[PositionRecovery] Recovery complete: "
                f"recovered={total_recovered}, stale={total_stale}, "
                f"restored_to_panel2={restored_to_panel2}"
            )

            if fresh_positions:
                for pos in fresh_positions:
                    log.info(
                        f"[PositionRecovery] Recovered: {pos['mode']}/{pos['account']} "
                        f"{pos['symbol']} {pos['side']} {abs(pos['qty'])}@{pos['entry_price']}"
                    )

            if stale_positions:
                log.warning(
                    f"[PositionRecovery] WARNING: {total_stale} stale position(s) detected. "
                    "These may need manual review/cleanup."
                )

            return {
                "recovered_count": total_recovered,
                "stale_count": total_stale,
                "restored_to_panel2": restored_to_panel2,
                "positions": fresh_positions,
                "stale_positions": stale_positions,
            }

        except Exception as e:
            log.error(f"[PositionRecovery] Error during position recovery: {e}")
            return {
                "recovered_count": 0,
                "stale_count": 0,
                "restored_to_panel2": False,
                "positions": [],
                "error": str(e)
            }

    def _restore_position_to_state_manager(
        self,
        state_manager,
        position: Dict[str, Any]
    ) -> bool:
        """
        Restore position from database to StateManager.

        Args:
            state_manager: StateManager instance
            position: Position dict from database

        Returns:
            True if restore succeeded, False otherwise

        Thread-Safe: Yes (StateManager methods are thread-safe)
        """
        try:
            # Restore position to StateManager
            state_manager.open_position(
                symbol=position["symbol"],
                qty=position["qty"],  # Signed quantity
                entry_price=position["entry_price"],
                entry_time=position["entry_time"],
                mode=position["mode"]
            )

            # Restore entry snapshots
            state_manager.entry_vwap = position.get("entry_vwap")
            state_manager.entry_cum_delta = position.get("entry_cum_delta")
            state_manager.entry_poc = position.get("entry_poc")

            log.debug(
                f"[PositionRecovery] Restored to StateManager: "
                f"{position['mode']}/{position['account']} {position['symbol']}"
            )

            return True

        except Exception as e:
            log.error(f"[PositionRecovery] Error restoring to StateManager: {e}")
            return False

    def _restore_position_to_panel2(
        self,
        panel2,
        position: Dict[str, Any]
    ) -> bool:
        """
        Restore position from database to Panel2 UI.

        Args:
            panel2: Panel2 instance
            position: Position dict from database

        Returns:
            True if restore succeeded, False otherwise

        Thread-Safe: Must be called from Qt GUI thread
        """
        try:
            # Restore position to Panel2
            is_long = position["qty"] > 0
            abs_qty = abs(position["qty"])

            panel2.set_position(
                qty=abs_qty,
                entry_price=position["entry_price"],
                is_long=is_long
            )

            # Restore timer state
            panel2.entry_time_epoch = int(position["entry_time"].timestamp())

            # Restore trade extremes (for MAE/MFE)
            panel2._trade_min_price = position.get("trade_min_price")
            panel2._trade_max_price = position.get("trade_max_price")

            # Restore bracket orders if set
            if position.get("target_price"):
                panel2.target_price = position["target_price"]
            if position.get("stop_price"):
                panel2.stop_price = position["stop_price"]

            # Trigger UI refresh
            panel2._refresh_all_cells()

            log.info(
                f"[PositionRecovery] Restored to Panel2: "
                f"{position['symbol']} {position['side']} "
                f"{abs_qty}@{position['entry_price']}"
            )

            return True

        except Exception as e:
            log.error(f"[PositionRecovery] Error restoring to Panel2: {e}")
            return False

    def get_recovery_dialog_message(
        self,
        recovery_summary: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate user-friendly message for recovery dialog.

        If positions were recovered, returns a message to show to the user.
        Otherwise, returns None.

        Args:
            recovery_summary: Dict returned from recover_positions_on_startup()

        Returns:
            Message string if positions recovered, None otherwise
        """
        recovered_count = recovery_summary.get("recovered_count", 0)
        stale_count = recovery_summary.get("stale_count", 0)

        if recovered_count == 0 and stale_count == 0:
            return None

        lines = []

        if recovered_count > 0:
            lines.append(f"✅ Recovered {recovered_count} open position(s) from previous session:")
            for pos in recovery_summary.get("positions", []):
                side = pos['side']
                qty = abs(pos['qty'])
                symbol = pos['symbol']
                entry = pos['entry_price']
                mode = pos['mode']
                lines.append(f"  • {mode}: {side} {qty} {symbol} @ {entry}")

        if stale_count > 0:
            lines.append("")
            lines.append(f"⚠️  WARNING: {stale_count} stale position(s) detected (>24h old)")
            lines.append("These positions may have been closed by your broker.")
            lines.append("Please verify with Sierra Chart and manually close if needed.")
            for pos in recovery_summary.get("stale_positions", []):
                symbol = pos['symbol']
                mode = pos['mode']
                age_hours = (datetime.now(timezone.utc) - pos['updated_at']).total_seconds() / 3600
                lines.append(f"  • {mode}: {symbol} (age: {age_hours:.1f}h)")

        return "\n".join(lines)

    def cleanup_stale_positions(
        self,
        max_age_hours: int = 48
    ) -> int:
        """
        Clean up stale positions from database.

        Deletes open positions older than max_age_hours.
        Use with caution - this permanently deletes position records.

        Args:
            max_age_hours: Maximum age in hours (default: 48)

        Returns:
            Number of positions deleted

        Thread-Safe: Yes
        """
        try:
            positions = self.position_repo.recover_all_open_positions()

            now_utc = datetime.now(timezone.utc)
            stale_threshold = timedelta(hours=max_age_hours)

            deleted_count = 0
            for pos in positions:
                age = now_utc - pos["updated_at"]

                if age > stale_threshold:
                    success = self.position_repo.delete_open_position(
                        mode=pos["mode"],
                        account=pos["account"]
                    )
                    if success:
                        deleted_count += 1
                        log.info(
                            f"[PositionRecovery] Cleaned up stale position: "
                            f"{pos['mode']}/{pos['account']} {pos['symbol']} "
                            f"age={age.total_seconds()/3600:.1f}h"
                        )

            if deleted_count > 0:
                log.info(f"[PositionRecovery] Cleaned up {deleted_count} stale position(s)")

            return deleted_count

        except Exception as e:
            log.error(f"[PositionRecovery] Error cleaning up stale positions: {e}")
            return 0


# Global service instance (singleton pattern)
_recovery_service: Optional[PositionRecoveryService] = None


def get_recovery_service() -> PositionRecoveryService:
    """
    Get global PositionRecoveryService instance (singleton).

    Returns:
        PositionRecoveryService instance
    """
    global _recovery_service
    if _recovery_service is None:
        _recovery_service = PositionRecoveryService()
    return _recovery_service


def recover_positions_on_startup(
    state_manager,
    panel2=None,
    max_age_hours: int = 24
) -> Dict[str, Any]:
    """
    Convenience function for position recovery on app startup.

    This is the main entry point that should be called from app_manager.py.

    Args:
        state_manager: StateManager instance (required)
        panel2: Panel2 instance (optional)
        max_age_hours: Maximum age for valid positions (default: 24)

    Returns:
        Recovery summary dict

    Example usage in app_manager.py:
        from services.position_recovery import recover_positions_on_startup

        # After StateManager and Panel2 are initialized
        recovery_summary = recover_positions_on_startup(
            state_manager=self.state_manager,
            panel2=self.panel_live,
            max_age_hours=24
        )

        # Optionally show dialog to user
        if recovery_summary.get("recovered_count", 0) > 0:
            from services.position_recovery import get_recovery_service
            service = get_recovery_service()
            message = service.get_recovery_dialog_message(recovery_summary)
            if message:
                # Show Qt dialog
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Position Recovery", message)
    """
    service = get_recovery_service()
    return service.recover_positions_on_startup(
        state_manager=state_manager,
        panel2=panel2,
        max_age_hours=max_age_hours
    )
