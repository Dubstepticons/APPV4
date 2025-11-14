"""
core/signal_bus.py

Centralized event bus using Qt signals for application-wide messaging.

Replaces:
- Blinker signals (from data_bridge)
- Direct method calls (from MessageRouter)
- Ad-hoc signal definitions

Benefits:
- Thread-safe (Qt signals automatically marshal across threads)
- Type-safe (typed signal parameters)
- Decoupled (panels don't need references to each other)
- Testable (signals can be mocked with pytest-qt)
- Single source of truth for all application events
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6 import QtCore

import structlog

log = structlog.get_logger(__name__)


class SignalBus(QtCore.QObject):
    """
    Centralized event bus for application-wide messaging.

    All components emit to and connect from this single bus.
    Qt automatically handles thread marshaling to the Qt event loop.
    """

    # ========================================================================
    # ACCOUNT EVENTS
    # ========================================================================

    #: TradeAccount response from DTC (full dict)
    tradeAccountReceived = QtCore.pyqtSignal(dict)

    #: Balance updated (balance, account)
    balanceUpdated = QtCore.pyqtSignal(float, str)

    #: Account switched by user
    accountChanged = QtCore.pyqtSignal(str)

    #: Request balance refresh
    balanceRefreshRequested = QtCore.pyqtSignal()

    # ========================================================================
    # POSITION EVENTS
    # ========================================================================

    #: Position opened - emits Position domain object
    positionOpened = QtCore.pyqtSignal(object)

    #: Position update from DTC (dict with position fields)
    positionUpdated = QtCore.pyqtSignal(dict)

    #: Position closed - emits trade record dict (OUTCOME event from service)
    positionClosed = QtCore.pyqtSignal(dict)

    #: Position extremes updated (for MAE/MFE tracking)
    positionExtremesUpdated = QtCore.pyqtSignal(str, str, float)  # mode, account, price

    # ARCHITECTURE (Step 7): Trade lifecycle intents from UI
    #: User requested to close position (INTENT signal from Panel2)
    tradeCloseRequested = QtCore.pyqtSignal(dict)  # trade dict with exit context

    # ========================================================================
    # ORDER EVENTS
    # ========================================================================

    #: Order fill received from DTC
    orderFillReceived = QtCore.pyqtSignal(dict)

    #: Order status update from DTC
    orderUpdateReceived = QtCore.pyqtSignal(dict)

    #: Order submission requested
    orderSubmitRequested = QtCore.pyqtSignal(dict)  # order params

    # ARCHITECTURE FIX (Step 3): Removed unused signals
    # - orderRejected (never emitted or subscribed)
    # - marketTradeReceived (never emitted or subscribed)
    # - marketBidAskReceived (never emitted or subscribed)
    # - priceUpdated (never emitted or subscribed)

    # ========================================================================
    # SESSION EVENTS
    # ========================================================================

    #: DTC connection established
    dtcConnected = QtCore.pyqtSignal()

    #: DTC connection lost
    dtcDisconnected = QtCore.pyqtSignal()

    #: DTC session ready for requests
    dtcSessionReady = QtCore.pyqtSignal()

    #: Heartbeat received (timestamp)
    dtcHeartbeat = QtCore.pyqtSignal(float)

    # ========================================================================
    # MODE EVENTS (Migrated from StateManager)
    # ========================================================================

    #: Trading mode changed (SIM/LIVE/DEBUG)
    modeChanged = QtCore.pyqtSignal(str)

    #: User requested mode switch
    modeSwitchRequested = QtCore.pyqtSignal(str)

    #: Mode drift detected (expected_mode, actual_mode)
    modeDriftDetected = QtCore.pyqtSignal(str, str)

    # ========================================================================
    # UI EVENTS
    # ========================================================================

    #: UI refresh requested (coalesced updates)
    uiRefreshRequested = QtCore.pyqtSignal()

    #: Status message to display
    statusMessagePosted = QtCore.pyqtSignal(str, int)  # message, timeout_ms

    #: Error message to display
    errorMessagePosted = QtCore.pyqtSignal(str)

    #: Theme change requested (Phase 4 - replace direct calls)
    themeChangeRequested = QtCore.pyqtSignal()

    #: Timeframe change requested (Phase 4 - replace direct calls)
    timeframeChangeRequested = QtCore.pyqtSignal(str)  # timeframe

    # ========================================================================
    # BALANCE & EQUITY EVENTS (Phase 4 - Panel1 display updates)
    # ========================================================================

    #: Request Panel1 to display balance (replaces set_account_balance)
    balanceDisplayRequested = QtCore.pyqtSignal(float, str)  # balance, mode

    #: Request Panel1 to add equity point (replaces update_equity_series_from_balance)
    equityPointRequested = QtCore.pyqtSignal(float, str)  # balance, mode

    # ========================================================================
    # PANEL2 VISUAL INDICATORS (Phase 4 - LIVE mode indicators)
    # ========================================================================

    #: LIVE dot visibility requested
    liveDotVisibilityRequested = QtCore.pyqtSignal(bool)  # visible

    #: LIVE dot pulsing requested
    liveDotPulsingRequested = QtCore.pyqtSignal(bool)  # pulsing

    # ========================================================================
    # PANEL3 ANALYTICS (Phase 4 - optional)
    # ========================================================================

    #: Trade closed event for Panel3 (can use positionClosed or separate signal)
    tradeClosedForAnalytics = QtCore.pyqtSignal(dict)  # trade record

    #: Metrics reload requested
    metricsReloadRequested = QtCore.pyqtSignal(str)  # timeframe

    #: Snapshot analysis requested
    snapshotAnalysisRequested = QtCore.pyqtSignal()

    # ========================================================================
    # CHART EVENTS
    # ========================================================================

    #: Chart click detected (symbol, price)
    chartClicked = QtCore.pyqtSignal(str, float)

    #: VWAP updated on chart
    vwapUpdated = QtCore.pyqtSignal(str, float)  # symbol, vwap

    def __init__(self):
        super().__init__()
        log.info("signal_bus.initialized", msg="SignalBus created")

    def emit_safe(self, signal: QtCore.pyqtSignal, *args, **kwargs):
        """
        Emit a signal with error handling.

        Logs errors but doesn't crash the application if a slot fails.

        Args:
            signal: The Qt signal to emit
            *args: Positional arguments to pass to signal
            **kwargs: Keyword arguments (not supported by Qt signals, logged as warning)
        """
        try:
            if kwargs:
                log.warning(
                    "signal_bus.emit_with_kwargs",
                    msg="Qt signals don't support kwargs, ignoring",
                    signal=signal.signal,
                    kwargs=kwargs,
                )
            signal.emit(*args)
        except Exception as e:
            log.error(
                "signal_bus.emit_failed",
                msg="Signal emission failed",
                signal=signal.signal,
                error=str(e),
                exc_info=True,
            )


# ========================================================================
# SINGLETON ACCESSOR
# ========================================================================

_signal_bus_instance: Optional[SignalBus] = None


def get_signal_bus() -> SignalBus:
    """
    Get the global SignalBus singleton.

    Returns:
        SignalBus: The application-wide event bus

    Example:
        >>> signal_bus = get_signal_bus()
        >>> signal_bus.positionOpened.connect(my_handler)
        >>> signal_bus.positionOpened.emit(position)
    """
    global _signal_bus_instance

    if _signal_bus_instance is None:
        _signal_bus_instance = SignalBus()
        log.info("signal_bus.singleton_created", msg="Global SignalBus created")

    return _signal_bus_instance


def reset_signal_bus() -> None:
    """
    Reset the global SignalBus singleton.

    Useful for testing to ensure clean state between tests.

    Warning:
        This will disconnect all existing connections.
        Only use in test fixtures.
    """
    global _signal_bus_instance

    if _signal_bus_instance is not None:
        # Disconnect all signals
        try:
            _signal_bus_instance.deleteLater()
        except Exception:
            pass

    _signal_bus_instance = None
    log.info("signal_bus.reset", msg="Global SignalBus reset")


# ========================================================================
# MIGRATION HELPERS
# ========================================================================


# ARCHITECTURE FIX (Step 3): wrap_blinker_signal function REMOVED
# Blinker is no longer used in runtime dispatch (see data_bridge.py)
# All event routing now uses SignalBus (Qt signals) only
