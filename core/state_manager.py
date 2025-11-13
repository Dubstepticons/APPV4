from __future__ import annotations

import contextlib
from datetime import datetime

# File: core/state_manager.py
# Block 26/?? -- StateManager with mode awareness (SIM/LIVE)
from typing import Any, Dict, Optional

from PyQt6 import QtCore

# CONSOLIDATION FIX: Import canonical mode detection (single source of truth)
from utils.trade_mode import detect_mode_from_account


class StateManager(QtCore.QObject):
    """
    Unified state manager with mode-aware position tracking and atomic updates.

    This class is the single source of truth for:
    - Trading mode (SIM/LIVE/DEBUG)
    - Position state (symbol, qty, entry price, side)
    - Account balances (mode-specific: sim_balance, live_balance)
    - Mode transition history and conflict detection

    KEY ARCHITECTURAL INVARIANTS:
    ==============================
    1. **Single Mode Invariant**: current_mode == position_mode when position is open
       - When flat (no position): position_mode = None
       - When in trade: current_mode and position_mode are ALWAYS synchronized

    2. **DTC as Source of Truth**: Position updates ONLY from DTC messages
       - POSITION_UPDATE messages from Sierra Chart
       - ORDER_UPDATE messages with "FILLED" status
       - GUI actions send orders to DTC, but don't update state directly

    3. **Mode Precedence**: LIVE > SIM > DEBUG
       - LIVE mode can always override (highest priority)
       - SIM mode blocked if LIVE position is open
       - SIM position auto-closes when switching to LIVE

    4. **Atomic State Updates**: All state changes are atomic
       - Use begin_state_update() / end_state_update() pattern
       - Signals are buffered during updates and emitted together
       - Prevents partial state / UI desync issues

    ARCHITECTURAL UPGRADES (v2.0):
    ==============================
    ✅ UPGRADE 1: Unified state machine (current_mode + position_mode synchronized)
    ✅ UPGRADE 2: Authoritative mode switching (request_mode_change)
    ✅ UPGRADE 3: LIVE balance ingestion from DTC (update_live_balance_from_dtc)
    ✅ UPGRADE 4: Event source of truth documentation (DTC messages only)
    ✅ UPGRADE 5: Mode conflict detection (validate_mode_transition, analyze_mode_conflicts)
    ✅ UPGRADE 6: Atomic state updates (begin/end_state_update with signal buffering)
    ✅ UPGRADE 7: DTC reconnect recovery (recover_state_from_dtc)
    ✅ UPGRADE 8: Explicit panel contracts (added positionChanged signal)

    USAGE GUIDELINES:
    =================
    Mode Changes:
        Use: state.request_mode_change("LIVE", account)
        Avoid: state.current_mode = "LIVE" (bypasses validation)

    Position Updates:
        Only from message_router after receiving DTC messages
        Use: state.open_position(symbol, qty, price, time, mode)
        Use: state.close_position()

    Balance Updates:
        SIM: Automatically calculated from trade P&L
        LIVE: state.update_live_balance_from_dtc(balance, account)

    Atomic Operations:
        state.begin_state_update()
        try:
            # ... multiple state changes ...
        finally:
            state.end_state_update()  # Emits all signals at once

    SIGNALS:
    ========
    - balanceChanged(float): Emitted when balance updates
    - modeChanged(str): Emitted when trading mode changes
    - positionChanged(dict): Emitted when position opens/closes/updates
    """

    # ===== SIGNALS =====
    balanceChanged = QtCore.pyqtSignal(float)  # Emitted when balance updates
    modeChanged = QtCore.pyqtSignal(str)  # Emitted when mode changes (SIM->LIVE or vice versa)
    positionChanged = QtCore.pyqtSignal(dict)  # Emitted when position opens/closes/updates

    def __init__(self):
        super().__init__()

        # Core dynamic store
        self._state: dict[str, Any] = {}

        # -------------------- mode awareness (start)
        self.current_account: Optional[str] = None
        self.current_mode: str = "SIM"  # "SIM", "LIVE", or "DEBUG"

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

        # ===== ATOMIC STATE UPDATES =====
        self._state_update_depth: int = 0  # Track nested state updates
        self._pending_signals: list[tuple[str, Any]] = []  # Buffer signals during atomic updates

    # ===== ATOMIC STATE UPDATE CONTEXT MANAGER =====
    def begin_state_update(self):
        """Begin atomic state update - buffer signals until end_state_update()"""
        self._state_update_depth += 1

    def end_state_update(self):
        """End atomic state update - emit all buffered signals"""
        self._state_update_depth -= 1
        if self._state_update_depth == 0:
            # Emit all buffered signals
            for signal_name, value in self._pending_signals:
                if signal_name == "balance":
                    self.balanceChanged.emit(value)
                elif signal_name == "mode":
                    self.modeChanged.emit(value)
                elif signal_name == "position":
                    self.positionChanged.emit(value)
            self._pending_signals.clear()

    def _emit_signal(self, signal_name: str, value: Any):
        """
        Internal signal emission helper - buffers during atomic updates.

        Args:
            signal_name: "balance", "mode", or "position"
            value: Signal payload
        """
        if self._state_update_depth > 0:
            # Buffer signal for later
            self._pending_signals.append((signal_name, value))
        else:
            # Emit immediately
            if signal_name == "balance":
                self.balanceChanged.emit(value)
            elif signal_name == "mode":
                self.modeChanged.emit(value)
            elif signal_name == "position":
                self.positionChanged.emit(value)

    def load_sim_balance_from_trades(self) -> float:
        """
        Load the SIM balance from the database by summing all realized P&L trades.
        This is called on app startup to restore the balance if the app was restarted.
        """
        try:
            from data.db_engine import get_session
            from data.schema import TradeRecord
            from sqlalchemy import func

            print(f"[DEBUG state_manager.load_sim_balance_from_trades] Loading SIM balance from database...")

            with get_session() as session:
                # Query all closed trades in SIM mode and sum their realized P&L
                result = session.query(func.sum(TradeRecord.realized_pnl)).filter(
                    TradeRecord.mode == "SIM",
                    TradeRecord.realized_pnl != None,
                    TradeRecord.is_closed == True
                ).scalar()

                # Also count how many trades we have
                trade_count = session.query(TradeRecord).filter(
                    TradeRecord.mode == "SIM",
                    TradeRecord.is_closed == True
                ).count()

                total_pnl = float(result) if result else 0.0
                self.sim_balance = 10000.0 + total_pnl

                print(f"\n[DATABASE LOAD] SIM Balance Restored from Trades")
                print(f"  Trades in Database: {trade_count}")
                print(f"  Base Balance: $10,000.00")
                print(f"  Total P&L: {total_pnl:+,.2f}")
                print(f"  Current Balance: ${self.sim_balance:,.2f}\n")
                print(f"[DEBUG state_manager.load_sim_balance_from_trades] Total PnL from trades: {total_pnl:+,.2f}, SIM balance: ${self.sim_balance:,.2f}")

                return self.sim_balance
        except Exception as e:
            print(f"[DEBUG state_manager.load_sim_balance_from_trades] Error loading balance: {e}")
            # Fall back to default 10k
            self.sim_balance = 10000.0
            return self.sim_balance

    # ---- Core API ----
    def set(self, key: str, value: Any) -> None:
        """Assign a value to the state."""
        self._state[key] = value

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Retrieve a value or default."""
        return self._state.get(key, default)

    def delete(self, key: str) -> None:
        """Remove a key from the state."""
        if key in self._state:
            del self._state[key]

    def clear(self) -> None:
        """Clear all runtime state."""
        self._state.clear()

    # ---- Utility methods ----
    def dump(self) -> dict[str, Any]:
        """Return a shallow copy of state for debugging."""
        return dict(self._state)

    def keys(self):
        return list(self._state.keys())

    def update(self, mapping: dict[str, Any]) -> None:
        """Bulk update state."""
        self._state.update(mapping)

    # ---- Convenience accessors ----
    def get_active_symbol(self) -> Optional[str]:
        return self._state.get("active_symbol")

    def get_last_price(self) -> Optional[float]:
        return self._state.get("last_price")

    def get_positions(self) -> list[dict]:
        return self._state.get("positions", [])

    def set_positions(self, positions: list[dict]) -> None:
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

        DEPRECATED: Use request_mode_change() for new code.
        """
        old_mode = self.current_mode
        self.current_account = account

        # CONSOLIDATION FIX: Use canonical mode detection (no inline import needed)
        new_mode = detect_mode_from_account(account or "")

        if new_mode != old_mode:
            self.current_mode = new_mode
            self._add_to_mode_history(new_mode, account or "")
            self._log_mode_change("StateManager.set_mode", new_mode)

            # Emit modeChanged signal (uses buffering)
            self._emit_signal("mode", new_mode)

    # -------------------- mode setter (end)

    # -------------------- mode history tracking (start)
    def _add_to_mode_history(self, mode: str, account: str) -> None:
        """
        Add a mode change to history.

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

    def get_mode_history(self, limit: Optional[int] = None) -> list[tuple[datetime, str, str]]:
        """
        Get mode change history.

        Args:
            limit: Optional limit on number of entries (most recent)

        Returns:
            List of (timestamp_utc, mode, account) tuples
        """
        if limit:
            return self.mode_history[-limit:]
        return list(self.mode_history)

    def get_last_mode_change(self) -> Optional[tuple[datetime, str, str]]:
        """
        Get the most recent mode change.

        Returns:
            Tuple of (timestamp_utc, mode, account) or None if no history
        """
        if self.mode_history:
            return self.mode_history[-1]
        return None

    def clear_mode_history(self) -> None:
        """Clear mode history (useful for testing)."""
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

    # ===== UNIFIED MODE MANAGEMENT (UPGRADE 1 & 2) =====
    def validate_mode_transition(self, old_mode: str, new_mode: str) -> tuple[bool, Optional[str]]:
        """
        Validate if a mode transition is allowed.

        Rules:
        1. LIVE mode can always override (highest precedence)
        2. SIM mode blocked if LIVE position is open
        3. Mode switches within same mode are no-ops
        4. Must close SIM position before switching to LIVE

        Args:
            old_mode: Current mode
            new_mode: Requested mode

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if transition is valid
            - (False, reason) if transition is blocked
        """
        # No change = always valid
        if new_mode == old_mode:
            return (True, None)

        # LIVE always wins (highest precedence)
        if new_mode == "LIVE":
            # Check if we have open SIM position that needs to be closed
            if self.has_active_position() and self.position_mode == "SIM":
                return (True, None)  # Will auto-close SIM position
            return (True, None)

        # Switching to SIM
        if new_mode == "SIM":
            # Block if LIVE position is open
            if self.has_active_position() and self.position_mode == "LIVE":
                return (False, "Cannot switch to SIM: LIVE position is open")
            return (True, None)

        # DEBUG mode transitions
        if new_mode == "DEBUG":
            return (True, None)  # DEBUG can always be entered

        return (False, f"Invalid mode transition: {old_mode} -> {new_mode}")

    def request_mode_change(self, new_mode: str, account: Optional[str] = None) -> bool:
        """
        Authoritative entry point for ALL mode changes.
        Validates transition, handles position cleanup, updates state atomically.

        This replaces all ad-hoc mode switching logic throughout the codebase.

        Args:
            new_mode: Requested mode ("SIM", "LIVE", "DEBUG")
            account: Optional account identifier

        Returns:
            True if mode change succeeded, False if blocked
        """
        old_mode = self.current_mode

        # Validate transition
        is_valid, error = self.validate_mode_transition(old_mode, new_mode)
        if not is_valid:
            try:
                from utils.logger import get_logger
                log = get_logger("StateManager")
                log.warning(f"[Mode Change Blocked] {error}")
            except Exception:
                pass
            return False

        # No-op if same mode
        if new_mode == old_mode:
            return True

        # Begin atomic state update
        self.begin_state_update()

        try:
            # Handle position cleanup for mode transitions
            if new_mode == "LIVE" and self.position_mode == "SIM":
                # Close SIM position when switching to LIVE
                closed_trade = self.close_position()
                if closed_trade:
                    try:
                        from utils.logger import get_logger
                        log = get_logger("StateManager")
                        log.info(f"[Mode Switch] Auto-closed SIM position: {closed_trade['symbol']}")
                    except Exception:
                        pass

            # Update mode state
            self.current_mode = new_mode
            self.current_account = account

            # Add to mode history
            self._add_to_mode_history(new_mode, account or "")

            # Log mode change
            self._log_mode_change("StateManager.request_mode_change", new_mode)

            # Emit mode changed signal (buffered)
            self._emit_signal("mode", new_mode)

            return True

        finally:
            # End atomic update (emits all buffered signals)
            self.end_state_update()

    def analyze_mode_conflicts(self, lookback_minutes: int = 5) -> list[dict]:
        """
        Analyze mode history for conflicts and rapid switching.

        Args:
            lookback_minutes: How far back to analyze (default 5 min)

        Returns:
            List of detected conflicts with details
        """
        from datetime import timezone, timedelta

        conflicts = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=lookback_minutes)

        recent_changes = [
            (ts, mode, acct)
            for ts, mode, acct in self.mode_history
            if ts >= cutoff
        ]

        # Detect rapid mode switching (>3 changes in lookback window)
        if len(recent_changes) > 3:
            conflicts.append({
                "type": "rapid_switching",
                "count": len(recent_changes),
                "window_minutes": lookback_minutes,
                "changes": recent_changes
            })

        # Detect SIM->LIVE->SIM patterns (indicates mode thrashing)
        for i in range(len(recent_changes) - 2):
            ts1, mode1, _ = recent_changes[i]
            ts2, mode2, _ = recent_changes[i + 1]
            ts3, mode3, _ = recent_changes[i + 2]

            if mode1 == "SIM" and mode2 == "LIVE" and mode3 == "SIM":
                conflicts.append({
                    "type": "mode_thrashing",
                    "pattern": "SIM->LIVE->SIM",
                    "timestamps": [ts1, ts2, ts3],
                    "duration_seconds": (ts3 - ts1).total_seconds()
                })

        return conflicts

    # -------------------- Trading data persistence (start)
    def update_balance(self, balance: Optional[float]) -> None:
        """Record current account balance."""
        if balance is not None:
            with contextlib.suppress(TypeError, ValueError):
                self._state["balance"] = float(balance)  # Ignore invalid balance values

    def update_position(self, symbol: Optional[str], qty: int, avg_price: Optional[float]) -> None:
        """Record or remove a position."""
        if not symbol:
            return
        positions = self._state.get("positions", {})
        if qty == 0:
            # Close position (remove from dict)
            positions.pop(symbol, None)
        else:
            # Update or create position
            positions[symbol] = {
                "qty": int(qty),
                "avg_price": float(avg_price) if avg_price else None,
            }
        self._state["positions"] = positions

    def record_order(self, payload: dict) -> None:
        """Record an order event for statistics and replay."""
        if not isinstance(payload, dict):
            return
        orders = self._state.get("orders", [])
        orders.append(payload)
        self._state["orders"] = orders

    # -------------------- Trading data persistence (end)

    # ===== MODE MANAGEMENT =====
    @property
    def active_balance(self) -> float:
        """Return balance for the currently OPEN trade (not current_mode)"""
        if self.position_mode == "SIM":
            return self.sim_balance
        elif self.position_mode == "LIVE":
            return self.live_balance
        else:
            return self.get_balance_for_mode(self.current_mode)

    def get_balance_for_mode(self, mode: str) -> float:
        """Get balance for a specific mode"""
        return self.sim_balance if mode == "SIM" else self.live_balance

    def set_balance_for_mode(self, mode: str, balance: float) -> None:
        """Update balance for a specific mode"""
        print(f"[DEBUG state_manager.set_balance_for_mode] STEP 1: Called with mode={mode}, balance={balance}")
        if mode == "SIM":
            old_balance = self.sim_balance
            self.sim_balance = balance
            print(f"[DEBUG state_manager.set_balance_for_mode] STEP 2: SIM balance updated from {old_balance} to {balance}")
        else:
            old_balance = self.live_balance
            self.live_balance = balance
            print(f"[DEBUG state_manager.set_balance_for_mode] STEP 2: LIVE balance updated from {old_balance} to {balance}")

        # Emit signal so UI can update (uses atomic signal buffering)
        print(f"[DEBUG state_manager.set_balance_for_mode] STEP 3: Emitting balanceChanged signal with balance={balance}")
        self._emit_signal("balance", balance)
        print(f"[DEBUG state_manager.set_balance_for_mode] STEP 4: Signal emitted successfully")

    def update_live_balance_from_dtc(self, balance: float, account: str) -> bool:
        """
        UPGRADE 3: Update LIVE balance from DTC account balance messages.

        This is the authoritative entry point for LIVE balance updates.
        Should be called from message_router when ACCOUNT_BALANCE messages arrive.

        Args:
            balance: New balance from DTC
            account: Account identifier from DTC

        Returns:
            True if balance was updated, False if ignored (wrong mode)
        """
        try:
            # Only update if this is actually LIVE mode
            detected_mode = detect_mode_from_account(account)
            if detected_mode != "LIVE":
                return False

            # Update LIVE balance
            old_balance = self.live_balance
            self.live_balance = float(balance)

            # Log balance update
            try:
                from utils.logger import get_logger
                log = get_logger("StateManager")
                log.info(f"[LIVE Balance] Updated from DTC: ${old_balance:,.2f} -> ${self.live_balance:,.2f}")
            except Exception:
                pass

            # Emit signal if LIVE mode is active
            if self.current_mode == "LIVE":
                self._emit_signal("balance", self.live_balance)

            return True

        except (TypeError, ValueError) as e:
            try:
                from utils.logger import get_logger
                log = get_logger("StateManager")
                log.error(f"[LIVE Balance] Error updating from DTC: {e}")
            except Exception:
                pass
            return False

    def reset_sim_balance_to_10k(self) -> float:
        """Reset SIM balance to $10,000 (for monthly reset or manual hotkey)"""
        self.sim_balance = 10000.0
        self.sim_balance_start_of_month = 10000.0
        return self.sim_balance

    def adjust_sim_balance_by_pnl(self, realized_pnl: float) -> float:
        """
        Adjust SIM balance by realized P&L from a closed trade.

        Args:
            realized_pnl: The P&L from the closed trade (positive or negative)

        Returns:
            The new SIM balance after adjustment
        """
        try:
            realized_pnl_float = float(realized_pnl)
            self.sim_balance += realized_pnl_float

            from utils.logger import get_logger
            log = get_logger("StateManager")
            log.info(f"[SIM Balance] Adjusted by {realized_pnl_float:+,.2f} - New balance: ${self.sim_balance:,.2f}")

            return self.sim_balance
        except (TypeError, ValueError) as e:
            from utils.logger import get_logger
            log = get_logger("StateManager")
            log.error(f"[SIM Balance] Error adjusting balance: {e}")
            return self.sim_balance

    # ===== MODE DETECTION =====
    def detect_and_set_mode(self, account: str) -> str:
        """
        Detect trading mode from account string and update state.

        CONSOLIDATION FIX: Uses canonical detect_mode_from_account() from utils.trade_mode
        (single source of truth - no duplicate logic).

        DEPRECATED: Use request_mode_change() for new code.

        Args:
            account: Account identifier from DTC

        Returns:
            Detected mode: "SIM", "LIVE", or "DEBUG"
        """
        # CONSOLIDATION FIX: Use canonical mode detection (single source of truth)
        mode = detect_mode_from_account(account or "")

        # Only add to history if mode actually changed
        if mode != self.current_mode:
            self._add_to_mode_history(mode, account)
            self._log_mode_change("StateManager.detect_and_set_mode", mode)

            # Emit modeChanged signal so UI (Panel 3) can update (uses buffering)
            self._emit_signal("mode", mode)

        self.current_mode = mode
        self.current_account = account
        return mode

    # ===== POSITION TRACKING =====
    # EVENT SOURCE OF TRUTH (UPGRADE 4):
    # ===================================
    # Position tracking is ONLY updated from DTC protocol messages:
    # 1. POSITION_UPDATE messages (symbol, qty, avg_entry) from Sierra Chart
    # 2. ORDER_UPDATE messages with "FILLED" status (inferred position changes)
    #
    # GUI actions (button clicks, manual entries) do NOT directly update positions.
    # They send orders to DTC, and positions are updated when DTC confirms fills.
    #
    # This ensures StateManager always reflects the broker's truth, not client assumptions.

    def has_active_position(self) -> bool:
        """Check if ANY position is currently open"""
        return self.position_qty != 0

    def get_open_trade_mode(self) -> Optional[str]:
        """Returns what mode the current open trade is in (SIM, LIVE, or None)"""
        return self.position_mode if self.has_active_position() else None

    def is_mode_blocked(self, requested_mode: str) -> bool:
        """
        Check if switching to requested_mode is blocked due to open trade.

        Rules:
        1. LIVE mode cannot be blocked (always allowed)
        2. SIM mode blocked if LIVE position is open
        3. SIM mode allowed if SIM position is open (same mode)
        """
        if requested_mode == "LIVE":
            return False  # LIVE always takes precedence

        if requested_mode == "SIM":
            return self.position_mode == "LIVE"  # Blocked only if LIVE position open

        return False

    def open_position(self, symbol: str, qty: float, entry_price: float,
                      entry_time: datetime, mode: str) -> None:
        """
        Open a new position in the specified mode.

        ENFORCES INVARIANT: current_mode == position_mode when position is open
        """
        # Begin atomic state update
        self.begin_state_update()

        try:
            # CRITICAL: Synchronize current_mode with position_mode (single invariant)
            self.current_mode = mode
            self.position_mode = mode

            # Update position state
            self.position_symbol = symbol
            self.position_qty = qty
            self.position_entry_price = entry_price
            self.position_entry_time = entry_time
            self.position_side = "LONG" if qty > 0 else "SHORT"

            # Emit positionChanged signal
            position_data = {
                "action": "open",
                "symbol": symbol,
                "qty": qty,
                "entry_price": entry_price,
                "side": self.position_side,
                "mode": mode
            }
            self._emit_signal("position", position_data)

        finally:
            # End atomic update
            self.end_state_update()

    def close_position(self) -> Optional[dict]:
        """
        Close the current position and return the complete trade record.
        Called when position reaches qty = 0.

        ENFORCES INVARIANT: position_mode = None when flat (no position)
        """
        if not self.has_active_position():
            return None

        # Begin atomic state update
        self.begin_state_update()

        try:
            # Capture trade record before clearing
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

            # Clear position state
            self.position_symbol = None
            self.position_qty = 0
            self.position_entry_price = 0
            self.position_entry_time = None
            self.position_side = None
            self.position_mode = None  # <-- INVARIANT: None when flat

            # Clear snapshots
            self.entry_vwap = None
            self.entry_cum_delta = None
            self.entry_poc = None

            # Emit positionChanged signal
            position_data = {
                "action": "close",
                "trade_record": trade_record
            }
            self._emit_signal("position", position_data)

            return trade_record

        finally:
            # End atomic update
            self.end_state_update()

    def handle_mode_switch(self, new_mode: str) -> Optional[dict]:
        """
        Handle switching to a new mode.

        DEPRECATED: Use request_mode_change() for new code.
        This method is kept for backward compatibility only.

        Rules:
        1. If switching to LIVE and SIM position is open -> close SIM position
        2. If switching to SIM and LIVE position is open -> DENY (block switch)
        3. If switching within same mode -> no-op

        Returns: Closed trade record (if any), or None
        """
        if new_mode == self.current_mode:
            return None  # No change

        if new_mode == "LIVE":
            # Switching to LIVE
            if self.position_mode == "SIM":
                # Close SIM position immediately
                closed_trade = self.close_position()
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

    # ===== DTC RECONNECT RECOVERY (UPGRADE 7) =====
    def recover_state_from_dtc(
        self,
        open_positions: list[dict],
        account_balance: Optional[float] = None,
        account: Optional[str] = None
    ) -> dict:
        """
        Recover state from DTC after reconnection or restart.

        Called by message_router when DTC connection is (re)established.
        Synchronizes StateManager with broker's current state.

        Args:
            open_positions: List of position dicts from DTC
                            [{"symbol": str, "qty": int, "avg_entry": float, "account": str}, ...]
            account_balance: Current account balance from DTC (optional)
            account: Account identifier from DTC (optional)

        Returns:
            Recovery report dict with counts and actions taken
        """
        recovery_report = {
            "positions_recovered": 0,
            "balance_updated": False,
            "mode_detected": None,
            "conflicts_found": []
        }

        # Begin atomic state update
        self.begin_state_update()

        try:
            # 1. Detect mode from account if provided
            if account:
                detected_mode = detect_mode_from_account(account)
                recovery_report["mode_detected"] = detected_mode

                # Update mode if it changed
                if detected_mode != self.current_mode:
                    self.request_mode_change(detected_mode, account)

            # 2. Recover positions
            if open_positions:
                # Check if we already have a position recorded
                if self.has_active_position():
                    # Conflict: we think we have a position, but DTC says something else
                    recovery_report["conflicts_found"].append({
                        "type": "position_mismatch",
                        "local": {
                            "symbol": self.position_symbol,
                            "qty": self.position_qty
                        },
                        "dtc": open_positions
                    })

                # Take DTC as source of truth
                for pos in open_positions:
                    symbol = pos.get("symbol")
                    qty = pos.get("qty", 0)
                    avg_entry = pos.get("avg_entry", 0.0)
                    pos_account = pos.get("account", account)

                    if qty != 0 and symbol:
                        # Detect mode from position's account
                        pos_mode = detect_mode_from_account(pos_account or "")

                        # Open position (will enforce mode invariant)
                        self.open_position(
                            symbol=symbol,
                            qty=float(qty),
                            entry_price=float(avg_entry),
                            entry_time=datetime.now(),
                            mode=pos_mode
                        )
                        recovery_report["positions_recovered"] += 1

            else:
                # No open positions from DTC
                if self.has_active_position():
                    # Conflict: we think we have a position, but DTC says flat
                    recovery_report["conflicts_found"].append({
                        "type": "phantom_position",
                        "local": {
                            "symbol": self.position_symbol,
                            "qty": self.position_qty
                        },
                        "dtc": "no positions"
                    })

                    # Clear phantom position (trust DTC)
                    self.close_position()

            # 3. Update balance if provided
            if account_balance is not None and account:
                detected_mode = detect_mode_from_account(account)
                if detected_mode == "LIVE":
                    self.update_live_balance_from_dtc(account_balance, account)
                    recovery_report["balance_updated"] = True

            # Log recovery
            try:
                from utils.logger import get_logger
                log = get_logger("StateManager")
                log.info(
                    f"[DTC Recovery] Positions: {recovery_report['positions_recovered']}, "
                    f"Conflicts: {len(recovery_report['conflicts_found'])}, "
                    f"Mode: {recovery_report['mode_detected']}"
                )
            except Exception:
                pass

            return recovery_report

        finally:
            # End atomic update (emit all buffered signals)
            self.end_state_update()
