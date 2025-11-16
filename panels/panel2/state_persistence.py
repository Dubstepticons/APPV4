"""
panels/panel2/state_persistence.py

State persistence handler for Panel2.

This module handles loading and saving position state to:
1. JSON files (for session timers and heat tracking)
2. Database (for position data via PositionService)

Architecture:
- Atomic writes (no partial/corrupted state)
- Mode-scoped files (separate state per SIM/LIVE/DEBUG)
- Account-scoped (separate state per account)
- Crash recovery via database priority

Usage:
    from panels.panel2.state_persistence import StatePersistence
    from panels.panel2.position_state import PositionState

    persistence = StatePersistence(mode="SIM", account="Sim1")

    # Save state
    persistence.save_state(position_state)

    # Load state (tries DB first, then JSON)
    state = persistence.load_state()
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import structlog

from .position_state import PositionState

log = structlog.get_logger(__name__)

STATE_PERSISTENCE_DEBUG = os.getenv("APPSIERRA_STATE_PERSISTENCE_DEBUG", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _debug_log(message: str, **kwargs) -> None:
    if STATE_PERSISTENCE_DEBUG:
        log.debug(message, **kwargs)


class StatePersistence:
    """
    Handles state loading/saving for Panel2.

    Manages both JSON files (for UI-specific state like heat timers)
    and database (for position data).

    State priority:
    1. Database (source of truth for positions)
    2. JSON file (fallback for UI state)
    """

    def __init__(self, mode: str, account: str):
        """
        Initialize state persistence.

        Args:
            mode: Trading mode ("SIM", "LIVE", "DEBUG")
            account: Account identifier
        """
        self.mode = mode
        self.account = account

        log.info(
            "[StatePersistence] Initialized",
            mode=mode,
            account=account
        )

    def _get_state_path(self) -> Path:
        """
        Get scoped state file path for current (mode, account).

        Returns:
            Path to state file: data/runtime_state_panel2_{mode}_{account}.json
        """
        from utils.atomic_persistence import get_scoped_path

        path = get_scoped_path("runtime_state_panel2", self.mode, self.account)
        return path

    def save_state(self, state: PositionState) -> bool:
        """
        Save position state to JSON file.

        This saves UI-specific state (heat timers, trade extremes) to JSON.
        Position data is automatically saved to database via PositionService.

        Args:
            state: Position state to save

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            from utils.atomic_persistence import save_json_atomic

            state_path = self._get_state_path()

            # Save state dict
            data = state.to_dict()

            success = save_json_atomic(data, state_path)

            if success:
                _debug_log(
                    "[StatePersistence] Saved session state",
                    mode=self.mode,
                    account=self.account,
                    path=str(state_path)
                )
            else:
                log.warning(
                    "[StatePersistence] Failed to save state",
                    mode=self.mode,
                    account=self.account
                )

            return success

        except Exception as e:
            log.error(
                "[StatePersistence] Save error",
                error=str(e),
                mode=self.mode,
                account=self.account,
                exc_info=True
            )
            return False

    def load_state(self) -> Optional[PositionState]:
        """
        Load position state.

        Priority:
        1. Database (via PositionService) - source of truth for positions
        2. JSON file - fallback for UI state

        Returns:
            PositionState instance, or None if no state found
        """
        # Try database first (priority 1)
        state = self._load_from_database()
        if state is not None:
            return state

        # Fallback to JSON file (priority 2)
        state = self._load_from_json()
        if state is not None:
            return state

        # No state found - return flat state
        _debug_log(
            "[StatePersistence] No persisted state found",
            mode=self.mode,
            account=self.account
        )
        return PositionState.flat(mode=self.mode, account=self.account)

    def _load_from_json(self) -> Optional[PositionState]:
        """
        Load state from JSON file.

        Returns:
            PositionState instance, or None if file doesn't exist or is invalid
        """
        try:
            from utils.atomic_persistence import load_json_atomic

            state_path = self._get_state_path()
            data = load_json_atomic(str(state_path))

            if not data:
                return None

            # Create PositionState from dict
            state = PositionState.from_dict(data)

            log.info(
                "[StatePersistence] Restored state from JSON",
                mode=self.mode,
                account=self.account,
                has_position=state.has_position()
            )

            return state

        except Exception as e:
            log.warning(
                "[StatePersistence] Failed to load from JSON",
                error=str(e),
                mode=self.mode,
                account=self.account
            )
            return None

    def _load_from_database(self) -> Optional[PositionState]:
        """
        Load position from database via PositionService.

        This is the source of truth for position data.

        Returns:
            PositionState instance, or None if no open position
        """
        try:
            from services.position_service import get_position_service

            position_service = get_position_service()
            position = position_service.get_open_position(
                mode=self.mode,
                account=self.account
            )

            if position is None:
                _debug_log(
                    "[StatePersistence] No open position in database",
                    mode=self.mode,
                    account=self.account
                )
                return None

            # Convert Position domain model to PositionState
            # We need current market data, but we don't have it yet
            # Return with default market data (will be updated by CSV feed)
            market_data = {
                "last_price": 0.0,
                "session_high": 0.0,
                "session_low": 0.0,
                "vwap": 0.0,
                "cum_delta": 0.0,
                "poc": 0.0,
            }

            state = PositionState.from_position_domain(position, market_data)

            log.info(
                "[StatePersistence] Restored position from database",
                mode=self.mode,
                account=self.account,
                symbol=state.symbol,
                qty=state.entry_qty,
                entry_price=state.entry_price
            )

            return state

        except Exception as e:
            log.error(
                "[StatePersistence] Failed to load from database",
                error=str(e),
                mode=self.mode,
                account=self.account,
                exc_info=True
            )
            return None

    def clear_state(self) -> bool:
        """
        Clear persisted state (JSON file only).

        Note: Database position is not cleared - use PositionService for that.

        Returns:
            True if clear succeeded, False otherwise
        """
        try:
            state_path = self._get_state_path()

            if state_path.exists():
                state_path.unlink()
                log.info(
                    "[StatePersistence] Cleared persisted state",
                    mode=self.mode,
                    account=self.account
                )
                return True
            else:
                _debug_log(
                    "[StatePersistence] No state file to clear",
                    mode=self.mode,
                    account=self.account
                )
                return True

        except Exception as e:
            log.error(
                "[StatePersistence] Failed to clear state",
                error=str(e),
                mode=self.mode,
                account=self.account,
                exc_info=True
            )
            return False

    def save_position_to_database(self, state: PositionState) -> bool:
        """
        Save open position to database via PositionService.

        This is called when position is opened or updated.

        Args:
            state: Position state to save

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            from services.position_service import get_position_service
            from domain.position import Position
            from datetime import datetime, timezone

            if state.is_flat():
                _debug_log(
                    "[StatePersistence] Not saving flat position to database",
                    mode=self.mode,
                    account=self.account
                )
                return True

            position_service = get_position_service()

            # Create Position domain model from state
            position = Position(
                symbol=state.symbol,
                qty=state.entry_qty if state.is_long else -state.entry_qty,
                entry_price=state.entry_price,
                entry_time=datetime.fromtimestamp(state.entry_time_epoch, tz=timezone.utc) if state.entry_time_epoch else datetime.now(timezone.utc),
                mode=state.current_mode,
                account=state.current_account,
                target_price=state.target_price,
                stop_price=state.stop_price,
                entry_vwap=state.entry_vwap,
                entry_cum_delta=state.entry_cum_delta,
                entry_poc=state.entry_poc,
            )

            # Upsert to database
            position_service.save_open_position(
                mode=self.mode,
                account=self.account,
                symbol=position.symbol,
                qty=position.qty,
                entry_price=position.entry_price,
                entry_time_epoch=state.entry_time_epoch,
                entry_vwap=position.entry_vwap,
                entry_cum_delta=position.entry_cum_delta,
                entry_poc=position.entry_poc,
                target_price=position.target_price,
                stop_price=position.stop_price,
            )

            log.info(
                "[StatePersistence] Saved position to database",
                mode=self.mode,
                account=self.account,
                symbol=state.symbol,
                qty=state.entry_qty
            )

            return True

        except Exception as e:
            log.error(
                "[StatePersistence] Failed to save position to database",
                error=str(e),
                mode=self.mode,
                account=self.account,
                exc_info=True
            )
            return False

    def close_position_in_database(self) -> bool:
        """
        Close (remove) open position from database.

        Called when position is closed.

        Returns:
            True if close succeeded, False otherwise
        """
        try:
            from data.position_repository import get_position_repository

            repo = get_position_repository()
            # Use last stored price if available; fall back to entry
            exit_price = self._state.trade_max_price if hasattr(self, "_state") else 0.0
            repo.close_position(
                mode=self.mode,
                account=self.account,
                exit_price=exit_price,
            )

            log.info(
                "[StatePersistence] Closed position in database",
                mode=self.mode,
                account=self.account
            )

            return True

        except Exception as e:
            log.error(
                "[StatePersistence] Failed to close position in database",
                error=str(e),
                mode=self.mode,
                account=self.account,
                exc_info=True
            )
            return False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def migrate_state_file(old_path: str, new_mode: str, new_account: str) -> bool:
    """
    Migrate state file to new mode/account.

    Useful when changing mode or account naming.

    Args:
        old_path: Old state file path
        new_mode: New mode
        new_account: New account

    Returns:
        True if migration succeeded, False otherwise
    """
    try:
        from utils.atomic_persistence import load_json_atomic

        # Load old state
        data = load_json_atomic(old_path)
        if not data:
            return False

        # Update mode/account
        data["current_mode"] = new_mode
        data["current_account"] = new_account

        # Save to new location
        persistence = StatePersistence(new_mode, new_account)
        state = PositionState.from_dict(data)
        success = persistence.save_state(state)

        if success:
            # Remove old file
            Path(old_path).unlink()
            log.info(
                "[StatePersistence] Migrated state file",
                old_path=old_path,
                new_mode=new_mode,
                new_account=new_account
            )

        return success

    except Exception as e:
        log.error(
            "[StatePersistence] Migration failed",
            error=str(e),
            old_path=old_path,
            exc_info=True
        )
        return False
