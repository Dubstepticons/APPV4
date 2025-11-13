from __future__ import annotations

import contextlib
import time

# File: core/data_bridge.py
# DTC JSON bridge (Qt): null-terminated framing, event normalization,
# heartbeat, watchdog, auto-reconnect, and handshake-ready signaling.
# -------------------- Imports (start)
from typing import Any, Dict, Optional

from blinker import Signal
import orjson
from pydantic import BaseModel, Field
from PyQt6 import QtCore, QtNetwork
import structlog

from services.dtc_constants import (
    ACCOUNT_BALANCE_UPDATE,
    ENCODING_REQUEST,
    ENCODING_RESPONSE,
    HEARTBEAT,
    LOGON_REQUEST,
    LOGON_RESPONSE,
    POSITION_UPDATE,
    type_to_name,
)
from services.dtc_protocol import (
    build_heartbeat,
    build_logon_request,
    frame_message,
    is_logon_success,
    parse_messages,
)


# -------------------- Imports (end)

log = structlog.get_logger(__name__)

# ===== NEW UTILITIES (v2.0 Architecture) =====
from utils.signal_bus import bus, signal_trade_account, signal_balance, signal_position, signal_order
from utils.debug_throttle import DebugThrottle
from utils.position_state import PositionStateMachine
from utils.order_state import OrderStateMachine

# ===== NEW PARSER (Phase 2) =====
from core.dtc_parser import AppMessage, parse_dtc_message

# ===== BACKWARD COMPATIBILITY =====
# Module-level signal aliases for existing code (deprecated)
# TODO: Migrate all imports to use `bus` directly
# signal_trade_account, signal_balance, signal_position, signal_order imported above

# ===== DEPRECATED NORMALIZERS =====
# All normalization logic has been moved to core/dtc_parser.py (Phase 2)
# These are kept for backward compatibility only and will be removed in Phase 3


# -------------------- DTC Client (start)
class DTCClientJSON(QtCore.QObject):
    # Public Qt signals
    connected = QtCore.pyqtSignal()
    disconnected = QtCore.pyqtSignal()
    message = QtCore.pyqtSignal(dict)  # raw DTC dict (added for app_manager fallback)
    messageReceived = QtCore.pyqtSignal(dict)  # same payload for compatibility
    errorOccurred = QtCore.pyqtSignal(str)
    handshake_ready = QtCore.pyqtSignal()  # fires when DTC logon successful (handshake complete)
    seed_ready = QtCore.pyqtSignal()  # fires when initial data queries complete (positions/orders/balance)

    # DEPRECATED: Use handshake_ready instead
    session_ready = QtCore.pyqtSignal()  # fires when fully connected (post-logon)

    # -------------------- __init__ (start)
    def __init__(self, host="127.0.0.1", port=11099, router=None, _sim_mode: bool = False):
        super().__init__()
        self._host, self._port, self._router = host, int(port), router
        self._sock = QtNetwork.QTcpSocket(self)

        # Socket signal wiring
        self._sock.readyRead.connect(self._on_ready_read)
        self._sock.connected.connect(self._on_connected)
        self._sock.disconnected.connect(self._on_disconnected)
        self._sock.errorOccurred.connect(self._on_error)

        # Buffers and timers
        self._buf = bytearray()
        self._heartbeat_timer: Optional[QtCore.QTimer] = None
        self._watchdog_timer: Optional[QtCore.QTimer] = None
        self._reconnect_timer: Optional[QtCore.QTimer] = None
        self._reconnect_attempts: int = 0

        # Handshake helper
        self._handshake_timer: Optional[QtCore.QTimer] = None
        self._init_handshake_detector()

        # Encoding/transport diagnostics
        self._binary_mode_suspected: bool = False
        self._awaiting_encoding_ack: bool = False
        self._encoding_ack_timer: Optional[QtCore.QTimer] = None

        # ===== v2.0 ARCHITECTURE COMPONENTS =====
        # Debug throttle (replaces _debug_dump_next_allowed)
        self._debug_throttle = DebugThrottle()

        # State machines for lifecycle tracking
        self._position_tracker = PositionStateMachine()
        self._order_tracker = OrderStateMachine()

        # Mode-awareness mapping (Phase 2): account -> mode
        # Populated during handshake from TRADE_ACCOUNT responses
        self._mode_map: dict[str, str] = {}  # e.g., {"120005": "LIVE", "Sim1": "SIM"}

        # Initial data seeding tracker (Phase 2)
        self._seed_requests_pending: set[str] = set()  # Track which requests are pending
        self._seed_requests_completed: set[str] = set()  # Track which completed
        self._seed_requests_expected = {
            "trade_accounts",  # Type 400 (TradeAccountsRequest)
            # "positions",  # Type 500 (PositionsRequest) - SKIPPED intentionally
            "open_orders",  # Type 305 (OpenOrdersRequest)
            "fills",  # Type 303 (HistoricalOrderFillRequest)
            "balance",  # Type 601 (AccountBalanceRequest)
        }

        # Router error containment
        self._router_error_count: int = 0
        self._router_error_window_start: float = 0.0  # Monotonic clock
        self._router_error_suppression_active: bool = False

    # -------------------- __init__ (end)

    # -------------------- Debug helpers (start)
    def _allow_debug_dump(self, interval_ms: int = 2000, key: str = "default") -> bool:
        """
        Check if debug output is allowed (rate-limited).

        UPGRADED (v2.0): Uses DebugThrottle utility for cleaner throttling.

        Args:
            interval_ms: Minimum milliseconds between outputs
            key: Throttle key for independent rate limiting

        Returns:
            True if debug output is allowed
        """
        return self._debug_throttle.allow(key, interval_ms)

    # -------------------- Debug helpers (end)

    # -------------------- Lifecycle (start)
    def connect(self) -> None:
        log.info("dtc.tcp.connect", host=self._host, port=self._port)
        self._sock.connectToHost(self._host, self._port)

    def disconnect(self) -> None:
        self._stop_keepalive_system()
        if self._sock.state() != QtNetwork.QAbstractSocket.SocketState.UnconnectedState:
            self._sock.disconnectFromHost()

    # -------------------- Lifecycle (end)

    # -------------------- Qt socket handlers (start)
    def _on_connected(self) -> None:
        log.info("dtc.tcp.connected")
        self._reconnect_attempts = 0
        if self._reconnect_timer and self._reconnect_timer.isActive():
            self._reconnect_timer.stop()
        self.connected.emit()

        # Send DTC LOGON directly (Sierra Chart doesn't support ENCODING_REQUEST negotiation)
        try:
            from config.settings import DTC_PASSWORD, DTC_USERNAME

            logon_msg = build_logon_request(
                protocol_version=8,
                client_name="APPSIERRA",
                heartbeat_interval=10,  # 10-second heartbeat interval
                username=DTC_USERNAME or "",
                password=DTC_PASSWORD or "",
                trade_mode=1,
                OrderUpdatesAsConnectionDefault=1,  # Patch 3: Enable Type 301 (OrderUpdate) stream
            )
            self.send(logon_msg)
            log.info("dtc.logon.request", skip_encoding=True, hint="Sierra Chart doesn't support ENCODING_REQUEST")
        except Exception as e:
            log.error("dtc.handshake.error", err=str(e))

        self._init_keepalive_system()
        # Start handshake grace (in case logon frame is not surfaced)
        if self._handshake_timer:
            self._handshake_timer.start()

    def _on_disconnected(self) -> None:
        log.info("dtc.tcp.disconnected")
        self._stop_keepalive_system()
        self.disconnected.emit()
        # Stop any pending handshake timer
        if self._handshake_timer and self._handshake_timer.isActive():
            self._handshake_timer.stop()
        self._schedule_reconnect()

    def _on_error(self, _socket_error: QtNetwork.QAbstractSocket.SocketError) -> None:
        msg = self._sock.errorString()
        log.error("dtc.tcp.error", msg=msg)
        self.errorOccurred.emit(msg)

    # -------------------- Qt socket handlers (end)

    # -------------------- Handshake readiness (start)
    def _init_handshake_detector(self) -> None:
        """
        UPGRADED (v2.0): Emit handshake_ready when DTC logon succeeds.

        Separates handshake completion from data seeding completion.
        - handshake_ready: DTC logon successful (transport layer ready)
        - seed_ready: Initial data queries completed (application layer ready)

        Preferred: detect DTC LogonResponse(success) on the message stream.
        Fallback: short grace timer after raw TCP connect.
        """
        # Grace timer (optional safety so UI doesn't blink forever if no logon message is exposed)
        self._handshake_timer = QtCore.QTimer(self)
        self._handshake_timer.setSingleShot(True)
        self._handshake_timer.setInterval(1500)  # ms (adjust if your server is slower)
        self._handshake_timer.timeout.connect(self._on_handshake_grace_timeout)

        # Preferred path: detect explicit LogonResponse(success)
        def _check_logon(msg: dict) -> None:
            try:
                t = msg.get("Type") or msg.get("type") or msg.get("MessageType")
                result = msg.get("Result") or msg.get("result") or msg.get("Status")
                is_logon_resp = (t == LOGON_RESPONSE) or (isinstance(t, str) and t.lower() == "logonresponse")
                if not is_logon_resp:
                    return
                ok_tokens = {"LOGON_SUCCESS", "SUCCESS", "OK", "0", "1", 0, 1, True}
                if result in ok_tokens or (isinstance(result, str) and result.upper() in ok_tokens):
                    if self._handshake_timer.isActive():
                        self._handshake_timer.stop()
                    self._on_handshake_complete()
            except Exception:
                # Non-fatal (UI glue)
                pass

        # Wire to our own raw message signal
        with contextlib.suppress(Exception):
            self.message.connect(_check_logon, type=QtCore.Qt.ConnectionType.UniqueConnection)

    def _on_handshake_grace_timeout(self) -> None:
        """Fallback: handshake timeout (no LogonResponse seen)."""
        log.info("dtc.handshake_ready.grace_timeout")
        self._on_handshake_complete()

    def _on_handshake_complete(self) -> None:
        """
        Handshake complete - DTC logon successful.
        Emit handshake_ready signal and kick off initial data requests.
        """
        log.info("dtc.handshake_ready.logon")

        # Emit new signal
        self.handshake_ready.emit()

        # Emit deprecated signal for backward compatibility
        self.session_ready.emit()

        # Kick off initial data seeding
        with contextlib.suppress(Exception):
            self._request_initial_data()

    # -------------------- Handshake readiness (end)

    # -------------------- Heartbeat + Watchdog (start)
    def _init_keepalive_system(self) -> None:
        from datetime import datetime

        self._last_msg_ts = datetime.now()
        self._timeout_sec = 25
        self._heartbeat_interval_ms = 5000
        self._watchdog_interval_ms = 2000

        self._heartbeat_timer = QtCore.QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start(self._heartbeat_interval_ms)

        self._watchdog_timer = QtCore.QTimer(self)
        self._watchdog_timer.timeout.connect(self._check_connection_staleness)
        self._watchdog_timer.start(self._watchdog_interval_ms)

    def _send_heartbeat(self) -> None:
        try:
            if self._sock.state() == QtNetwork.QAbstractSocket.SocketState.ConnectedState:
                hb_msg = build_heartbeat()
                self._sock.write(orjson.dumps(hb_msg) + b"\x00")
                self._sock.flush()
                # Only log heartbeats when DEBUG_DTC=1 to reduce noise
                import os
                if os.getenv("DEBUG_DTC", "0") == "1":
                    log.debug("dtc.heartbeat.sent")
        except Exception as e:
            log.warning("dtc.heartbeat.error", err=str(e))

    def _check_connection_staleness(self) -> None:
        from datetime import datetime, timedelta

        if datetime.now() - self._last_msg_ts > timedelta(seconds=self._timeout_sec):
            log.error("dtc.watchdog.stale_abort")
            self._sock.abort()
            self.disconnected.emit()

    def _update_last_message_time(self) -> None:
        from datetime import datetime

        self._last_msg_ts = datetime.now()

    def _stop_keepalive_system(self) -> None:
        for t in (self._heartbeat_timer, self._watchdog_timer):
            if t and t.isActive():
                t.stop()

    # -------------------- Heartbeat + Watchdog (end)

    # -------------------- Auto-Reconnect (start)
    def _schedule_reconnect(self) -> None:
        base = 2000
        delay = min(base * (2**self._reconnect_attempts), 30000)
        self._reconnect_attempts += 1
        log.warning("dtc.reconnect.scheduled", attempt=self._reconnect_attempts, delay_ms=delay)

        if not self._reconnect_timer:
            self._reconnect_timer = QtCore.QTimer(self)
            self._reconnect_timer.setSingleShot(True)
            self._reconnect_timer.timeout.connect(self.connect)
        else:
            if self._reconnect_timer.isActive():
                self._reconnect_timer.stop()
        self._reconnect_timer.start(int(delay))

    # -------------------- Auto-Reconnect (end)

    # -------------------- Inbound I/O (start)
    def _on_ready_read(self) -> None:
        try:
            while self._sock.bytesAvailable() > 0:
                chunk = self._sock.read(65536)
                if not chunk:
                    break
                self._buf.extend(chunk)
                while True:
                    try:
                        i = self._buf.index(0)
                    except ValueError:
                        break
                    raw = self._buf[:i]
                    del self._buf[: i + 1]
                    if not raw:
                        continue
                    self._update_last_message_time()
                    self._handle_frame(raw)
        except Exception as e:
            log.error("dtc.read.error", err=str(e))

    def _handle_frame(self, raw: bytes) -> None:
        try:
            dtc = orjson.loads(raw)
        except Exception as e:
            log.warning("dtc.json.decode_fail", sample=raw[:160], err=str(e))
            # Heuristic: detect Binary DTC frames (little-endian size + type)
            self._maybe_detect_binary(raw)
            return

        # Defensive: some servers/paths may emit non-dict JSON (e.g., numbers/strings)
        if not isinstance(dtc, dict):
            try:
                preview = str(dtc)
            except Exception:
                preview = "<non-dict>"
            log.warning("dtc.json.non_object", sample=preview[:80])
            return

        # COMPREHENSIVE DEBUG: Log ALL responses with their RequestID to trace misrouted messages
        msg_type = dtc.get("Type")
        req_id = dtc.get("RequestID")
        msg_name = type_to_name(msg_type)

        # Create a REQUEST_ID_MAP to understand which responses belong to which requests
        REQUEST_ID_MAP = {
            1: "Type 400 (TradeAccountsRequest)",
            2: "Type 500 (PositionsRequest) - SKIPPED",
            3: "Type 305 (OpenOrdersRequest)",
            4: "Type 303 (HistoricalOrderFillRequest)",
            5: "Type 601 (AccountBalanceRequest)",
        }

        # Log all responses with RequestID for debugging request/response correlation
        if req_id is not None:
            expected_request = REQUEST_ID_MAP.get(req_id, f"Unknown RequestID {req_id}")
            log.info(
                "dtc.response.routing",
                type=msg_type,
                name=msg_name,
                request_id=req_id,
                expected_request=expected_request,
                symbol=dtc.get("Symbol"),
                qty=dtc.get("Quantity"),
            )

        # NOTE: Type 306 messages from Type 305 OpenOrdersRequest
        # Sierra sends Type 306 (PositionUpdate) in response to Type 305 (OpenOrdersRequest)
        # Process all messages normally - don't reject any

        # Intercept handshake control frames
        t = dtc.get("Type")
        # Note: We skip ENCODING_REQUEST/RESPONSE negotiation since Sierra Chart doesn't support it
        if t == 2:  # LOGON_RESPONSE
            pass  # Continue to normal processing

        # DEBUG: Print all incoming messages (with special highlighting for balance-related)
        msg_type = dtc.get("Type")
        msg_name = type_to_name(msg_type)

        # Comprehensive message type logging for diagnosis
        try:
            from config.settings import DEBUG_DATA, DEBUG_DTC
        except Exception:
            DEBUG_DATA = False
            DEBUG_DTC = False

        # Filter out zero-quantity position updates from debug output
        should_skip_debug = False
        if msg_type == POSITION_UPDATE:
            qty = dtc.get("PositionQuantity", dtc.get("Quantity", dtc.get("qty", 0)))
            avg = dtc.get("AveragePrice", dtc.get("avg_entry"))
            if qty == 0 and (avg is None or avg == 0.0):
                should_skip_debug = True

        # Always log message types if DEBUG_DTC is enabled (for troubleshooting)
        if DEBUG_DTC and msg_type not in (3,) and self._allow_debug_dump(interval_ms=1000) and not should_skip_debug:
            print(f"[DTC-ALL-TYPES] Type: {msg_type} ({msg_name}) Keys: {list(dtc.keys())}")

        # Highlight balance-related messages (gated + throttled)
        if (
            DEBUG_DATA
            and (msg_type == ACCOUNT_BALANCE_UPDATE or "Balance" in msg_name or "AccountBalance" in msg_name)
            and self._allow_debug_dump()
        ):
            print("\n" + "=" * 80)
            print(f"[BALANCE RESPONSE] DTC Message Type: {msg_type} ({msg_name})")
            print(f"   Raw JSON: {dtc}")
            print(f"   Timestamp: {__import__('datetime').datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print("=" * 80 + "\n")
        elif (
            DEBUG_DATA and msg_type not in (3, 501) and self._allow_debug_dump() and not should_skip_debug
        ):  # Skip heartbeats and noisy 501 bursts
            print(f"[DTC] Type: {msg_type} ({msg_name})")

        # Emit raw message for listeners (e.g., handshake detector / app_manager fallback)
        try:
            self.message.emit(dtc)
            self.messageReceived.emit(dtc)
        except Exception:
            pass

        # Normalize & dispatch app-level event (Phase 2: uses extracted parser)
        app_msg = parse_dtc_message(dtc, mode_map=self._mode_map)
        if app_msg:
            self._emit_app(app_msg)

    # -------------------- Inbound I/O (end)

    # -------------------- Initial data seeding (start)
    def _request_initial_data(self) -> None:
        """Request trade accounts, positions, open orders, recent fills, and balance."""

        # Stagger requests slightly to avoid burst disconnects
        def send_trade_accounts():
            self.send({"Type": 400, "RequestID": 1})
            log.info("dtc.request.trade_accounts")

        def send_positions():
            # FIX: Skip querying all positions to avoid pulling phantom/abandoned positions
            # from other account sessions in Sierra Chart's historical data.
            # Positions will come via:
            # 1. Live unsolicited Type 306 PositionUpdate messages from Sierra
            # 2. Initial position responses tied to specific account queries (if we knew the account)
            # Since Sierra doesn't reliably send Type 306 updates, all position data
            # is reconstructed from OrderRecord execution history.
            log.info("dtc.request.positions", status="skipped", reason="Use live updates instead")

        def send_open_orders():
            self.send({"Type": 305, "RequestID": 3})
            log.info("dtc.request.orders")

        def send_fills():
            import time

            days = 30
            now = int(time.time())
            start_ts = now - days * 86400
            self.send({"Type": 303, "RequestID": 4, "StartDateTime": start_ts})
            log.info("dtc.request.fills", days=30)

        def send_balance():
            self.request_account_balance(None)

        QtCore.QTimer.singleShot(0, send_trade_accounts)
        QtCore.QTimer.singleShot(100, send_positions)
        QtCore.QTimer.singleShot(200, send_open_orders)
        QtCore.QTimer.singleShot(300, send_fills)
        QtCore.QTimer.singleShot(400, send_balance)
        log.info("dtc.initial_data.requested")

    # -------------------- Initial data seeding (end)

    def _maybe_detect_binary(self, raw: bytes) -> None:
        """Best-effort detection of Binary DTC frames and log a clear hint once."""
        if self._binary_mode_suspected:
            return
        try:
            if not raw or len(raw) < 4:
                return
            # DTC binary: [uint16 size][uint16 type] little-endian
            size = (raw[1] << 8) | raw[0]
            mtype = (raw[3] << 8) | raw[2]
            if 1 <= mtype <= 900 and 0 < size < 65536:
                self._binary_mode_suspected = True
                log.error(
                    "dtc.encoding.mismatch",
                    hint="Server sending Binary DTC; enable JSON/Compact in Sierra",
                    binary_type=mtype,
                    frame_size=size,
                )
                with contextlib.suppress(Exception):
                    self.errorOccurred.emit(
                        "DTC server appears to be in BINARY mode. Enable JSON/Compact: "
                        "Global Settings > Data/Trade Service Settings > DTC Protocol Server."
                    )
        except Exception:
            # Non-fatal; keep normal flow
            pass

    # -------------------- Dispatch to app (start)
    def _emit_app(self, app_msg: AppMessage) -> None:
        """
        UPGRADED (Phase 2): Dispatch normalized app message with state machine tracking.

        Enhancements:
        - Populates _mode_map from TRADE_ACCOUNT responses
        - Tracks position/order state transitions using state machines
        - Tracks seed request completion
        - Emits seed_ready when all initial data loaded
        - Router error containment with rate limiting
        """
        data = app_msg.model_dump()
        payload = app_msg.payload

        # ===== Phase 2A: Populate mode_map from TRADE_ACCOUNT responses =====
        if app_msg.type == "TRADE_ACCOUNT":
            account = payload.get("account")
            if account:
                # Detect mode from account string
                from utils.trade_mode import detect_mode_from_account

                mode = detect_mode_from_account(account)
                self._mode_map[account] = mode
                log.info(f"dtc.mode_map.updated", account=account, mode=mode)

            # Mark trade_accounts seed request complete
            self._mark_seed_complete("trade_accounts")

        # ===== Phase 2B: Track position state transitions =====
        elif app_msg.type == "POSITION_UPDATE":
            try:
                symbol = payload.get("symbol")
                qty = payload.get("qty", 0)
                avg_entry = payload.get("avg_entry")
                mode = payload.get("mode", "SIM")  # Default to SIM if not in payload
                account = payload.get("TradeAccount")

                if symbol:
                    old_state, new_state = self._position_tracker.update(
                        symbol=symbol, qty=qty, avg_entry=avg_entry, mode=mode, account=account
                    )

                    # Log significant state transitions
                    if old_state != new_state:
                        log.info(
                            "dtc.position.transition",
                            symbol=symbol,
                            old_state=old_state,
                            new_state=new_state,
                            qty=qty,
                            mode=mode,
                        )
            except Exception as e:
                log.warning(f"dtc.position.state_machine.error: {e}")

        # ===== Phase 2C: Track order state transitions =====
        elif app_msg.type == "ORDER_UPDATE":
            try:
                self._order_tracker.update(
                    server_order_id=payload.get("ServerOrderID"),
                    client_order_id=payload.get("ClientOrderID"),
                    symbol=payload.get("Symbol"),
                    side=payload.get("BuySell"),
                    qty=payload.get("Quantity"),
                    filled_qty=payload.get("FilledQuantity"),
                    price=payload.get("Price1"),
                    avg_fill_price=payload.get("AverageFillPrice"),
                    dtc_status=payload.get("OrderStatus"),
                    mode=payload.get("mode", "SIM"),
                    account=payload.get("TradeAccount"),
                    order_type=payload.get("OrderType"),
                    time_in_force=payload.get("TimeInForce"),
                    text=payload.get("Text"),
                )

                # Mark open_orders or fills seed complete based on context
                # (This is approximate - real impl needs RequestID tracking)
                self._mark_seed_complete("open_orders")
                self._mark_seed_complete("fills")

            except Exception as e:
                log.warning(f"dtc.order.state_machine.error: {e}")

        # ===== Phase 2D: Track balance seed completion =====
        elif app_msg.type == "BALANCE_UPDATE":
            self._mark_seed_complete("balance")

        # ===== Emit signals (backward compatibility) =====
        with contextlib.suppress(Exception):
            # (Compatibility) If someone listens to messageReceived for app-envelopes, reuse it.
            self.messageReceived.emit(data)  # harmless if no slots connected

        try:
            try:
                from config.settings import DEBUG_DATA
            except Exception:
                DEBUG_DATA = False

            if app_msg.type == "TRADE_ACCOUNT":
                # Emit to both global and mode-specific signal
                bus.emit_with_mode("trade_account", payload)
            elif app_msg.type == "BALANCE_UPDATE":
                # Emit to both global and mode-specific signal
                bus.emit_with_mode("balance", payload)
            elif app_msg.type == "POSITION_UPDATE":
                if DEBUG_DATA and self._allow_debug_dump(key="position"):
                    print("DEBUG [data_bridge]: [POSITION] Sending POSITION_UPDATE signal")
                # Emit to both global and mode-specific signal
                bus.emit_with_mode("position", payload)
            elif app_msg.type == "ORDER_UPDATE":
                if DEBUG_DATA and self._allow_debug_dump(key="order"):
                    print("DEBUG [data_bridge]: [ORDER] Sending ORDER_UPDATE signal")
                # Emit to both global and mode-specific signal
                bus.emit_with_mode("order", payload)
        except Exception as e:
            log.warning("dtc.signal.error", type=app_msg.type, err=str(e))

        # ===== Phase 2E: Router dispatch with error containment =====
        try:
            if self._router:
                self._router.route(data)
                # Reset error count on successful routing
                self._router_error_count = 0
                self._router_error_suppression_active = False
        except Exception as e:
            self._handle_router_error(app_msg.type, e)

        # Only log dispatch for meaningful updates (filter out zero-quantity positions)
        if app_msg.type == "POSITION_UPDATE":
            qty = payload.get("qty", 0)
            avg = payload.get("avg_entry")
            # Skip logging empty position closures
            if qty == 0 and (avg is None or avg == 0.0):
                return
        log.debug("dtc.dispatch", type=app_msg.type, payload_preview=str(payload)[:200])

    def _mark_seed_complete(self, request_name: str) -> None:
        """
        Mark a seed request as complete and emit seed_ready if all complete.

        Args:
            request_name: Name of seed request (e.g., "trade_accounts", "balance")
        """
        if request_name in self._seed_requests_expected:
            if request_name not in self._seed_requests_completed:
                self._seed_requests_completed.add(request_name)
                log.debug(
                    "dtc.seed.progress", request=request_name, completed=len(self._seed_requests_completed), expected=len(self._seed_requests_expected)
                )

                # Check if all seed requests complete
                if self._seed_requests_completed >= self._seed_requests_expected:
                    log.info("dtc.seed.complete", completed=list(self._seed_requests_completed))
                    self.seed_ready.emit()

                    # Also emit to SignalBus
                    with contextlib.suppress(Exception):
                        bus.seed_ready.send({})

    def _handle_router_error(self, msg_type: str, error: Exception) -> None:
        """
        Handle router errors with rate limiting and suppression.

        Prevents cascade failures from bad router state.

        Args:
            msg_type: Message type that failed
            error: Exception that occurred
        """
        import time

        now = time.monotonic()

        # Reset error window if it's been more than 10 seconds
        if now - self._router_error_window_start > 10.0:
            self._router_error_count = 0
            self._router_error_window_start = now
            self._router_error_suppression_active = False

        self._router_error_count += 1

        # Suppress after 10 errors in 10 seconds
        if self._router_error_count > 10:
            if not self._router_error_suppression_active:
                log.error(
                    "dtc.router.error.suppressed",
                    reason="Too many router errors",
                    error_count=self._router_error_count,
                    window_seconds=10,
                )
                self._router_error_suppression_active = True
        else:
            log.warning("dtc.router.error", type=msg_type, err=str(error), error_count=self._router_error_count)

    # -------------------- Dispatch to app (end)

    # -------------------- Outbound (start)
    def send(self, msg: dict) -> None:
        try:
            data = orjson.dumps(msg) + b"\x00"
            if self._sock.state() == QtNetwork.QAbstractSocket.SocketState.ConnectedState:
                self._sock.write(data)
                self._sock.flush()
            else:
                log.warning("dtc.send.disconnected", dropped=True)
        except Exception as e:
            log.error("dtc.send.error", err=str(e))

    def request_account_balance(self, account: Optional[str] = None) -> None:
        """Request account balance from DTC server (type 601)."""
        from config.settings import DEBUG_DATA, LIVE_ACCOUNT

        acct = account or LIVE_ACCOUNT or ""
        msg = {
            "Type": 601,  # ACCOUNT_BALANCE_REQUEST
            "RequestID": 1,
            "TradeAccount": acct,
        }
        log.info(f"dtc.request.balance.{acct}")
        if DEBUG_DATA and self._allow_debug_dump():
            print("\n" + "=" * 80)
            print("[ACCOUNT BALANCE REQUEST] Sending to DTC server:")
            print(f"   JSON: {msg}")
            print(f"   Account: {acct}")
            print(f"   Timestamp: {__import__('datetime').datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print("=" * 80 + "\n")
        self.send(msg)

    # -------------------- Outbound (end)


# -------------------- DTC Client (end)
# -------------------- END FILE --------------------
