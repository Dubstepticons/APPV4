"""
DTC Manager Module

Handles DTC client initialization, connection management, and signal routing.
Extracted from core/app_manager.py for modularity.

Functions:
- init_dtc(): Initialize DTC client with circuit breaker protection
- connect_dtc_signals(): Wire DTC signals to UI handlers
- run_diagnostics_and_push(): Startup diagnostics

Signal Handlers:
- _on_dtc_connected(): Connection established
- _on_dtc_disconnected(): Connection lost
- _on_dtc_error(): Error handling
- _on_dtc_message(): Message routing and heartbeat tracking
- _on_connection_healthy(): Circuit breaker closed
- _on_connection_degraded(): Circuit breaker opened
- _on_dtc_stats_updated(): Health stats updated
"""

import os
from config.settings import DTC_HOST, DTC_PORT
from core.dtc_client_protected import ProtectedDTCClient
from core.message_router import MessageRouter
from utils.logger import get_logger

log = get_logger("DTCManager")


def init_dtc(main_window) -> None:
    """
    Initialize DTC client and start connection immediately (guarded).

    Creates MessageRouter, ProtectedDTCClient with circuit breaker,
    and starts TCP connection to DTC server.

    Args:
        main_window: MainWindow instance with panels and state
    """
    try:
        # Prevent duplicate initialization
        if getattr(main_window, "_dtc_started", False):
            if os.getenv("DEBUG_DTC", "0") == "1":
                log.debug("[DTC] Init already started; skipping duplicate init")
            return

        host = DTC_HOST
        port = int(DTC_PORT)

        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug(f"[DTC] Searching for DTC server at {host}:{port}")

        # Create message router to dispatch data to panels and state
        # Note: MessageRouter will auto-subscribe to Blinker signals
        router = MessageRouter(
            state=main_window._state,
            panel_balance=main_window.panel_balance,
            panel_live=main_window.panel_live,
            panel_stats=main_window.panel_stats,
            dtc_client=None,  # Will be set after DTC client is created
            auto_subscribe=True,  # Subscribe to Blinker signals
        )

        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug("[DTC] MessageRouter instantiated and wired to panels/state")

        # Use circuit-breaker protected DTC client for production-grade fault tolerance
        main_window._dtc = ProtectedDTCClient(
            host=host,
            port=port,
            router=router,
            failure_threshold=5,  # Open circuit after 5 consecutive failures
            recovery_timeout=60   # Wait 60s before retry attempt
        )

        # Give router access to DTC client for balance refresh requests
        router._dtc_client = main_window._dtc

        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug("[DTC] Router now has DTC client reference for balance requests")

        # Wire up signal handlers
        connect_dtc_signals(main_window)

        # Request balance after session is ready
        if hasattr(main_window._dtc, "session_ready"):

            def _on_session_ready():
                log.info("[startup] DTC session ready")
                if os.getenv("DEBUG_DTC", "0") == "1":
                    print("DEBUG: Session ready - balance will be requested by data_bridge")

            main_window._dtc.session_ready.connect(_on_session_ready)

            if os.getenv("DEBUG_DTC", "0") == "1":
                log.debug("[Startup] Wired session_ready -> request_account_balance")

        # Initiate TCP connection
        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug("[DTC] Client constructed; initiating TCP connect")

        if hasattr(main_window._dtc, "connect") and callable(main_window._dtc.connect):
            main_window._dtc_started = True
            main_window._dtc.connect()

    except Exception as e:
        log.exception(f"[DTC] Init failed: {e}")


def connect_dtc_signals(main_window) -> None:
    """
    Wire DTC client signals to UI + logs (guarded for presence).

    Connects all DTC signals including:
    - connected/disconnected
    - errorOccurred
    - message/messageReceived
    - Circuit breaker health signals

    Args:
        main_window: MainWindow instance with _dtc client
    """
    try:
        if not getattr(main_window, "_dtc", None):
            return

        c = main_window._dtc

        # Core DTC signals
        if hasattr(c, "connected"):
            c.connected.connect(lambda: _on_dtc_connected(main_window))
        if hasattr(c, "disconnected"):
            c.disconnected.connect(lambda: _on_dtc_disconnected(main_window))
        if hasattr(c, "errorOccurred"):
            c.errorOccurred.connect(lambda msg: _on_dtc_error(main_window, msg))
        if hasattr(c, "message"):
            c.message.connect(lambda msg: _on_dtc_message(main_window, msg))
        if hasattr(c, "messageReceived"):
            c.messageReceived.connect(lambda msg: _on_dtc_message(main_window, msg))

        # Circuit breaker health signals (if using ProtectedDTCClient)
        if hasattr(c, "connection_healthy"):
            c.connection_healthy.connect(lambda: _on_connection_healthy(main_window))
        if hasattr(c, "connection_degraded"):
            c.connection_degraded.connect(lambda reason: _on_connection_degraded(main_window, reason))
        if hasattr(c, "stats_updated"):
            c.stats_updated.connect(lambda stats: _on_dtc_stats_updated(main_window, stats))

    except Exception:
        pass


def run_diagnostics_and_push(main_window) -> None:
    """
    Run optional startup diagnostics (no longer updates connection icon).

    Diagnostics are logged but don't affect connection icon state
    (dual-circle uses timing-based logic).

    Args:
        main_window: MainWindow instance
    """
    try:
        from core.startup_diagnostics import run_diagnostics
        run_diagnostics()  # Still run diagnostics for logging/monitoring
    except Exception:
        pass


# -------------------- Signal Handlers --------------------

def _on_dtc_connected(main_window) -> None:
    """
    Called when DTC connection is established (updates outer ring).

    Args:
        main_window: MainWindow instance
    """
    log.info("[info] DTC connected")
    icon = getattr(main_window.panel_balance, "conn_icon", None)
    if icon and hasattr(icon, "mark_connected"):
        icon.mark_connected()


def _on_dtc_disconnected(main_window) -> None:
    """
    Called when DTC connection is lost (clears all timers).

    Args:
        main_window: MainWindow instance
    """
    log.info("[info] DTC disconnected")
    icon = getattr(main_window.panel_balance, "conn_icon", None)
    if icon and hasattr(icon, "mark_disconnected"):
        icon.mark_disconnected()


def _on_dtc_error(main_window, msg: str) -> None:
    """
    Called on DTC error (no explicit action needed - heartbeat timeout will trigger yellow/red).

    Args:
        main_window: MainWindow instance
        msg: Error message
    """
    log.error(f"[error] DTC error: {msg}")
    # No explicit action needed - the connection dot will automatically
    # transition to yellow/red based on heartbeat timeout


def _on_dtc_message(main_window, msg: dict) -> None:
    """
    Called when any DTC message is received (updates both rings).

    Args:
        main_window: MainWindow instance
        msg: DTC message dictionary
    """
    icon = getattr(main_window.panel_balance, "conn_icon", None)
    if icon:
        # Check if this is a heartbeat message (Type 3)
        if msg.get("Type") == 3 and hasattr(icon, "mark_heartbeat"):
            icon.mark_heartbeat()
        # All messages count as data activity
        if hasattr(icon, "mark_data_activity"):
            icon.mark_data_activity()


def _on_connection_healthy(main_window) -> None:
    """
    Called when circuit breaker closes (connection recovered).

    Args:
        main_window: MainWindow instance
    """
    log.info("[CircuitBreaker] Connection healthy - circuit closed")
    # Could add UI notification here (e.g., status bar message)
    # For now, just log - connection icon already handles visual state


def _on_connection_degraded(main_window, reason: str) -> None:
    """
    Called when circuit breaker opens (connection failing).

    Args:
        main_window: MainWindow instance
        reason: Failure reason
    """
    log.warning(f"[CircuitBreaker] Connection degraded - circuit open: {reason}")
    # Could add UI notification here (e.g., banner warning)
    # Application continues in degraded mode (no DTC data)


def _on_dtc_stats_updated(main_window, stats: dict) -> None:
    """
    Called when DTC health stats are updated - updates connection icon with circuit breaker status.

    Args:
        main_window: MainWindow instance
        stats: Health statistics dictionary
    """
    try:
        icon = getattr(main_window.panel_balance, "conn_icon", None)
        if not icon or not hasattr(icon, "update_circuit_breaker"):
            return

        # Extract circuit breaker stats
        cb_stats = stats.get("circuit_breaker", {})
        state = cb_stats.get("state", "CLOSED").upper()
        failures = cb_stats.get("failure_count", 0)
        threshold = cb_stats.get("failure_threshold", 5)
        recovery_time = cb_stats.get("last_failure_time")  # Epoch timestamp

        # If circuit is OPEN, add recovery timeout to get retry time
        if state == "OPEN":
            recovery_timeout = cb_stats.get("recovery_timeout", 60)
            if recovery_time:
                recovery_time = recovery_time + recovery_timeout
        else:
            recovery_time = None

        # Update connection icon
        icon.update_circuit_breaker(state, failures, threshold, recovery_time)

    except Exception as e:
        log.debug(f"[CircuitBreaker] Failed to update connection icon: {e}")
