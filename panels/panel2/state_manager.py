"""
State Manager Module

SINGLE SOURCE OF TRUTH for all Panel2 state.

Architecture Contract:
- Owns ALL state variables (position, feed, timers, extremes)
- Provides get/set/reset methods ONLY
- No business logic except mode scoping and persistence
- No UI access, no calculations

State Structure:
- Mode-scoped: Each (mode, account) pair has isolated state
- Persistent: Timers and extremes survive app restarts
- Atomic: All updates go through this module
"""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field, asdict
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class Panel2State:
    """
    Complete state container for Panel2.

    All fields default to None/0 to represent "flat" state.
    Mode switching creates fresh instances of this class.
    """
    # Mode scoping
    mode: str = "SIM"
    account: str = ""

    # Position state (from DTC PositionUpdate)
    symbol: str = "ES"
    entry_price: Optional[float] = None
    entry_qty: int = 0
    is_long: Optional[bool] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Feed state (from CSV, continuously updated)
    last_price: Optional[float] = None
    session_high: Optional[float] = None
    session_low: Optional[float] = None
    vwap: Optional[float] = None
    cum_delta: Optional[float] = None
    poc: Optional[float] = None

    # Entry snapshots (captured once at position open, frozen)
    entry_vwap: Optional[float] = None
    entry_delta: Optional[float] = None
    entry_poc: Optional[float] = None

    # Timers (persisted across restarts)
    entry_time_epoch: Optional[int] = None
    heat_start_epoch: Optional[int] = None

    # Trade extremes (for MAE/MFE tracking)
    trade_min_price: Optional[float] = None
    trade_max_price: Optional[float] = None

    # Internal flags
    _last_exit_fill_price: Optional[float] = None  # Captured from OrderUpdate

    def is_flat(self) -> bool:
        """Check if position is flat (no active trade)."""
        return self.entry_qty == 0 or self.entry_price is None or self.is_long is None

    def has_position(self) -> bool:
        """Check if position is open."""
        return not self.is_flat()

    def reset_position(self) -> None:
        """Reset all position-specific fields to flat state."""
        self.entry_price = None
        self.entry_qty = 0
        self.is_long = None
        self.target_price = None
        self.stop_price = None
        self.entry_vwap = None
        self.entry_delta = None
        self.entry_poc = None
        self.entry_time_epoch = None
        self.heat_start_epoch = None
        self.trade_min_price = None
        self.trade_max_price = None
        self._last_exit_fill_price = None


class StateManager:
    """
    Manages mode-scoped state for Panel2.

    Contract:
    - One StateManager instance per Panel2 instance
    - Stores state by (mode, account) key
    - Provides atomic get/set operations
    - Handles persistence save/load
    """

    def __init__(self):
        # State storage: {(mode, account): Panel2State}
        self._states: dict[tuple[str, str], Panel2State] = {}

        # Active scope (current mode/account)
        self._active_mode: str = "SIM"
        self._active_account: str = ""

    def get_state(self, mode: Optional[str] = None, account: Optional[str] = None) -> Panel2State:
        """
        Get state for specified (mode, account) scope.

        If mode/account not specified, returns active scope state.
        Creates new state instance if scope doesn't exist.

        Args:
            mode: Trading mode (SIM/LIVE/DEBUG)
            account: Account identifier

        Returns:
            Panel2State instance for the scope
        """
        if mode is None:
            mode = self._active_mode
        if account is None:
            account = self._active_account

        key = (mode, account)
        if key not in self._states:
            self._states[key] = Panel2State(mode=mode, account=account)
            log.debug(f"[StateManager] Created new state for {key}")

        return self._states[key]

    def set_active_scope(self, mode: str, account: str = "") -> None:
        """
        Switch active scope to new (mode, account).

        Args:
            mode: Trading mode (SIM/LIVE/DEBUG)
            account: Account identifier
        """
        old_scope = (self._active_mode, self._active_account)
        new_scope = (mode, account)

        if old_scope != new_scope:
            log.info(f"[StateManager] Scope switch: {old_scope} -> {new_scope}")
            self._active_mode = mode
            self._active_account = account

    def get_active_scope(self) -> tuple[str, str]:
        """Get current active (mode, account) scope."""
        return (self._active_mode, self._active_account)

    def reset_position(self, mode: Optional[str] = None, account: Optional[str] = None) -> None:
        """
        Reset position to flat for specified scope.

        Args:
            mode: Trading mode (defaults to active)
            account: Account identifier (defaults to active)
        """
        state = self.get_state(mode, account)
        state.reset_position()
        log.info(f"[StateManager] Position reset for {(state.mode, state.account)}")

    def save_state(self, mode: Optional[str] = None, account: Optional[str] = None) -> None:
        """
        Save state to persistent storage.

        Persists:
        - entry_time_epoch
        - heat_start_epoch
        - trade_min_price
        - trade_max_price

        Args:
            mode: Trading mode (defaults to active)
            account: Account identifier (defaults to active)
        """
        state = self.get_state(mode, account)

        try:
            from pathlib import Path
            from utils.atomic_persistence import save_json_atomic, get_scoped_path

            path = get_scoped_path("runtime_state_panel2", state.mode, state.account)

            data = {
                "entry_time_epoch": state.entry_time_epoch,
                "heat_start_epoch": state.heat_start_epoch,
                "trade_min_price": state.trade_min_price,
                "trade_max_price": state.trade_max_price,
                "mode": state.mode,
                "account": state.account,
            }

            success = save_json_atomic(data, Path(path))
            if success:
                log.debug(f"[StateManager] Saved state for {(state.mode, state.account)}")
        except Exception as e:
            log.error(f"[StateManager] Save failed: {e}")

    def load_state(self, mode: Optional[str] = None, account: Optional[str] = None) -> None:
        """
        Load state from persistent storage.

        Restores:
        - entry_time_epoch
        - heat_start_epoch
        - trade_min_price
        - trade_max_price

        Args:
            mode: Trading mode (defaults to active)
            account: Account identifier (defaults to active)
        """
        state = self.get_state(mode, account)

        try:
            from utils.atomic_persistence import load_json_atomic, get_scoped_path

            path = get_scoped_path("runtime_state_panel2", state.mode, state.account)
            data = load_json_atomic(str(path))

            if data:
                state.entry_time_epoch = data.get("entry_time_epoch")
                state.heat_start_epoch = data.get("heat_start_epoch")
                state.trade_min_price = data.get("trade_min_price")
                state.trade_max_price = data.get("trade_max_price")
                log.info(f"[StateManager] Restored timers for {(state.mode, state.account)}")
            else:
                log.debug(f"[StateManager] No persisted state for {(state.mode, state.account)}")
        except Exception as e:
            log.warning(f"[StateManager] Load failed: {e}")


def set_trading_mode(panel, mode: str, account: Optional[str] = None) -> None:
    """
    Update trading mode for this panel.

    CRITICAL: This implements the ModeChanged contract:
    1. Save current state to old scope
    2. Switch to new (mode, account) scope
    3. Load state from new scope
    4. Trigger UI refresh

    Args:
        panel: Panel2 instance
        mode: Trading mode ("SIM", "LIVE", "DEBUG")
        account: Account identifier (optional, defaults to empty string)
    """
    mode = mode.upper()
    if mode not in ("DEBUG", "SIM", "LIVE"):
        log.warning(f"[Panel2] Invalid trading mode: {mode}")
        return

    # Use empty string if account not provided
    if account is None:
        account = ""

    # Get state manager from panel
    if not hasattr(panel, '_state_manager'):
        log.error("[Panel2] No state manager found")
        return

    sm: StateManager = panel._state_manager
    old_scope = sm.get_active_scope()
    new_scope = (mode, account)

    # Check if mode/account actually changed
    if old_scope == new_scope:
        log.debug(f"[Panel2] Mode/account unchanged: {mode}, {account}")
        return

    log.info(f"[Panel2] Mode change: {old_scope} -> {new_scope}")

    # 1. Save current state
    sm.save_state()

    # 2. Switch scope
    sm.set_active_scope(mode, account)

    # 3. Load new state
    sm.load_state()

    # 4. Refresh UI
    from panels.panel2 import metrics_updater
    state = sm.get_state()
    metrics_updater.refresh_all_cells(panel, state)
    metrics_updater.update_live_banner(panel, state)

    log.info(f"[Panel2] Switched to {mode}/{account}")
