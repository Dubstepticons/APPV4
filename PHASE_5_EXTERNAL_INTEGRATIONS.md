# PHASE 5 – EXTERNAL INTEGRATIONS (DTC & OTHERS)

**Strictly Descriptive Documentation: No Design Opinions**

This document describes how APPSIERRA integrates with external systems, primarily Sierra Chart via the DTC (Data and Trading Communications) protocol.

---

## 5.1 DTC / SIERRA CHART INTEGRATION

### 5.1.1 Overview

**Integration name:** Sierra Chart DTC Protocol (JSON mode)

**What it is:**
Sierra Chart is a professional charting and trading platform. It exposes a DTC server that allows external applications to subscribe to market data, submit orders, and receive account updates. APPSIERRA connects to this server to execute trades and track positions.

**Protocol:** DTC v8 (JSON encoding)

**Transport:** TCP socket with JSON-framed messages

---

### 5.1.2 Modules Handling Interaction

| Module | File | Purpose |
|--------|------|---------|
| **DTCClientJSON** | `core/data_bridge.py` | Qt-based TCP socket client, connection management, heartbeat |
| **DTC Protocol** | `services/dtc_protocol.py` | Message framing, parsing, builders |
| **DTC Schemas** | `services/dtc_schemas.py` | Pydantic models for message validation |
| **DTC Constants** | `services/dtc_constants.py` | Message type codes, enums, status codes |
| **MessageRouter** | `core/message_router.py` | Routes DTC messages to panels, mode detection |

---

### 5.1.3 Connection Establishment

**File:** `core/data_bridge.py:185-245`

**Step-by-step connection flow:**

#### Step 1: TCP Connection
**When:** App startup or reconnect after disconnect
**Triggered by:** `DTCClientJSON.connect()` called from `MainWindow.__init__()`

```python
# Connection parameters
host = DTC_HOST  # Default: "127.0.0.1"
port = DTC_PORT  # Default: 11099

# Qt socket connection
socket = QTcpSocket()
socket.connectToHost(host, port)
timeout = 5000ms  # 5 seconds
```

**Success signal:** `socket.connected` emitted, triggers `_on_connected()`
**Failure:** `socket.error` emitted, triggers `_on_error()`, schedules reconnect

---

#### Step 2: Logon Handshake
**When:** Immediately after TCP connection established
**Triggered by:** `_on_connected()` at line 254

**Message sent:**
```json
{
  "Type": 1,
  "ProtocolVersion": 8,
  "Username": "DTC_USERNAME",
  "Password": "DTC_PASSWORD",
  "GeneralTextData": "APPSIERRA",
  "ClientName": "APPSIERRA v1.0",
  "MarketDataTransmissionInterval": 0,
  "HeartbeatIntervalInSeconds": 10,
  "TradeMode": 1,  // 1=LIVE, 2=SIM, 0=DEMO
  "Integer_1": 1
}
```

**Field meanings:**
- `Type: 1` = LOGON_REQUEST
- `ProtocolVersion: 8` = DTC protocol version (fixed)
- `HeartbeatIntervalInSeconds: 10` = How often server should send heartbeats
- `TradeMode`: Requested trading mode (1=LIVE means real money orders)
- `ClientName`: Identifies this application to Sierra Chart logs

**How it's sent:**
Via `send_logon()` function in `services/dtc_protocol.py:111`

---

#### Step 3: Logon Response
**When:** Sierra Chart validates credentials and sends response
**Message type:** Type 2 (LOGON_RESPONSE)

**Response fields checked:**
```json
{
  "Type": 2,
  "ProtocolVersion": 8,
  "Result": 1,  // 1=Success, others=failure
  "ResultText": "Logon successful",
  "ReconnectAddress": "",  // Optional redirect
  "Integer_1": 1,  // Server capabilities
  "ServerName": "Sierra Chart DTC",
  "MarketDepthUpdateIntervalInMilliseconds": 0,
  "OneHistoricalPriceDataRequestPerConnection": 0,
  "UseIntegerPriceOrderMessages": 0,
  "UsesMultiplePositionsPerSymbolAndTradeAccount": 0,
  "MarketDataSupported": 1
}
```

**Validation:** `_check_logon()` at line 375 looks for `Type==2` and `Result==1`

**Grace period:**
If logon response doesn't arrive within 1500ms, `_finalize_logon()` is called anyway to prevent hang. This handles cases where Sierra Chart doesn't send Type 2 but accepts the connection.

**Success signal:** `session_ready` emitted at line 402

---

#### Step 4: Initial Data Requests
**When:** After `session_ready` signal emitted
**Triggered by:** `_request_initial_data()` at line 588

**Requests sent in sequence:**

1. **Trade Accounts Request**
   ```json
   {
     "Type": 400,
     "RequestID": 1
   }
   ```
   **Purpose:** Enumerate all available trading accounts
   **Response:** Type 401 (TRADE_ACCOUNT_RESPONSE) for each account

2. **Open Orders Request**
   ```json
   {
     "Type": 305,
     "RequestID": 3,
     "RequestAllOrders": 1
   }
   ```
   **Purpose:** Get all currently open orders
   **Response:** Type 301 (ORDER_UPDATE) messages for each open order

3. **Historical Fills Request**
   ```json
   {
     "Type": 303,
     "RequestID": 4,
     "ServerOrderID": "",
     "NumberOfDays": 30
   }
   ```
   **Purpose:** Retrieve fills from last 30 days for position reconstruction
   **Response:** Type 304 (HISTORICAL_ORDER_FILL_RESPONSE) messages

4. **Account Balance Request**
   ```json
   {
     "Type": 601,
     "RequestID": 1,
     "TradeAccount": ""
   }
   ```
   **Purpose:** Get current account equity and buying power
   **Response:** Type 600 (ACCOUNT_BALANCE_UPDATE)

**Note:** Position request (Type 500) is SKIPPED. APPSIERRA relies on Type 301 order fills to track positions rather than Type 306 position updates, because Sierra Chart's DTC server doesn't send unsolicited position updates in standard configuration.

---

#### Step 5: Session Active
**When:** After initial data requests sent
**State:** Fully connected, ready for real-time updates

**Active systems:**
- Heartbeat timer: Sends Type 3 every 5 seconds
- Watchdog timer: Checks for stale connection every 2 seconds
- Message receiver: Processes incoming frames continuously

---

### 5.1.4 Message Sending (Outbound)

**File:** `core/data_bridge.py:657-686`

**How messages are sent:**

```python
def send(self, msg: dict) -> None:
    # 1. Check connection
    if not self._socket or self._socket.state() != QTcpSocket.ConnectedState:
        log.warning("Cannot send: socket not connected")
        return

    # 2. Frame message (add null terminator)
    raw = frame_message(msg)  # Converts to JSON + b'\x00'

    # 3. Write to socket
    bytes_written = self._socket.write(raw)

    # 4. Flush immediately
    self._socket.flush()
```

**Framing function** (`services/dtc_protocol.py:17`):
```python
def frame_message(msg: dict) -> bytes:
    return orjson.dumps(msg) + b'\x00'
```

**Why null terminator:**
DTC protocol in JSON mode uses null-terminated messages. Each JSON object must end with byte `0x00`. This allows Sierra Chart to detect message boundaries in the TCP stream.

**Example outbound messages:**

**Submit Market Order:**
```json
{
  "Type": 200,
  "ClientOrderID": "APP_20241113_001",
  "Symbol": "MESZ24",
  "Exchange": "CME",
  "TradeAccount": "Sim1",
  "OrderType": 1,  // Market
  "BuySell": 1,    // Buy
  "Price1": 0.0,   // Not used for market orders
  "Price2": 0.0,
  "Quantity": 5,
  "TimeInForce": 1,  // DAY
  "GoodTillDateTime": 0,
  "IsAutomatedOrder": 1
}
```

**Submit Limit Order:**
```json
{
  "Type": 200,
  "ClientOrderID": "APP_20241113_002",
  "Symbol": "MESZ24",
  "Exchange": "CME",
  "TradeAccount": "Sim1",
  "OrderType": 2,    // Limit
  "BuySell": 2,      // Sell
  "Price1": 6005.50, // Limit price
  "Quantity": 5,
  "TimeInForce": 1
}
```

**Cancel Order:**
```json
{
  "Type": 202,
  "ServerOrderID": "12345",
  "ClientOrderID": "APP_20241113_001"
}
```

**Builder functions in** `services/dtc_protocol.py`:
- `build_submit_order()`: Constructs Type 200 messages
- `build_cancel_order()`: Constructs Type 202 messages
- `send_logon()`: Constructs Type 1 messages
- `send_heartbeat()`: Constructs Type 3 messages

---

### 5.1.5 Message Reception (Inbound)

**File:** `core/data_bridge.py:405-531`

**Continuous reception loop:**

```
Qt Signal: socket.readyRead
    ↓
_on_ready_read() [Line 405]
    ↓
Read bytes from socket (up to 65536 per chunk)
    ↓
Append to internal buffer (bytearray)
    ↓
Parse null-terminated frames
    ↓
For each complete frame:
  - Decode JSON
  - Validate structure
  - Detect message type
  - Route to handler
```

**Detailed flow:**

#### Step 1: Read from Socket
```python
while self._socket.bytesAvailable() > 0:
    chunk = self._socket.read(65536)
    self._buffer.extend(chunk)
```

**Buffer growth:** Messages can span multiple TCP packets. Buffer accumulates bytes until a complete null-terminated frame is available.

---

#### Step 2: Frame Extraction
**Function:** `parse_messages(buffer)` in `services/dtc_protocol.py:31`

```python
def parse_messages(buffer: bytearray) -> tuple[list[dict], bytearray]:
    messages = []
    while b'\x00' in buffer:
        # Find null terminator
        idx = buffer.index(b'\x00')

        # Extract frame
        frame = buffer[:idx]

        # Remove from buffer (including null byte)
        buffer = buffer[idx+1:]

        # Decode JSON
        try:
            msg = orjson.loads(frame)
            messages.append(msg)
        except Exception:
            # Skip malformed frames
            continue

    return messages, buffer  # Remaining incomplete data stays in buffer
```

**Result:** List of complete messages + remaining buffer for next read

---

#### Step 3: Message Validation
**File:** `core/data_bridge.py:426-443`

```python
for raw_msg in messages:
    # 1. Check type
    if not isinstance(raw_msg, dict):
        log.warning("Non-dict message received")
        continue

    # 2. Extract message type
    msg_type = raw_msg.get("Type")
    if msg_type is None:
        log.warning("Message missing 'Type' field")
        continue

    # 3. Update watchdog (connection is alive)
    self._last_msg_ts = time.time()

    # 4. Handle frame
    self._handle_frame(raw_msg)
```

---

#### Step 4: Frame Handling
**Function:** `_handle_frame(raw_msg)` at line 470

**Routing by message type:**

| Type | Name | Handler |
|------|------|---------|
| 2 | LOGON_RESPONSE | `_check_logon()` |
| 3 | HEARTBEAT | Ignored (no action needed) |
| 6 | ENCODING_RESPONSE | Ignored (JSON mode already established) |
| 301 | ORDER_UPDATE | Normalized to AppMessage, routed to MessageRouter |
| 304 | HISTORICAL_ORDER_FILL_RESPONSE | Normalized, routed |
| 306 | POSITION_UPDATE | Normalized, routed |
| 401 | TRADE_ACCOUNT_RESPONSE | Normalized, routed |
| 600 | ACCOUNT_BALANCE_UPDATE | Normalized, routed |
| Others | Unknown | Logged if DEBUG_DTC enabled |

**Control frames** (2, 3, 6): Handled directly by DTCClientJSON, not passed to application layer.

**Data frames** (301, 306, 401, 600): Normalized to `AppMessage` format and routed.

---

#### Step 5: Normalization to AppMessage
**Function:** `_dtc_to_app_event(raw_msg)` at line 59

**Purpose:** Convert DTC-specific message format to application-internal format.

**Example transformation:**

**DTC Type 301 (OrderUpdate):**
```json
{
  "Type": 301,
  "ServerOrderID": "12345",
  "Symbol": "MESZ24",
  "BuySell": 1,
  "OrderStatus": 7,
  "OrderQuantity": 5,
  "FilledQuantity": 5,
  "AverageFillPrice": 5998.50,
  "TradeAccount": "Sim1",
  "LatestTransactionDateTime": 1699881234.0
}
```

**Normalized to AppMessage:**
```python
{
    "type": "ORDER_UPDATE",
    "payload": {
        "order_id": "12345",
        "symbol": "MESZ24",
        "side": "BUY",
        "status": "FILLED",
        "qty": 5,
        "filled_qty": 5,
        "filled_price": 5998.50,
        "account": "Sim1",
        "timestamp": 1699881234.0
    }
}
```

**Field coalescing:**
Normalization functions handle multiple possible field names:

```python
def _normalize_order(msg: dict) -> dict:
    # Quantity: try OrderQuantity, then Quantity, then TotalQuantity
    qty = msg.get("OrderQuantity") or msg.get("Quantity") or msg.get("TotalQuantity")

    # Price: try Price1, then Price, then LimitPrice, then StopPrice
    price = msg.get("Price1") or msg.get("Price") or msg.get("LimitPrice") or msg.get("StopPrice")

    # ... and so on
```

**Why coalescing:** Different Sierra Chart versions send different field names. Normalization ensures APPSIERRA works across versions.

---

#### Step 6: Emit to Application
**Function:** `_emit_app(app_msg)` at line 179

**Two routes:**

1. **Blinker Signal:**
```python
signal_order.send(payload)      # For ORDER_UPDATE
signal_position.send(payload)   # For POSITION_UPDATE
signal_balance.send(payload)    # For ACCOUNT_BALANCE_UPDATE
signal_trade_account.send(payload)  # For TRADE_ACCOUNT_RESPONSE
```

2. **MessageRouter:**
```python
router.route(app_msg)
```

**Why both:** Signals allow loosely-coupled subscribers (e.g., debug loggers), while MessageRouter provides centralized handling.

---

### 5.1.6 Message Transformation

**File:** `services/dtc_schemas.py`

**Pydantic validation layer:**

Each DTC message type has a corresponding Pydantic model that:
- Validates field types
- Provides field aliases for backward compatibility
- Offers helper methods for common operations

**Example: OrderUpdate model**

```python
class OrderUpdate(BaseModel):
    Type: int = Field(default=301)
    ServerOrderID: Optional[str] = None
    Symbol: str
    BuySell: int = Field(..., ge=1, le=2)  # Validator: must be 1 or 2
    OrderStatus: int = Field(..., ge=0, le=9)

    # Field aliases
    OrderQuantity: Optional[int] = Field(None, alias="Quantity")
    TotalQuantity: Optional[int] = Field(None, alias="TotalQuantity")

    # Helper methods
    def get_quantity(self) -> Optional[int]:
        return self.OrderQuantity or self.TotalQuantity or self.Quantity

    def is_terminal(self) -> bool:
        return self.OrderStatus in [6, 7, 8]  # Canceled, Filled, Rejected
```

**Parsing function:**

```python
def parse_dtc_message(raw: dict) -> DTCMessage:
    msg_type = raw.get("Type")

    # Look up model class
    model_class = DTC_MESSAGE_REGISTRY.get(msg_type, DTCMessage)

    # Parse with Pydantic
    return model_class(**raw)
```

**Error handling:**
If Pydantic validation fails (e.g., unexpected field type), it raises `ValidationError`. This is caught in `_handle_frame()` and logged, but doesn't crash the application.

---

### 5.1.7 Disconnect, Reconnect, and Error Handling

**Disconnection triggers:**

1. **Network failure:** TCP socket closes unexpectedly
2. **Sierra Chart shutdown:** DTC server stops
3. **User action:** App explicitly disconnects
4. **Watchdog timeout:** No messages received for 25 seconds

**Disconnect handler:** `_on_disconnected()` at line 293

**Actions taken:**
```python
1. Stop heartbeat timer
2. Stop watchdog timer
3. Stop logon handshake grace timer
4. Emit disconnected signal
5. Schedule reconnect (exponential backoff)
```

**Reconnection strategy:**
```python
Base delay: 2 seconds
Backoff: delay * (2 ^ attempt)
Maximum: 30 seconds
Reset on success: attempt counter = 0
```

**Example sequence:**
- Attempt 1: Wait 2s, try reconnect
- Attempt 2: Wait 4s, try reconnect
- Attempt 3: Wait 8s, try reconnect
- Attempt 4: Wait 16s, try reconnect
- Attempt 5+: Wait 30s, try reconnect
- Success: Reset to 2s for next disconnect

**Reconnect function:** `_schedule_reconnect()` at line 333

```python
def _schedule_reconnect(self):
    delay = min(2000 * (2 ** self._reconnect_attempts), 30000)
    log.info("Scheduling reconnect", delay_ms=delay)
    QTimer.singleShot(delay, self.connect)
    self._reconnect_attempts += 1
```

---

**Error types handled:**

#### 1. Connection Refused
**Cause:** Sierra Chart DTC server not running
**Handling:** `_on_error()` logs error, emits `errorOccurred` signal, schedules reconnect
**User feedback:** Panel 1 shows "Disconnected" status

#### 2. Socket Timeout
**Cause:** Network delay, no response from server
**Handling:** Same as connection refused

#### 3. Invalid JSON
**Cause:** Corrupted data, binary DTC mode enabled
**Handling:**
```python
try:
    msg = orjson.loads(frame)
except JSONDecodeError:
    log.warning("Malformed JSON", sample=frame[:100])
    _maybe_detect_binary(frame)  # Heuristic check
    continue  # Skip this frame, continue processing
```

**Binary detection:** `_maybe_detect_binary()` at line 445
- Checks if frame starts with `[uint16 size][uint16 type]` pattern
- If detected: Logs diagnostic with hint to enable JSON encoding in Sierra Chart settings
- Emits `errorOccurred` signal with configuration instructions

#### 4. Watchdog Timeout
**Trigger:** `time.time() - _last_msg_ts > 25` seconds
**Handling:** `_check_watchdog()` aborts connection and triggers reconnect

**Watchdog timer:** Runs every 2 seconds at line 348
```python
def _check_watchdog(self):
    if time.time() - self._last_msg_ts > 25:
        log.warning("Watchdog timeout, aborting stale connection")
        self._socket.abort()
```

---

**Heartbeat system:**

**Purpose:** Keep connection alive, detect dead connections
**Interval:** 5 seconds (configurable via `_heartbeat_interval`)
**Message:** `{"Type": 3}`

**Timer:** `_heartbeat_timer` at line 336
```python
def _send_heartbeat(self):
    if self._socket and self._socket.state() == QTcpSocket.ConnectedState:
        self.send({"Type": 3})
```

**Why needed:**
- Prevents router/firewall from closing idle TCP connection
- Allows server to detect dead clients
- Provides regular "alive" signal for watchdog timer

---

**Recovery sequence:**

After reconnect succeeds, application state must be resynchronized:

**File:** `core/message_router.py:172-283`

**Function:** `trigger_recovery_sequence()`

**3-step process:**

1. **Request Positions** (Type 500)
   ```json
   {
     "Type": 500,
     "RequestID": 9001,
     "TradeAccount": ""
   }
   ```
   **Response:** Type 306 messages for all open positions

2. **Request Open Orders** (Type 305)
   ```json
   {
     "Type": 305,
     "RequestID": 9002,
     "RequestAllOrders": 1
   }
   ```
   **Response:** Type 301 messages for all open orders

3. **Request Historical Fills** (Type 303)
   ```json
   {
     "Type": 303,
     "RequestID": 9003,
     "ServerOrderID": "",
     "NumberOfDays": 7
   }
   ```
   **Response:** Type 304 messages for fills in last 7 days

4. **Relink Bracket Orders**
   - Parse parent-child relationships from order text fields
   - Reconstruct OCO (One-Cancels-Other) linkages
   - Ensure stop-loss and profit-target orders are properly paired

**When triggered:**
- App startup (after initial connection)
- Network reconnect (after disconnect)
- User manual trigger (debug button)

**Why needed:**
If app was offline, it may have missed order fills, position changes, or cancellations. Recovery sequence rebuilds accurate state from server's authoritative data.

---

### 5.1.8 Mode Detection and Safety

**File:** `core/message_router.py:91-130`

**What it does:**
Detects when incoming DTC messages don't match the current trading mode, which could indicate:
- User switched accounts in Sierra Chart
- Wrong account selected
- Configuration mismatch

**Function:** `_check_mode_drift()`

**Detection logic:**
```python
# Extract account from DTC message
incoming_account = msg.get("TradeAccount")

# Detect mode from account name
incoming_mode = detect_mode_from_account(incoming_account)

# Compare to current state
if incoming_mode != state.current_mode or incoming_account != state.current_account:
    # MODE DRIFT DETECTED
    log.warning("Mode drift detected",
                current=(state.current_mode, state.current_account),
                incoming=(incoming_mode, incoming_account))

    # Safety action: disarm LIVE trading
    if state.current_mode == "LIVE":
        disarm_live_trading(reason="mode_drift")

    # Emit warning to UI
    emit_mode_drift_warning(...)
```

**Mode detection function:** `detect_mode_from_account(account: str)` in `utils/trade_mode.py`

**Detection rules:**
```python
if account.startswith("Sim"):
    return "SIM"
elif account.isdigit():
    return "LIVE"
else:
    return "DEBUG"
```

**Examples:**
- `"Sim1"` → SIM mode
- `"Sim2"` → SIM mode
- `"120005"` → LIVE mode
- `"TestAccount"` → DEBUG mode

**Safety mechanism:**
If mode drift is detected while LIVE trading is armed, the system immediately disarms to prevent accidental real-money orders with wrong account.

**Debouncing:**
Mode drift check is debounced to prevent spam if many messages arrive with same drift. Only logs once per drift event, with 2-second cooldown.

---

## 5.2 OTHER EXTERNAL INTEGRATIONS

### 5.2.1 Logging Service (structlog)

**Module:** `utils/logger.py`

**What it is:**
Structured logging system that outputs to both console (debug mode) and rotating file.

**Logging targets:**

1. **Console Handler** (conditional)
   - Only active when `TRADING_MODE == "DEBUG"`
   - Level: DEBUG or INFO (based on `QUIET_STARTUP` flag)
   - Format: Human-readable with colors (if supported)

2. **File Handler** (always active)
   - Path: `logs/app.log`
   - Max size: 1 MB per file
   - Backups: 3 rotating files (app.log, app.log.1, app.log.2, app.log.3)
   - Level: DEBUG or INFO
   - Format: `[timestamp] [level] [module] message key1=val1 key2=val2`

**How messages are sent:**
```python
from utils.logger import get_logger
log = get_logger(__name__)
log.info("order_filled", symbol="MESZ24", qty=5, price=5998.50)
```

**Output:**
```
[2024-11-13T10:30:45Z] [INFO] [panels.panel2] order_filled symbol=MESZ24 qty=5 price=5998.50
```

**Log levels:**
- DEBUG: Verbose output for diagnosis
- INFO: Normal operational events
- WARNING: Unexpected but recoverable issues
- ERROR: Errors requiring attention
- CRITICAL: Severe errors

**Debug flags:**
- `DEBUG_DTC`: DTC protocol messages
- `DEBUG_DATA`: Message payloads
- `DEBUG_CORE`: Core system events
- `DEBUG_UI`: UI updates
- `DEBUG_NETWORK`: Socket events

**Initialization:**
`_init_logger_system()` called once at app startup. Uses decorator pattern to ensure single initialization.

**Error handling:**
If log directory can't be created, logs to stderr and continues (doesn't crash app).

---

### 5.2.2 File-Based Persistence (JSON/JSONL)

**Module:** `utils/atomic_persistence.py` and `core/persistence.py`

**What it is:**
Local file storage for application state that must survive restarts.

**Write operations:**

1. **Atomic JSON writes:**
   ```python
   save_json_atomic(data, path)
   ```
   - Writes to temporary file
   - Atomic rename to final path
   - Guarantees file is never partially written

2. **Append-only JSONL:**
   ```python
   append_jsonl(path, record)
   ```
   - Appends single JSON line to file
   - Low memory, fast sequential writes

**Read operations:**

1. **Load JSON:**
   ```python
   data = load_json_atomic(path)
   ```
   - Returns dict or None if missing/corrupt

2. **Read JSONL:**
   ```python
   records = read_jsonl(path)
   ```
   - Returns list of all records

**Files managed:**

| File | Contents | When Written |
|------|----------|--------------|
| `data/panel2_state_{mode}_{account}.json` | Open position state | Every position change |
| `data/sim_balance_{account}.json` | SIM starting balance | Every balance reset |
| `config/config.json` | User configuration | Manual edit only |
| `~/.sierra_pnl_monitor/equity_curve.jsonl` | Time-series equity | Not currently used |

**Error handling:**
- Missing file: Returns None or empty list
- Corrupted JSON: Logs error, returns None
- Permission denied: Logs error, continues with in-memory state

**Schema versioning:**
Every JSON file includes:
```json
{
  "_schema_version": "1.0",
  "_saved_at_utc": "2024-11-13T10:30:00Z"
}
```

If version mismatch detected on load, warning is logged but data is still used.

---

### 5.2.3 Database (PostgreSQL/SQLite via SQLAlchemy)

**Module:** `data/db_engine.py`

**What it is:**
Persistent relational database for trade records, orders, and account balances.

**Connection establishment:**

**Priority chain:**
1. Try `DB_URL` environment variable (PostgreSQL connection string)
2. Try `POSTGRES_DSN` environment variable
3. Fall back to SQLite file: `sqlite:///data/appsierra.db`
4. Last resort: In-memory SQLite (warning logged)

**How connection is established:**
```python
engine = create_engine(
    db_url,
    pool_pre_ping=True,  # Test connection before use
    echo=DEBUG_MODE      # Log SQL in debug mode
)
```

**Initialization:**
`init_db()` called at app startup:
1. Creates all tables from SQLModel metadata
2. Runs migrations from `data/migrations/*.sql`

**Migrations:**
- Files: `data/migrations/add_efficiency_column.sql`, etc.
- Applied in alphabetical order
- Must be idempotent (safe to run multiple times)

**Message types sent:** SQL queries via SQLAlchemy
**Message types received:** Result sets

**Disconnect/reconnect handling:**
- `pool_pre_ping=True` prevents stale connection errors
- If connection fails, exception is raised and logged
- Reconnection is automatic on next query (handled by SQLAlchemy)

**Error handling:**
- Connection failure: Falls back to next option in chain
- Query failure: Logged via structlog, exception propagated to caller
- Transaction rollback: Automatic on exception in `with get_session()` context

---

### 5.2.4 Qt Signal/Slot System

**What it is:**
Qt's built-in inter-component communication mechanism.

**How APPSIERRA uses it:**

**Signals emitted by DTCClientJSON:**
- `connected`: TCP connection established
- `disconnected`: TCP connection lost
- `messageReceived(dict)`: DTC message arrived
- `errorOccurred(str)`: Socket error or protocol error
- `session_ready`: Logon complete, ready for requests

**Slots (handlers):**
- `MainWindow._on_connected()`: Updates UI connection status
- `MainWindow._on_disconnected()`: Shows disconnect warning
- `MessageRouter._on_order_signal()`: Processes order updates
- `Panel1._on_balance_changed()`: Updates balance display

**Cross-thread communication:**
Qt signals are thread-safe by default. However, APPSIERRA explicitly marshals callbacks to Qt main thread using `marshal_to_qt_thread()` to ensure UI updates happen on correct thread.

**Example:**
```python
def marshal_to_qt_thread(callback, *args):
    QTimer.singleShot(0, lambda: callback(*args))
```

This ensures callback runs on Qt main thread's event loop, preventing race conditions in UI rendering.

---

### 5.2.5 Blinker Event Bus

**Module:** `blinker` (third-party library)

**What it is:**
Lightweight event system for loosely-coupled pub/sub messaging.

**How APPSIERRA uses it:**

**Signals defined:**
```python
signal_trade_account = Signal("trade_account")
signal_balance = Signal("balance")
signal_position = Signal("position")
signal_order = Signal("order")
```

**Publishers:**
- `DTCClientJSON._emit_app()`: Sends DTC events

**Subscribers:**
- `MessageRouter`: Routes to panels
- Debug loggers: Log events for diagnosis
- Future extensions: Can subscribe without modifying existing code

**Example:**
```python
# Subscribe
signal_order.connect(my_handler)

# Publish
signal_order.send(payload)

# Handler called
def my_handler(sender, **payload):
    print(f"Order update: {payload}")
```

**Why used:**
Allows adding new functionality without modifying core message handling code. For example, a new analytics module can subscribe to `signal_order` without changing DTCClientJSON or MessageRouter.

---

## 5.3 SUMMARY: INTEGRATION TOUCHPOINTS

### Entry Points (Where External Data Enters APPSIERRA)

1. **DTC Socket:** `DTCClientJSON._on_ready_read()` in `core/data_bridge.py:405`
2. **Config File:** Settings loaded in `config/settings.py` at import time
3. **Database:** Queries via `get_session()` context manager in `data/db_engine.py`
4. **JSON Files:** `load_json_atomic()` in `utils/atomic_persistence.py`

### Exit Points (Where APPSIERRA Sends Data Out)

1. **DTC Socket:** `DTCClientJSON.send()` in `core/data_bridge.py:657`
2. **Database:** `session.add()` + `session.commit()` in TradeManager
3. **JSON Files:** `save_json_atomic()` in `utils/atomic_persistence.py`
4. **Log Files:** `log.info()` / `log.error()` via structlog

### Critical Paths (High-Priority Message Flows)

1. **Order Fill → Position Update:**
   ```
   DTC Type 301 → DTCClientJSON → MessageRouter → Panel2 → TradeManager → Database
   ```

2. **Balance Update:**
   ```
   DTC Type 600 → DTCClientJSON → MessageRouter → StateManager → Panel1 UI
   ```

3. **Trade Close → Balance Recalculation:**
   ```
   Panel2 close action → TradeManager.record_close_trade() → Database write → SimBalanceManager.update_sim_balance() → StateManager → Panel1 UI
   ```

---

**End of Phase 5 Documentation**
