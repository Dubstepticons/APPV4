from __future__ import annotations

import contextlib
import threading
from datetime import datetime

# File: core/state_manager.py
# Block 26/?? -- StateManager with mode awareness (SIM/LIVE)
from typing import Any, Dict, Optional

from PyQt6 import QtCore

# CONSOLIDATION FIX: Import canonical mode detection (single source of truth)
from utils.trade_mode import detect_mode_from_account


class StateManager(QtCore.QObject):
    """
    Lightweight app-wide state registry with advanced mode-aware position tracking.

    Maintains transient runtime data for panels, price feed, and
    account metrics. Should not store persistent data.

    Key Invariant: Only ONE active position at a time (SIM OR LIVE, not both)

    Thread Safety: All public methods are thread-safe. Uses reentrant lock (RLock)
    to protect all mutable state. Signals are emitted OUTSIDE of lock scope to
    prevent deadlocks.
    """

    # ===== SIGNALS =====
    balanceChanged = QtCore.pyqtSignal(float)  # Emitted when balance updates
    modeChanged = QtCore.pyqtSignal(str)  # Emitted when mode changes (SIM->LIVE or vice versa)

    def __init__(self):
        super().__init__()

        # Thread safety: Reentrant lock protects all mutable state
        # RLock allows same thread to acquire lock multiple times (needed for nested calls)
        self._lock = threading.RLock()

        # Core dynamic store
        self._state: dict[str, Any] = {}

        # -------------------- mode awareness (start)
        self.current_account: Optional[str] = None
        self.current_mode: str = "SIM"  # "SIM", "LIVE", or "DEBUG" - Default to SIM (safe starting mode)
        # FIX: Initialize to SIM as the default trading mode when the app starts
        # CRITICAL: This must be detected from actual DTC messages, not hardcoded
        # SIM is the safe starting mode to prevent accidental LIVE trades

        # Mode history: list of (timestamp_utc, mode, account) tuples
        self.mode_history: list[tuple[datetime, str, str]] = []
        self._add_to_mode_history(self.current_mode, self.current_account or "")

        self._log_mode_change("INIT", self.current_mode)
        # -------------------- mode awareness (end)

        # ===== MODE-SPECIFIC BALANCE =====
        self.sim_balance: float = 10000.0  # SIM mode starting balance: $10K/month
        self.sim_balance_start_of_month: float = 10000.0  # Track starting balance for reset
        self.live_balance: float = 0.0

        # ===== POSITION TRACKING (MODE-AWARE) =====
        self.position_symbol: Optional[str] = None
        self.position_qty: float = 0  # positive = long, negative = short
        self.position_entry_price: float = 0
        self.position_entry_time: Optional[datetime] = None
        self.position_side: Optional[str] = None  # "LONG" or "SHORT"
        self.position_mode: Optional[str] = None  # "SIM" or "LIVE" - what mode this position is in

        # ===== ENTRY SNAPSHOTS (for closed trade record) =====
        self.entry_vwap: Optional[float] = None
        self.entry_cum_delta: Optional[float] = None
        self.entry_poc: Optional[float] = None
        self.entry_snapshot_time: Optional[datetime] = None

        # Config (injected)
        self.live_account_id: str = "120005"  # Will be set from config

    # ---- Core API (Thread-Safe) ----
    def set(self, key: str, value: Any) -> None:
        """Assign a value to the state. Thread-safe."""
        with self._lock:
            self._state[key] = value

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieve a value or default. Thread-safe."""
        with self._lock:
            return self._state.get(key, default)

    def delete(self, key: str) -> None:
        """Remove a key from the state. Thread-safe."""
        with self._lock:
            if key in self._state:
                del self._state[key]

    def clear(self) -> None:
        """Clear all runtime state. Thread-safe."""
        with self._lock:
            self._state.clear()

    # ---- Utility methods (Thread-Safe) ----
    def dump(self) -> dict[str, Any]:
        """Return a shallow copy of state for debugging. Thread-safe."""
        with self._lock:
            return dict(self._state)

    def keys(self):
        """Return list of keys. Thread-safe."""
        with self._lock:
            return list(self._state.keys())

    def update(self, mapping: dict[str, Any]) -> None:
        """Bulk update state. Thread-safe."""
        with self._lock:
            self._state.update(mapping)

    # ---- Convenience accessors (Thread-Safe) ----
    def get_active_symbol(self) -> Optional[str]:
        """Thread-safe."""
        with self._lock:
            return self._state.get("active_symbol")

    def get_last_price(self) -> Optional[float]:
        """Thread-safe."""
        with self._lock:
            return self._state.get("last_price")

    def get_positions(self) -> list[dict]:
        """Thread-safe. Returns a copy."""
        with self._lock:
            return list(self._state.get("positions", []))

    def set_positions(self, positions: list[dict]) -> None:
        """Thread-safe."""
        with self._lock:
            self._state["positions"] = positions

    # -------------------- mode properties (backward compatibility) ----
    @property
    def is_sim_mode(self) -> bool:
        """
        Backward compatibility property.
        Returns True if current mode is SIM, False otherwise.

        DEPRECATED: Use current_mode == "SIM" instead.
        """
        return self.current_mode == "SIM"

    @is_sim_mode.setter
    def is_sim_mode(self, value: bool) -> None:
        """
        Backward compatibility setter.
        Sets current_mode based on boolean value.

        DEPRECATED: Use set_mode() or current_mode directly instead.
        """
        self.current_mode = "SIM" if value else "LIVE"

    # -------------------- mode setter (start)
    def set_mode(self, account: str | None) -> None:
        """
        Detect and update mode based on account string.
        Uses proper mode detection (LIVE/SIM/DEBUG) from utils.trade_mode (single source of truth).
        Thread-safe.
        """
        # CONSOLIDATION FIX: Use canonical mode detection (no inline import needed)
        new_mode = detect_mode_from_account(account or "")

        with self._lock:
            old_mode = self.current_mode
            mode_changed = (new_mode != old_mode)

            if mode_changed:
                self.current_mode = new_mode
                self.current_account = account
                self._add_to_mode_history_unsafe(new_mode, account or "")
                self._log_mode_change("StateManager.set_mode", new_mode)
            else:
                # Update account even if mode didn't change
                self.current_account = account

        # Emit signal OUTSIDE lock scope to prevent deadlocks
        if mode_changed:
            try:
                self.modeChanged.emit(new_mode)
            except Exception:
                pass  # Signal emission failure shouldn't crash

    # -------------------- mode setter (end)

    # -------------------- mode history tracking (start)
    def _add_to_mode_history_unsafe(self, mode: str, account: str) -> None:
        """
        Add a mode change to history. MUST be called with lock held.
        Internal helper for use within locked sections.

        Args:
            mode: Trading mode ("LIVE", "SIM", "DEBUG")
            account: Account identifier
        """
        from datetime import timezone
        timestamp_utc = datetime.now(timezone.utc)
        self.mode_history.append((timestamp_utc, mode, account))

        # Keep only last 100 mode changes to prevent memory bloat
        if len(self.mode_history) > 100:
            self.mode_history = self.mode_history[-100:]

    def _add_to_mode_history(self, mode: str, account: str) -> None:
        """
        Add a mode change to history. Thread-safe.

        Args:
            mode: Trading mode ("LIVE", "SIM", "DEBUG")
            account: Account identifier
        """
        with self._lock:
            self._add_to_mode_history_unsafe(mode, account)

    def get_mode_history(self, limit: Optional[int] = None) -> list[tuple[datetime, str, str]]:
        """
        Get mode change history. Thread-safe.

        Args:
            limit: Optional limit on number of entries (most recent)

        Returns:
            List of (timestamp_utc, mode, account) tuples
        """
        with self._lock:
            if limit:
                return self.mode_history[-limit:]
            return list(self.mode_history)

    def get_last_mode_change(self) -> Optional[tuple[datetime, str, str]]:
        """
        Get the most recent mode change. Thread-safe.

        Returns:
            Tuple of (timestamp_utc, mode, account) or None if no history
        """
        with self._lock:
            if self.mode_history:
                return self.mode_history[-1]
            return None

    def clear_mode_history(self) -> None:
        """Clear mode history (useful for testing). Thread-safe."""
        with self._lock:
            self.mode_history.clear()

    # -------------------- mode history tracking (end)

    # -------------------- mode logging (start)
    def _log_mode_change(self, src: str, mode: str) -> None:
        """
        Internal helper for logging mode changes.

        Args:
            src: Source of the mode change (e.g., "StateManager.set_mode", "INIT")
            mode: Mode string ("LIVE", "SIM", "DEBUG")
        """
        try:
            from utils.logger import get_logger

            log = get_logger("StateManager")
            log.info(f"[Mode] {src}: Application now in {mode} mode")
        except Exception:
            pass

    # -------------------- mode logging (end)

    # -------------------- Trading data persistence (start)
    # ARCHITECTURE FIX (Step 3): Obsolete generic tracker methods REMOVED
    # These methods were never used in production code (only in tests/diagnostic tools)
    # - update_balance() - superseded by set_balance_for_mode() and balance properties
    # - update_position() - superseded by open_position()/close_position() methods
    # - record_order() - never used in production, only in diagnostic tools
    # If tests need these, they should use the specific domain methods instead

    # -------------------- Trading data persistence (end)

    # ===== MODE MANAGEMENT =====
    @property
    def active_balance(self) -> float:
        """Return balance for the currently OPEN trade (not current_mode). Thread-safe."""
        with self._lock:
            if self.position_mode == "SIM":
                return self.sim_balance
            elif self.position_mode == "LIVE":
                return self.live_balance
            else:
                return self.sim_balance if self.current_mode == "SIM" else self.live_balance

    def get_balance_for_mode(self, mode: str) -> float:
        """Get balance for a specific mode. Thread-safe."""
        with self._lock:
            return self.sim_balance if mode == "SIM" else self.live_balance

    def set_balance_for_mode(self, mode: str, balance: float) -> None:
        """Update balance for a specific mode. Thread-safe."""
        with self._lock:
            if mode == "SIM":
                self.sim_balance = balance
            else:
                self.live_balance = balance

        # Emit signal OUTSIDE lock scope to prevent deadlocks
        self.balanceChanged.emit(balance)

    def reset_sim_balance_to_10k(self) -> float:
        """Reset SIM balance to $10,000 (for monthly reset or manual hotkey). Thread-safe."""
        with self._lock:
            self.sim_balance = 10000.0
            self.sim_balance_start_of_month = 10000.0
            return self.sim_balance

    def adjust_sim_balance_by_pnl(self, realized_pnl: float) -> float:
        """
        Adjust SIM balance by realized P&L from a closed trade.
        Thread-safe - VULN-001 FIX.

        Args:
            realized_pnl: The P&L from the closed trade (positive or negative)

        Returns:
            The new SIM balance after adjustment
        """
        try:
            realized_pnl_float = float(realized_pnl)

            # VULN-001 FIX: Protect read-modify-write operation with lock
            with self._lock:
                self.sim_balance += realized_pnl_float
                new_balance = self.sim_balance

            from utils.logger import get_logger
            log = get_logger("StateManager")
            log.info(f"[SIM Balance] Adjusted by {realized_pnl_float:+,.2f} - New balance: ${new_balance:,.2f}")

            return new_balance
        except (TypeError, ValueError) as e:
            from utils.logger import get_logger
            log = get_logger("StateManager")
            log.error(f"[SIM Balance] Error adjusting balance: {e}")
            with self._lock:
                return self.sim_balance

    # ===== MODE DETECTION =====
    def detect_and_set_mode(self, account: str) -> str:
        """
        Detect trading mode from account string and update state.
        Thread-safe.

        CONSOLIDATION FIX: Uses canonical detect_mode_from_account() from utils.trade_mode
        (single source of truth - no duplicate logic).

        Args:
            account: Account identifier from DTC

        Returns:
            Detected mode: "SIM", "LIVE", or "DEBUG"
        """
        # CONSOLIDATION FIX: Use canonical mode detection (single source of truth)
        mode = detect_mode_from_account(account or "")

        with self._lock:
            mode_changed = (mode != self.current_mode)

            # Only add to history if mode actually changed
            if mode_changed:
                self._add_to_mode_history_unsafe(mode, account)
                self._log_mode_change("StateManager.detect_and_set_mode", mode)

            self.current_mode = mode
            self.current_account = account

        # Emit signal OUTSIDE lock scope to prevent deadlocks
        if mode_changed:
            try:
                self.modeChanged.emit(mode)
            except Exception:
                pass  # Signal emission failure shouldn't crash

        return mode

    # ===== POSITION TRACKING =====
    def has_active_position(self) -> bool:
        """Check if ANY position is currently open. Thread-safe."""
        with self._lock:
            return self.position_qty != 0

    def get_open_trade_mode(self) -> Optional[str]:
        """Returns what mode the current open trade is in (SIM, LIVE, or None). Thread-safe."""
        with self._lock:
            return self.position_mode if self.position_qty != 0 else None

    def is_mode_blocked(self, requested_mode: str) -> bool:
        """
        Check if switching to requested_mode is blocked due to open trade.
        Thread-safe.

        Rules:
        1. LIVE mode cannot be blocked (always allowed)
        2. SIM mode blocked if LIVE position is open
        3. SIM mode allowed if SIM position is open (same mode)
        """
        if requested_mode == "LIVE":
            return False  # LIVE always takes precedence

        if requested_mode == "SIM":
            with self._lock:
                return self.position_mode == "LIVE"  # Blocked only if LIVE position open

        return False

    def open_position(self, symbol: str, qty: float, entry_price: float,
                      entry_time: datetime, mode: str) -> None:
        """Open a new position in the specified mode. Thread-safe."""
        with self._lock:
            self.position_symbol = symbol
            self.position_qty = qty
            self.position_entry_price = entry_price
            self.position_entry_time = entry_time
            self.position_side = "LONG" if qty > 0 else "SHORT"
            self.position_mode = mode  # <-- KEY: Store what mode this position is in

    def close_position(self) -> Optional[dict]:
        """
        Close the current position and return the complete trade record.
        Called when position reaches qty = 0. Thread-safe.
        """
        with self._lock:
            if self.position_qty == 0:
                return None

            trade_record = {
                "symbol": self.position_symbol,
                "side": self.position_side,
                "qty": abs(self.position_qty),
                "entry_time": self.position_entry_time,
                "entry_price": self.position_entry_price,
                "entry_vwap": self.entry_vwap,
                "entry_cum_delta": self.entry_cum_delta,
                "mode": self.position_mode,  # <-- Record what mode this was
            }

            # Clear position
            self.position_symbol = None
            self.position_qty = 0
            self.position_entry_price = 0
            self.position_entry_time = None
            self.position_side = None
            self.position_mode = None

            # Clear snapshots
            self.entry_vwap = None
            self.entry_cum_delta = None
            self.entry_poc = None

            return trade_record

    def handle_mode_switch(self, new_mode: str) -> Optional[dict]:
        """
        Handle switching to a new mode. Thread-safe.

        Rules:
        1. If switching to LIVE and SIM position is open -> close SIM position
        2. If switching to SIM and LIVE position is open -> DENY (block switch)
        3. If switching within same mode -> no-op

        Returns: Closed trade record (if any), or None
        """
        with self._lock:
            if new_mode == self.current_mode:
                return None  # No change

            if new_mode == "LIVE":
                # Switching to LIVE
                if self.position_mode == "SIM":
                    # Close SIM position immediately (need to call unsafe version inside lock)
                    if self.position_qty == 0:
                        closed_trade = None
                    else:
                        closed_trade = {
                            "symbol": self.position_symbol,
                            "side": self.position_side,
                            "qty": abs(self.position_qty),
                            "entry_time": self.position_entry_time,
                            "entry_price": self.position_entry_price,
                            "entry_vwap": self.entry_vwap,
                            "entry_cum_delta": self.entry_cum_delta,
                            "mode": self.position_mode,
                        }
                        # Clear position
                        self.position_symbol = None
                        self.position_qty = 0
                        self.position_entry_price = 0
                        self.position_entry_time = None
                        self.position_side = None
                        self.position_mode = None
                        self.entry_vwap = None
                        self.entry_cum_delta = None
                        self.entry_poc = None

                    self.current_mode = new_mode
                    return closed_trade
                else:
                    # No open position or already LIVE
                    self.current_mode = new_mode
                    return None

            elif new_mode == "SIM":
                # Switching to SIM
                if self.position_mode == "LIVE":
                    # CANNOT switch - block it
                    return None
                else:
                    # No open position or already SIM
                    self.current_mode = new_mode
                    return None

            return None
