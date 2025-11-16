"""
panels/panel1/equity_state.py

Thread-safe equity curve state management for Panel1.

This module manages equity curves with:
- Scoped curves per (mode, account) tuple
- Thread-safe access with QMutex
- Async loading with QtConcurrent
- In-memory caching
- Signal emissions on load complete

Architecture:
- Thread-safe (QMutex protection for all state access)
- Async loading (background thread with QtConcurrent)
- Scoped isolation (separate curves per mode/account)
- Signal-driven (emits equityCurveLoaded when ready)

**CRITICAL:** This module must be thread-safe. All access to _equity_curves
must be protected by _equity_mutex to prevent race conditions.

Usage:
    from panels.panel1.equity_state import EquityStateManager

    manager = EquityStateManager()
    manager.equityCurveLoaded.connect(on_curve_loaded)

    # Set active scope
    manager.set_scope("SIM", "Test1")

    # Get equity curve (initiates async load if not cached)
    curve = manager.get_equity_curve("SIM", "Test1")

    # Add balance point (thread-safe)
    manager.add_balance_point(balance=10500.0, timestamp=time.time())
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6 import QtCore

import structlog

from panels.panel1.state_persistence import EquityStatePersistence

log = structlog.get_logger(__name__)

# Check if QtConcurrent is available
try:
    from PyQt6.QtConcurrent import QtConcurrent
    HAS_QTCONCURRENT = True
except ImportError:
    QtConcurrent = None
    HAS_QTCONCURRENT = False


class EquityStateManager(QtCore.QObject):
    """
    Thread-safe equity curve state manager.

    Manages equity curves scoped by (mode, account) with:
    - QMutex protection for thread safety
    - Async database loading with QtConcurrent
    - In-memory caching
    - Signal emissions

    **CRITICAL:** All _equity_curves access must be mutex-protected.
    """

    # Signals
    equityCurveLoaded = QtCore.pyqtSignal(str, str, object)  # mode, account, points

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """
        Initialize equity state manager.

        Args:
            parent: Parent QObject (optional)
        """
        super().__init__(parent)

        # Scoped equity curves: {(mode, account): [(timestamp, balance), ...]}
        self._equity_curves: dict[tuple[str, str], list[tuple[float, float]]] = {}

        # Thread safety: QMutex for equity curve access
        # CRITICAL: Prevents race conditions between UI thread and background loaders
        self._equity_mutex = QtCore.QMutex()

        # Current active scope
        self._current_mode: str = "SIM"
        self._current_account: str = ""

        # Active curve (points to current scope's curve)
        self._active_points: list[tuple[float, float]] = []

        # Track pending async loads (prevent duplicate requests)
        self._pending_loads: set[tuple[str, str]] = set()

        # Future watchers (prevent garbage collection)
        self._future_watchers: list[QtCore.QFutureWatcher] = []

        log.info("[EquityStateManager] Initialized")

    def set_scope(self, mode: str, account: str) -> None:
        """
        Set active (mode, account) scope.

        Updates the active curve to match the new scope.

        Args:
            mode: Trading mode ("SIM", "LIVE", "DEBUG")
            account: Account identifier
        """
        self._current_mode = mode
        self._current_account = account

        scope = (mode, account)

        # Thread-safe update of active points
        self._equity_mutex.lock()
        try:
            if scope in self._equity_curves:
                self._active_points = list(self._equity_curves[scope])
            else:
                self._active_points = []
        finally:
            self._equity_mutex.unlock()

        log.debug(
            "[EquityStateManager] Scope changed",
            mode=mode,
            account=account,
            points=len(self._active_points)
        )

    def get_current_scope(self) -> tuple[str, str]:
        """
        Get current (mode, account) scope.

        Returns:
            Tuple of (mode, account)
        """
        return (self._current_mode, self._current_account)

    def get_equity_curve(
        self,
        mode: str,
        account: str
    ) -> list[tuple[float, float]]:
        """
        Get equity curve for (mode, account) scope.

        If curve is not cached, initiates async load from database.

        **CRITICAL:** Thread-safe access with QMutex.

        Args:
            mode: Trading mode
            account: Account identifier

        Returns:
            List of (timestamp, balance) points (empty if not yet loaded)
        """
        scope = (mode, account)

        # Thread-safe check if curve exists
        self._equity_mutex.lock()
        try:
            if scope in self._equity_curves:
                # Already cached - return copy to prevent external mutation
                return list(self._equity_curves[scope])

            # Check if already loading
            if scope in self._pending_loads:
                # Load in progress - return empty for now
                return []

            # Mark as pending and trigger async load
            self._pending_loads.add(scope)

        finally:
            self._equity_mutex.unlock()

        # Start async database load on background thread
        log.debug("[EquityStateManager] Starting async equity curve load", scope=scope)

        if HAS_QTCONCURRENT:
            # Async loading with QtConcurrent (preferred)
            future = QtConcurrent.run(self._load_equity_curve_from_database, mode, account)

            # Connect callback for when load completes
            watcher = QtCore.QFutureWatcher()
            watcher.setFuture(future)
            watcher.finished.connect(
                lambda: self._on_equity_curve_loaded(mode, account, watcher.result())
            )

            # Store watcher to prevent garbage collection
            self._future_watchers.append(watcher)

        else:
            # Fallback: Synchronous loading (may cause brief UI freeze)
            log.warning("[EquityStateManager] QtConcurrent not available, loading synchronously")
            data = self._load_equity_curve_from_database(mode, account)
            self._on_equity_curve_loaded(mode, account, data)

        return []  # Return empty until load completes

    def get_active_curve(self) -> list[tuple[float, float]]:
        """
        Get active equity curve (current scope).

        Returns:
            List of (timestamp, balance) points
        """
        # Return copy to prevent external mutation
        return list(self._active_points)

    def add_balance_point(
        self,
        balance: float,
        timestamp: Optional[float] = None,
        mode: Optional[str] = None,
        account: Optional[str] = None
    ) -> None:
        """
        Add balance point to equity curve.

        **CRITICAL:** Thread-safe with QMutex protection.

        Args:
            balance: Balance value
            timestamp: Unix timestamp (defaults to current time)
            mode: Trading mode (defaults to current scope)
            account: Account identifier (defaults to current scope)
        """
        try:
            # Use current scope if not specified
            if mode is None:
                mode = self._current_mode
            if account is None:
                account = self._current_account

            # Use current time if not provided
            if timestamp is None:
                timestamp = time.time()

            scope = (mode, account)

            # Thread-safe curve update
            self._equity_mutex.lock()
            try:
                # Get existing curve or create new one
                if scope in self._equity_curves:
                    curve = list(self._equity_curves[scope])
                else:
                    curve = []

                # Append new point
                curve.append((float(timestamp), float(balance)))

                # Update scoped dict
                self._equity_curves[scope] = curve

                # Update active points if this is the current scope
                if scope == (self._current_mode, self._current_account):
                    self._active_points = list(curve)

            finally:
                self._equity_mutex.unlock()

            try:
                EquityStatePersistence(mode, account).append_point(timestamp, balance)
            except Exception as exc:
                log.warning(
                    "[EquityStateManager] Failed to persist equity point",
                    error=str(exc),
                    mode=mode,
                    account=account,
                )

            log.debug(
                "[EquityStateManager] Balance point added",
                mode=mode,
                account=account,
                balance=balance,
                points=len(curve)
            )

        except Exception as e:
            log.error(
                "[EquityStateManager] Error adding balance point",
                error=str(e),
                exc_info=True
            )

    def clear_curve(self, mode: str, account: str) -> None:
        """
        Clear equity curve for scope.

        Args:
            mode: Trading mode
            account: Account identifier
        """
        scope = (mode, account)

        self._equity_mutex.lock()
        try:
            if scope in self._equity_curves:
                del self._equity_curves[scope]

            # Clear active points if this is the current scope
            if scope == (self._current_mode, self._current_account):
                self._active_points = []

        finally:
            self._equity_mutex.unlock()

        log.debug("[EquityStateManager] Curve cleared", scope=scope)

    def _load_equity_curve_from_database(
        self,
        mode: str,
        account: str
    ) -> list[tuple[float, float]]:
        """
        Load equity curve from database (runs on background thread).

        Queries all closed trades for the given (mode, account) scope,
        sorts them by exit time, and builds a cumulative balance curve.

        Args:
            mode: Trading mode
            account: Account identifier

        Returns:
            List of (timestamp, balance) points
        """
        try:
            # Delegate to stats service helper
            from services.stats_service import get_equity_curve_for_scope

            points = get_equity_curve_for_scope(mode, account)

            persisted = EquityStatePersistence(mode, account).load_points()
            if persisted:
                points = self._merge_points(points, persisted)

            log.debug(
                "[EquityStateManager] Loaded equity curve from database",
                mode=mode,
                account=account,
                points=len(points)
            )

            return points

        except Exception as e:
            log.error(
                "[EquityStateManager] Error loading equity curve from database",
                error=str(e),
                mode=mode,
                account=account,
                exc_info=True
            )
            return []

    @staticmethod
    def _merge_points(
        db_points: list[tuple[float, float]],
        persisted_points: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Merge database and persisted equity points without duplicates."""
        combined = list(db_points)
        combined.extend(persisted_points)
        combined.sort(key=lambda p: p[0])

        deduped: list[tuple[float, float]] = []
        last_ts: Optional[float] = None
        for ts, bal in combined:
            if last_ts is not None and abs(ts - last_ts) < 1e-6:
                deduped[-1] = (ts, bal)
            else:
                deduped.append((ts, bal))
                last_ts = ts
        return deduped

    def _on_equity_curve_loaded(
        self,
        mode: str,
        account: str,
        equity_points: list[tuple[float, float]]
    ) -> None:
        """
        Callback when async equity curve load completes.

        **CRITICAL:** Thread-safe cache update and signal emission.

        Args:
            mode: Trading mode
            account: Account identifier
            equity_points: Loaded equity curve points
        """
        scope = (mode, account)

        # Thread-safe cache update
        self._equity_mutex.lock()
        try:
            self._equity_curves[scope] = equity_points
            self._pending_loads.discard(scope)

            # Update active curve if this is the current scope
            if scope == (self._current_mode, self._current_account):
                self._active_points = list(equity_points)

        finally:
            self._equity_mutex.unlock()

        log.info(
            "[EquityStateManager] Equity curve loaded",
            mode=mode,
            account=account,
            points=len(equity_points)
        )

        # Emit signal (after releasing mutex to prevent deadlock)
        self.equityCurveLoaded.emit(mode, account, equity_points)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_default_curve(starting_balance: float = 10000.0) -> list[tuple[float, float]]:
    """
    Create default equity curve with starting balance.

    Args:
        starting_balance: Starting balance (default: $10,000)

    Returns:
        List with single point at current time

    Examples:
        >>> curve = create_default_curve(10000.0)
        >>> len(curve)
        1
        >>> curve[0][1]  # Balance
        10000.0
    """
    return [(time.time(), starting_balance)]
