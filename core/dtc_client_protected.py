"""
Circuit-Breaker Protected DTC Client

Wraps DTCClientJSON with circuit breaker pattern for production-grade fault tolerance.
Prevents infinite reconnection attempts and provides graceful degradation.

Features:
- Automatic circuit opening after 5 consecutive connection failures
- 60-second cooldown before retry attempts
- Detailed connection statistics and health monitoring
- Thread-safe state management
- Graceful degradation (app continues working without DTC)

Usage:
    >>> client = ProtectedDTCClient(host="127.0.0.1", port=11099)
    >>> client.connect()  # Protected by circuit breaker
    >>> stats = client.get_health_stats()
"""

from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal
import structlog

from core.data_bridge import DTCClientJSON
from core.circuit_breaker import CircuitBreaker, CircuitBreakerError, get_registry
from utils.logger import get_logger

log = structlog.get_logger(__name__)


class ConnectionError(Exception):
    """Raised when DTC connection fails"""
    pass


class ProtectedDTCClient(QObject):
    """
    DTC client with circuit breaker protection.

    Wraps DTCClientJSON with fault tolerance:
    - Prevents cascade failures from repeated connection attempts
    - Provides graceful degradation when DTC server unavailable
    - Emits detailed health status for UI monitoring

    Signals:
        connection_healthy: Emitted when circuit closes (connection recovered)
        connection_degraded: Emitted when circuit opens (connection failing)
        stats_updated: Emitted periodically with health statistics
    """

    # Health status signals
    connection_healthy = pyqtSignal()
    connection_degraded = pyqtSignal(str)  # reason
    stats_updated = pyqtSignal(dict)

    # Forwarded DTC client signals (for compatibility with existing code)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    errorOccurred = pyqtSignal(str)
    session_ready = pyqtSignal()
    message = pyqtSignal(dict)
    messageReceived = pyqtSignal(dict)

    def __init__(
        self,
        host: str,
        port: int,
        router=None,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        parent: Optional[QObject] = None
    ):
        """
        Initialize protected DTC client.

        Args:
            host: DTC server hostname/IP
            port: DTC server port
            router: MessageRouter instance for dispatching messages (optional)
            failure_threshold: Failures before opening circuit (default: 5)
            recovery_timeout: Seconds before retry (default: 60)
            parent: Qt parent object
        """
        super().__init__(parent)

        self._host = host
        self._port = port
        self._router = router

        # Create underlying DTC client with router
        self._client = DTCClientJSON(host=host, port=port, router=router)

        # Create circuit breaker for connection protection
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=ConnectionError,
            name=f"DTC-{host}:{port}"
        )

        # Register with global registry for monitoring
        get_registry().register(self._circuit_breaker)

        # Wire up client signals with forwarding
        self._client.connected.connect(self._on_client_connected)
        self._client.connected.connect(self.connected)  # Forward signal
        self._client.disconnected.connect(self._on_client_disconnected)
        self._client.disconnected.connect(self.disconnected)  # Forward signal
        self._client.errorOccurred.connect(self._on_client_error)
        self._client.errorOccurred.connect(self.errorOccurred)  # Forward signal
        self._client.session_ready.connect(self._on_session_ready)
        self._client.session_ready.connect(self.session_ready)  # Forward signal

        # Forward message signals if they exist
        if hasattr(self._client, 'message'):
            self._client.message.connect(self.message)
        if hasattr(self._client, 'messageReceived'):
            self._client.messageReceived.connect(self.messageReceived)

        # State tracking
        self._is_connected = False
        self._last_error: Optional[str] = None
        self._connection_attempts = 0

        log.info(
            f"[ProtectedDTC] Initialized with circuit breaker "
            f"(threshold={failure_threshold}, timeout={recovery_timeout}s)"
        )

    def connect(self) -> bool:
        """
        Attempt to connect to DTC server.

        Circuit breaker is checked but NOT wrapped around the async call.
        Connection success/failure is tracked via Qt signals.

        Returns:
            True if connection attempt initiated, False if circuit is open
        """
        from core.circuit_breaker import CircuitState

        # Check if circuit breaker is open (too many failures)
        if self._circuit_breaker.state == CircuitState.OPEN:
            if not self._circuit_breaker._should_attempt_reset():
                log.warning(
                    f"[ProtectedDTC] Connection blocked - circuit breaker is OPEN "
                    f"(failures: {self._circuit_breaker.failure_count}/{self._circuit_breaker.failure_threshold})"
                )
                self.connection_degraded.emit("Circuit breaker is OPEN - too many failures")
                return False
            else:
                # Circuit moving to HALF_OPEN - allow single retry attempt
                log.info("[ProtectedDTC] Circuit breaker transitioning to HALF_OPEN - attempting recovery")
                self._circuit_breaker._transition_to_half_open()

        # Initiate connection (async via Qt signals)
        self._connection_attempts += 1
        log.info(
            f"[ProtectedDTC] Initiating connection to {self._host}:{self._port} "
            f"(attempt #{self._connection_attempts}, circuit: {self._circuit_breaker.state.value})"
        )

        try:
            self._client.connect()
            return True
        except Exception as e:
            error_msg = f"Connection initiation failed: {str(e)}"
            self._last_error = error_msg
            log.error(f"[ProtectedDTC] {error_msg}")
            self._on_connection_failed(error_msg)
            return False

    def disconnect(self) -> None:
        """Disconnect from DTC server"""
        log.info("[ProtectedDTC] Disconnecting from DTC server")
        self._client.disconnect()

    def send_order(self, *args, **kwargs) -> bool:
        """
        Send order through DTC client (if connected).

        Returns:
            True if sent, False if not connected
        """
        if not self._is_connected:
            log.warning("[ProtectedDTC] Cannot send order - not connected")
            return False

        try:
            # Forward to underlying client
            # (Assumes DTCClientJSON has send_order method - adapt as needed)
            return self._client.send_order(*args, **kwargs)
        except Exception as e:
            log.error(f"[ProtectedDTC] Order send failed: {e}")
            return False

    # Signal handlers

    def _on_client_connected(self) -> None:
        """Handle successful TCP connection"""
        log.info("[ProtectedDTC] TCP connection established")
        # Don't mark as fully connected yet - wait for session_ready

    def _on_session_ready(self) -> None:
        """Handle DTC session ready (after successful logon)"""
        self._is_connected = True
        self._last_error = None

        log.info("[ProtectedDTC] DTC session ready - connection healthy")

        # Connection successful - notify circuit breaker
        self._on_connection_success()

        # Emit health status
        self.connection_healthy.emit()
        self._emit_stats()

    def _on_client_disconnected(self) -> None:
        """Handle disconnection"""
        was_connected = self._is_connected
        self._is_connected = False

        log.warning("[ProtectedDTC] Disconnected from DTC server")

        if was_connected:
            # Unexpected disconnection - treat as failure
            self._on_connection_failed("Unexpected disconnection")

        self._emit_stats()

    def _on_client_error(self, error_msg: str) -> None:
        """Handle connection error"""
        self._is_connected = False
        self._last_error = error_msg

        log.error(f"[ProtectedDTC] Connection error: {error_msg}")

        # Record failure with circuit breaker
        self._on_connection_failed(error_msg)

        self.connection_degraded.emit(error_msg)
        self._emit_stats()

    def _on_connection_success(self) -> None:
        """Handle successful connection - reset circuit breaker"""
        self._circuit_breaker._on_success()
        log.info(
            f"[ProtectedDTC] Connection success - circuit breaker reset "
            f"(state: {self._circuit_breaker.state.value})"
        )

    def _on_connection_failed(self, reason: str) -> None:
        """Handle connection failure - update circuit breaker"""
        self._circuit_breaker._on_failure()
        log.warning(
            f"[ProtectedDTC] Connection failure: {reason} "
            f"(failures: {self._circuit_breaker.failure_count}/{self._circuit_breaker.failure_threshold}, "
            f"state: {self._circuit_breaker.state.value})"
        )

    # Health monitoring

    def is_connected(self) -> bool:
        """Check if DTC session is active"""
        return self._is_connected

    def is_healthy(self) -> bool:
        """Check if connection is healthy (connected and circuit closed)"""
        return (
            self._is_connected and
            self._circuit_breaker.state.value == "closed"
        )

    def get_health_stats(self) -> dict:
        """
        Get comprehensive health statistics.

        Returns:
            Dictionary with connection and circuit breaker stats
        """
        breaker_stats = self._circuit_breaker.get_stats()

        return {
            "connection": {
                "is_connected": self._is_connected,
                "is_healthy": self.is_healthy(),
                "host": self._host,
                "port": self._port,
                "connection_attempts": self._connection_attempts,
                "last_error": self._last_error,
            },
            "circuit_breaker": breaker_stats,
            "status": self._get_status_string()
        }

    def _get_status_string(self) -> str:
        """Get human-readable status"""
        if self._is_connected:
            return "CONNECTED"
        elif self._circuit_breaker.state.value == "open":
            return "CIRCUIT_OPEN"
        elif self._circuit_breaker.state.value == "half_open":
            return "TESTING_RECOVERY"
        else:
            return "DISCONNECTED"

    def _emit_stats(self) -> None:
        """Emit current health statistics"""
        stats = self.get_health_stats()
        self.stats_updated.emit(stats)

    def reset_circuit_breaker(self) -> None:
        """
        Manually reset circuit breaker (administrative override).

        Use with caution - typically only for testing or manual recovery.
        """
        log.warning("[ProtectedDTC] Circuit breaker manually reset")
        self._circuit_breaker.reset()
        self._emit_stats()

    # Proxy methods for underlying client

    @property
    def client(self) -> DTCClientJSON:
        """Get underlying DTC client (for advanced use)"""
        return self._client

    def __repr__(self) -> str:
        return (
            f"ProtectedDTCClient(host={self._host}, port={self._port}, "
            f"status={self._get_status_string()})"
        )


def create_protected_dtc_client(
    host: str,
    port: int,
    on_connected: Optional[Callable] = None,
    on_degraded: Optional[Callable[[str], None]] = None,
    **kwargs
) -> ProtectedDTCClient:
    """
    Factory function for creating protected DTC client with callbacks.

    Args:
        host: DTC server hostname
        port: DTC server port
        on_connected: Callback when connection healthy
        on_degraded: Callback when connection degraded (receives error message)
        **kwargs: Additional arguments for ProtectedDTCClient

    Returns:
        Configured ProtectedDTCClient instance

    Example:
        >>> def on_healthy():
        ...     print("DTC connection recovered!")
        >>> def on_degraded(reason):
        ...     print(f"DTC failing: {reason}")
        >>> client = create_protected_dtc_client(
        ...     "127.0.0.1", 11099,
        ...     on_connected=on_healthy,
        ...     on_degraded=on_degraded
        ... )
    """
    client = ProtectedDTCClient(host, port, **kwargs)

    if on_connected:
        client.connection_healthy.connect(on_connected)

    if on_degraded:
        client.connection_degraded.connect(on_degraded)

    return client
