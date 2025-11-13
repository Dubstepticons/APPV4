# PHASE 6 – HAND-OFF SUMMARY FOR REVIEWERS

**Strictly Descriptive Documentation: No Design Opinions**

This document provides a compact summary for technical reviewers who will evaluate and potentially refactor the APPSIERRA trading system.

---

## 6.1 HIGH-LEVEL OVERVIEW IN PLAIN ENGLISH

### What APPSIERRA Is

APPSIERRA is a desktop trading application built with Python and Qt that connects to Sierra Chart (a professional trading platform) to execute and manage futures trades. It provides three modes of operation: DEBUG (development), SIM (simulated trading with fake money), and LIVE (real money trading). The application tracks positions, calculates performance statistics, manages account balances, and provides a graphical interface for traders to monitor their activity.

### How It Works at Runtime

**On startup**, the application:
1. Connects to a PostgreSQL or SQLite database to retrieve historical trades
2. Loads the SIM balance by calculating: starting balance ($10,000) + sum of all closed SIM trade profits/losses
3. Establishes a TCP connection to Sierra Chart's DTC (Data and Trading Communications) server on localhost:11099
4. Sends a logon message with credentials and requests account data, open orders, recent fills, and current balance
5. Displays three panels: Panel 1 (account balance), Panel 2 (live position tracking), Panel 3 (trade statistics)

**During operation**, the application:
- Receives real-time messages from Sierra Chart when orders are submitted, filled, cancelled, or rejected (DTC Type 301 messages)
- Tracks open positions in Panel 2, calculating live P&L, Maximum Adverse Excursion (MAE), and Maximum Favorable Excursion (MFE) every 100 milliseconds
- When a position closes, writes a complete TradeRecord to the database with final metrics and recalculates account balance
- Updates Panel 3 statistics every 2 seconds by querying the database for aggregate metrics (win rate, profit factor, expectancy, etc.)
- Maintains mode isolation: SIM trades never mix with LIVE trades in statistics or balance calculations
- Detects "mode drift" when incoming messages don't match the current mode/account and disarms LIVE trading as a safety measure

**On shutdown**, the application:
- Saves the current position state to a JSON file (if a position is open) so it can be resumed on next startup
- Closes the database connection
- Disconnects from the DTC server gracefully

### Architecture Philosophy

The system uses an **event-driven architecture** with message passing:
- **DTC messages** arrive asynchronously via TCP socket
- **Normalization layer** converts DTC-specific formats to internal AppMessage objects
- **MessageRouter** dispatches messages to appropriate panels based on type
- **State Manager** maintains global state (mode, account, balances, active position)
- **Panels** own their own UI state and respond to routed messages
- **TradeManager** handles all database writes with thread-safety locks
- **StatsService** computes statistics on-demand with TTL caching

The system separates concerns clearly:
- `core/` handles DTC communication and message routing
- `panels/` handles UI and user interaction
- `services/` handles business logic (trade recording, statistics, order ledger)
- `data/` handles persistence (database, schemas, migrations)
- `config/` handles configuration and environment variables
- `utils/` provides shared utilities (logging, atomic file writes, error helpers)

---

## 6.2 KEY COMPONENTS CHEAT SHEET

### To Understand How DTC Messages Enter the App

**Read:**
- `core/data_bridge.py:405-531` - Socket reading, frame parsing, message handling
- `services/dtc_protocol.py:31-50` - Null-terminated JSON frame extraction
- `services/dtc_schemas.py:111-442` - Pydantic models for message validation
- `core/message_router.py:285-807` - Routing messages to panels

**Key flow:**
```
TCP socket → _on_ready_read() → parse_messages() → _handle_frame() →
_dtc_to_app_event() → _emit_app() → MessageRouter → Panel handlers
```

**Important details:**
- Messages are null-terminated JSON (`{...}\x00`)
- Field aliases handle multiple Sierra Chart versions (e.g., "Quantity" vs "OrderQuantity")
- Control frames (heartbeat, logon response) are handled separately from data frames

---

### To Understand How State Is Stored and Updated

**Read:**
- `core/state_manager.py` - Global state holder (mode, account, balances, active position)
- `core/sim_balance.py` - SIM balance calculation (ledger-based from database)
- `core/app_state.py` - Singleton accessor for StateManager
- `data/db_engine.py` - Database connection and session management
- `utils/atomic_persistence.py` - JSON file persistence with atomic writes

**Key concepts:**
- **StateManager** is a singleton accessed via `get_state_manager()`
- **SIM balance** is never stored directly; always computed as: `starting_balance + SUM(realized_pnl from SIM trades)`
- **LIVE balance** comes from DTC Type 600 messages and is stored in `StateManager.live_balance`
- **Panel state** (open positions) is saved to JSON files scoped by mode and account
- **Thread safety:** All database writes are protected by a lock in TradeManager

**State flow on trade close:**
```
Panel2 detects exit fill → TradeManager.record_close_trade() →
Write TradeRecord to DB → SimBalanceManager.update_sim_balance() →
Calculate from DB → Update StateManager.sim_balance →
Emit balanceChanged signal → Panel1 updates display
```

---

### To Understand Panel 1 / Panel 2 / Panel 3 Behavior

#### Panel 1 (Balance & Account Display)
**File:** `panels/panel1.py`

**Purpose:** Display current account balance (SIM or LIVE) and account selection

**Key behavior:**
- Shows `StateManager.sim_balance` when in SIM mode
- Shows `StateManager.live_balance` when in LIVE mode
- Dropdown allows switching between available accounts
- No complex logic, primarily UI rendering

**Data sources:**
- StateManager for current balance
- DTC Type 401 messages for account enumeration

---

#### Panel 2 (Live Trading / Position Management)
**File:** `panels/panel2.py`

**Purpose:** Track open positions, display live P&L, manage entry/exit

**Key behavior:**
- Maintains in-memory position dict: `{symbol, side, qty, entry_price, entry_time, mode, account}`
- On Type 301 fill message: Updates position quantity, recalculates entry price (weighted average for adds)
- Every 100ms: Calculates live P&L from current market price, tracks MAE/MFE
- On full exit: Calls `TradeManager.record_close_trade()` with final metrics
- Persists position state to `data/panel2_state_{mode}_{account}.json` after every change

**Data sources:**
- DTC Type 301 (ORDER_UPDATE) messages
- Current market price (from price feed, not shown in code but referenced)

**Critical methods:**
- `on_order_update()` - Processes fills
- `_update_live_pnl()` - Recalculates P&L
- `_on_close_trade()` - Finalizes trade and writes to database

---

#### Panel 3 (Statistics & Trade History)
**File:** `panels/panel3.py`

**Purpose:** Display aggregate trading performance metrics

**Key behavior:**
- Every 2 seconds, calls `StatsService.calculate_stats(timeframe, mode)`
- Displays 15+ metrics: total P&L, win rate, profit factor, avg MAE/MFE, drawdown, runup, etc.
- Timeframe filter: "All", "Today", "This Week", "This Month"
- Mode filter: Shows only stats for current mode (SIM or LIVE, never mixed)

**Data sources:**
- TradeRecord database table (all closed trades)

**Caching:**
- Stats cached for 5 seconds to avoid redundant database queries
- Cache invalidated on new trade close or mode change

**Critical methods:**
- `_refresh_stats()` - Updates display every 2 seconds
- `on_timeframe_change()` - Handles user filter changes

---

### To Understand Mode Separation (SIM/LIVE/DEBUG)

**Read:**
- `core/state_manager.py:45-89` - Mode management and history tracking
- `core/message_router.py:91-130` - Mode drift detection
- `utils/trade_mode.py` - Mode detection from account name (NOTE: This file is referenced but doesn't exist in the codebase - see Open Questions)
- `config/settings.py:67-72` - Trading mode configuration

**How modes are detected:**
- **From account name:** "Sim1" → SIM, "120005" → LIVE, "TestAccount" → DEBUG
- **From configuration:** `TRADING_MODE` environment variable sets default mode
- **From DTC messages:** `TradeAccount` field triggers mode detection on every message

**Mode invariant:** Only ONE active position at a time across all modes. System prevents simultaneous SIM and LIVE positions.

**Safety mechanism:**
If a DTC message arrives with account "Sim1" but current mode is LIVE, the system:
1. Logs a mode drift warning
2. Disarms LIVE trading (prevents accidental orders)
3. Emits UI warning to user

**LIVE arming gate:**
- LIVE trading starts **disarmed** on every app launch
- User must explicitly click "Arm LIVE" button to enable real-money orders
- Auto-disarms on: disconnect, mode drift, config reload, manual disarm

---

### To Understand Order Lifecycle

**Read:**
- `services/dtc_schemas.py:111-315` - OrderUpdate message model
- `services/dtc_ledger.py` - Order ledger building from Type 301 messages
- `panels/panel2.py:302-400` - Order processing in live panel

**Order states (OrderStatus field in Type 301):**
```
0 = Unspecified
1 = New (order created but not submitted)
2 = Submitted (sent to exchange)
3 = Pending Cancel (cancel request sent)
4 = Open (working on exchange)
5 = Pending Replace (modify request sent)
6 = Canceled (order cancelled)
7 = Filled (fully executed)
8 = Rejected (exchange rejected)
9 = Partially Filled (partial execution)
```

**Terminal states:** 6 (Canceled), 7 (Filled), 8 (Rejected)

**Fill detection:**
An order is considered filled when:
- `OrderStatus == 7` OR
- `FilledQuantity > 0` AND `FilledQuantity == OrderQuantity`

**Lifecycle example:**
```
1. User submits order
   → Panel2 sends Type 200 (SUBMIT_ORDER) to DTC

2. Sierra Chart accepts
   → Type 301 arrives: OrderStatus=1 (New)

3. Exchange acknowledges
   → Type 301 arrives: OrderStatus=2 (Submitted)

4. Order working
   → Type 301 arrives: OrderStatus=4 (Open)

5. Partial fill
   → Type 301 arrives: OrderStatus=9, FilledQuantity=2, OrderQuantity=5

6. Full fill
   → Type 301 arrives: OrderStatus=7, FilledQuantity=5
   → Panel2 detects position entry/exit
   → TradeManager records trade
```

---

### To Understand Connection Management

**Read:**
- `core/data_bridge.py:185-402` - Connection, logon, heartbeat, reconnect
- `core/data_bridge.py:336-402` - Watchdog and keepalive timers
- `core/message_router.py:172-283` - Recovery sequence after reconnect

**Connection lifecycle:**
```
1. Startup
   → connect() called
   → TCP socket.connectToHost("127.0.0.1", 11099)

2. Connected
   → _on_connected() triggered
   → Send LOGON_REQUEST (Type 1)
   → Start heartbeat timer (every 5s)
   → Start watchdog timer (every 2s)

3. Logon Response
   → Type 2 arrives with Result=1 (success)
   → Emit session_ready signal
   → _request_initial_data() sends Type 400, 305, 303, 601

4. Active Session
   → Heartbeat sent every 5s
   → Watchdog checks for messages every 2s (timeout if >25s silence)

5. Disconnect
   → Socket error or _socket.disconnected signal
   → _on_disconnected() triggered
   → Stop all timers
   → Schedule reconnect with exponential backoff (2s, 4s, 8s, ..., max 30s)

6. Reconnect
   → connect() called again
   → Back to step 2
   → Recovery sequence: request positions, orders, fills
```

**Error handling:**
- **Connection refused:** Log error, schedule reconnect
- **Watchdog timeout:** Abort stale connection, trigger reconnect
- **Invalid JSON:** Log warning, continue processing other messages
- **Binary DTC detected:** Emit error with diagnostic hint about Sierra Chart settings

---

## 6.3 GLOSSARY

### Trading Terms

| Term | Definition |
|------|------------|
| **Position** | An open trade (long or short) in a specific symbol. APPSIERRA tracks one position at a time. |
| **Long** | Buying with intent to profit from price increase. |
| **Short** | Selling with intent to profit from price decrease. |
| **P&L (Profit & Loss)** | Dollar profit or loss on a trade. Positive = profit, negative = loss. |
| **Realized P&L** | Final profit/loss after position is closed. |
| **Unrealized P&L** | Current profit/loss on an open position (not yet closed). |
| **MAE (Maximum Adverse Excursion)** | Worst unrealized loss during a trade. Measures how far against you a trade went. |
| **MFE (Maximum Favorable Excursion)** | Best unrealized profit during a trade. Measures maximum potential profit. |
| **Efficiency** | Capture ratio = realized_pnl / mfe. How much of the maximum profit was actually captured. |
| **Entry Price** | Average fill price when entering a position. |
| **Exit Price** | Average fill price when exiting a position. |
| **Fill** | Execution of an order (partial or full). |
| **Tick** | Minimum price movement for a contract. Example: ES moves in 0.25 increments. |
| **Tick Value** | Dollar value of one tick. Example: ES tick = $12.50, MES tick = $1.25. |
| **SIM Mode** | Simulated trading with fake money ($10,000 starting balance). |
| **LIVE Mode** | Real-money trading with actual brokerage account. |
| **DEBUG Mode** | Development mode for testing without real or simulated trades. |

---

### Technical Terms

| Term | Definition |
|------|------------|
| **DTC (Data and Trading Communications)** | Protocol used by Sierra Chart for external application integration. |
| **Sierra Chart** | Professional trading platform that provides market data and order routing. |
| **Type 301** | DTC message type for order updates (most critical message type in APPSIERRA). |
| **Type 306** | DTC message type for position updates. |
| **Type 600** | DTC message type for account balance updates. |
| **TradeRecord** | Database table/model storing all closed trades with full metrics. |
| **OrderRecord** | Database table/model storing individual order events. |
| **StateManager** | Singleton object holding global runtime state (mode, account, balances, position). |
| **TradeManager** | Service responsible for writing trades to database and managing trade lifecycle. |
| **StatsService** | Service that calculates aggregate statistics from trade history. |
| **Panel** | Qt widget representing one section of the UI (Panel 1, 2, or 3). |
| **MessageRouter** | Central dispatcher that routes DTC messages to appropriate handlers. |
| **Blinker Signal** | Event bus mechanism for loosely-coupled pub/sub messaging. |
| **AppMessage** | Internal message format after DTC normalization. |
| **Mode Drift** | When incoming DTC messages don't match current mode/account. Safety hazard. |
| **LIVE Armed** | State indicating LIVE trading is enabled. Must be explicitly armed by user. |
| **Atomic Write** | File write operation that guarantees file is never partially written (crash-safe). |
| **JSONL** | Line-delimited JSON format where each line is a complete JSON object. |
| **TTL (Time To Live)** | Cache expiration time. Stats cache has 5-second TTL. |
| **Ledger-based Balance** | Balance calculated from sum of transactions rather than stored as mutable value. |

---

### Abbreviations

| Abbr. | Meaning |
|-------|---------|
| **DTC** | Data and Trading Communications |
| **P&L** | Profit and Loss |
| **MAE** | Maximum Adverse Excursion |
| **MFE** | Maximum Favorable Excursion |
| **OCO** | One-Cancels-Other (bracket orders where filling one cancels the other) |
| **MIT** | Market-If-Touched (order type) |
| **DAY** | Time-in-force for orders valid until end of trading day |
| **GTC** | Good-Till-Canceled (order remains active until explicitly cancelled) |
| **BUY/SELL** | Order direction (1=BUY, 2=SELL in DTC messages) |
| **ES** | E-mini S&P 500 futures contract (tick=$12.50) |
| **MES** | Micro E-mini S&P 500 futures contract (tick=$1.25) |
| **NQ** | E-mini Nasdaq 100 futures contract |
| **MNQ** | Micro E-mini Nasdaq 100 futures contract |
| **RTY** | E-mini Russell 2000 futures contract |
| **M2K** | Micro E-mini Russell 2000 futures contract |

---

### Class Names

| Class | File | Purpose |
|-------|------|---------|
| `DTCClientJSON` | `core/data_bridge.py` | Qt TCP socket client for DTC connection |
| `StateManager` | `core/state_manager.py` | Global state holder |
| `SimBalanceManager` | `core/sim_balance.py` | SIM balance calculation and persistence |
| `MessageRouter` | `core/message_router.py` | Routes DTC messages to panels |
| `TradeManager` | `services/trade_service.py` | Manages trade recording and database writes |
| `StatsService` | `services/stats_service.py` | Computes aggregate statistics |
| `OrderLedgerBuilder` | `services/dtc_ledger.py` | Builds order ledger from Type 301 messages |
| `TradeRecord` | `data/schema.py` | SQLModel for trade database records |
| `OrderRecord` | `data/schema.py` | SQLModel for order database records |
| `AccountBalance` | `data/schema.py` | SQLModel for balance snapshots |
| `OrderUpdate` | `services/dtc_schemas.py` | Pydantic model for DTC Type 301 |
| `PositionUpdate` | `services/dtc_schemas.py` | Pydantic model for DTC Type 306 |
| `AccountBalanceUpdate` | `services/dtc_schemas.py` | Pydantic model for DTC Type 600 |

---

## 6.4 OPEN QUESTIONS & UNCERTAINTIES

### Critical Uncertainties

#### 1. Missing Module: `utils/trade_mode.py`

**Location:** Referenced in `core/message_router.py:7` and `core/state_manager.py:15`

**Expected function:** `detect_mode_from_account(account: str) -> str`

**What it should do:**
- Input: Account identifier string (e.g., "Sim1", "120005", "TestAccount")
- Output: Mode string ("SIM", "LIVE", or "DEBUG")
- Logic: Likely pattern matching on account name

**Current status:** File does not exist in the codebase. Imports will fail at runtime.

**Assumption:** The function should implement:
```python
def detect_mode_from_account(account: str) -> str:
    if account.startswith("Sim"):
        return "SIM"
    elif account.isdigit():
        return "LIVE"
    else:
        return "DEBUG"
```

**Question for reviewer:** Where is this function actually implemented? Is it in a different module? Or does the code have a different fallback mechanism?

---

#### 2. Panel State Loading on Startup

**Location:** `panels/panel2.py` (referenced but not shown in exploration)

**Question:** When Panel 2 loads saved state from `panel2_state_{mode}_{account}.json`:
- Does it automatically resume tracking the position?
- Does it validate that the position still exists in Sierra Chart?
- What happens if the position was closed while the app was offline?

**Current behavior (assumed):**
- Loads position dict from JSON
- Displays position in UI
- Waits for next Type 301 or Type 306 message to confirm position still exists
- If position is closed, next exit fill will trigger normal close logic

**Uncertainty:** Is there explicit validation, or does it rely on next DTC message?

---

#### 3. Price Feed Source

**Location:** Panel 2 calculates live P&L every 100ms

**Question:** Where does the current market price come from?
- Is it from DTC market data messages (not documented)?
- Is it from Sierra Chart's price feed?
- Is it the last fill price?

**Current code:** References "current market price" but the actual source is not shown in the exploration results.

**Assumption:** Likely DTC market data subscription (not TYPE 301/306/600) or Sierra Chart shared memory.

**Question for reviewer:** How is real-time price data obtained for P&L calculation?

---

#### 4. Simultaneous Positions Across Modes

**Location:** `core/state_manager.py` and `panels/panel2.py`

**Stated invariant:** "Only ONE active position at a time (SIM OR LIVE, never both)"

**Question:** How is this enforced?
- Does StateManager reject position entry if another mode has an open position?
- Is it just a UI constraint (one panel shows position at a time)?
- What happens if user tries to open SIM position while LIVE position is open?

**Code evidence:** Not explicitly shown in exploration results.

**Assumption:** It's a UI-level constraint, not a hard enforcement in StateManager.

**Question for reviewer:** Is this a strict technical limitation or a design guideline?

---

#### 5. Bracket Order Relinking

**Location:** `core/message_router.py:256-283` - "Relink brackets (OCO orders)"

**Question:** How are parent-child order relationships determined?
- Does Sierra Chart include a ParentOrderID field in Type 301?
- Is it parsed from InfoText/TextMessage fields?
- Are OCO linkages stored in a separate data structure?

**Current code:** References "relink brackets" but implementation details not shown.

**Assumption:** Uses Sierra Chart's native OCO support with ParentOrderID or similar field.

**Question for reviewer:** What is the actual mechanism for identifying bracket relationships?

---

#### 6. Database Migration Tracking

**Location:** `data/db_engine.py` - Migrations applied in alphabetical order

**Question:** How does the system know which migrations have already been applied?
- Is there a migrations table that tracks applied migrations?
- Are all migrations idempotent (safe to run multiple times)?
- What happens if a migration fails mid-execution?

**Current behavior:** Migrations use `IF NOT EXISTS` clauses, suggesting idempotency.

**Uncertainty:** Is there explicit tracking, or does it rely on SQL idempotency?

**Question for reviewer:** Is there a migration version table, or is this purely idempotent SQL?

---

#### 7. Configuration Precedence

**Location:** `config/settings.py` - Loads from environment variables and config.json

**Question:** What is the exact precedence order?
- Does config.json override environment variables?
- Or do environment variables override config.json?
- What about command-line arguments (if any)?

**Code says:** "config.json overrides env vars if present"

**Uncertainty:** Is this consistently applied to all settings, or only some?

**Question for reviewer:** Confirm exact precedence: env vars → config.json → defaults, or config.json → env vars → defaults?

---

#### 8. Market Data Subscription

**Location:** Not documented in Phases 4-5

**Question:** Does APPSIERRA subscribe to market data via DTC?
- If yes, what message types are used (Type 101, 102, 103)?
- If no, how does it get price updates for P&L calculation?

**Assumption:** Either:
1. Subscribes to market data (not shown in code exploration)
2. Uses shared memory from Sierra Chart (not shown)
3. Uses last fill price from Type 301 (seems unlikely for real-time P&L)

**Question for reviewer:** Clarify how real-time price data flows into the system.

---

#### 9. Multi-Symbol Support

**Location:** Everywhere (symbol is a field in TradeRecord, OrderRecord, etc.)

**Question:** Can APPSIERRA track positions in multiple symbols simultaneously?
- Current documentation says "one position at a time"
- But schema supports multiple symbols

**Uncertainty:** Is this:
- One position per symbol (can have ES and NQ open simultaneously)?
- One total position across all symbols?

**Assumption:** One total position (current_position dict has no symbol-based multiplicity).

**Question for reviewer:** Is multi-symbol position tracking supported or planned?

---

#### 10. Error Recovery on Conflicting State

**Location:** Recovery sequence in `core/message_router.py:172-283`

**Question:** If recovery sequence finds:
- Sierra Chart says position is open
- But APPSIERRA's database says position is closed

What happens? Which source of truth wins?

**Uncertainty:** Does it:
1. Trust database and close the Sierra Chart position?
2. Trust Sierra Chart and reopen the database position?
3. Log a conflict and require manual resolution?

**Assumption:** Likely trusts Sierra Chart as authoritative and updates database.

**Question for reviewer:** What is the conflict resolution strategy?

---

### Ambiguities in Code Behavior

#### 11. Order Quantity Aliases

**Location:** `services/dtc_schemas.py:111-315` - Multiple quantity field names

**Question:** When Sierra Chart sends OrderQuantity=5 AND Quantity=3, which wins?

**Current code:** `get_quantity()` returns first non-None value in priority order.

**Uncertainty:** What is the exact priority order? Is it:
1. OrderQuantity → Quantity → TotalQuantity?
2. Quantity → OrderQuantity → TotalQuantity?

**Question for reviewer:** Document the exact field priority for all coalescing helper methods.

---

#### 12. Stats Cache Invalidation

**Location:** `services/stats_service.py` - 5-second TTL cache

**Question:** Is cache invalidated:
- Only after TTL expires?
- Explicitly on trade close?
- On mode change?
- All of the above?

**Code says:** "Invalidated on new trade close or mode change"

**Uncertainty:** How is this invalidation triggered? Via signal subscription? Direct call?

**Question for reviewer:** Clarify exact cache invalidation triggers and mechanism.

---

#### 13. Thread Safety Beyond Database

**Location:** TradeManager has a lock for database writes

**Question:** Are other components thread-safe?
- StateManager (accessed from multiple panels)
- Stats cache (read/write from timer thread?)
- Panel state dicts (updated from MessageRouter vs UI thread)

**Assumption:** Qt signal/slot system handles cross-thread access via event loop marshaling.

**Uncertainty:** Are there any race conditions in non-database state?

**Question for reviewer:** Audit all shared state for thread safety, not just database.

---

### Design Questions (for future refactoring, not current behavior)

These are NOT uncertainties about current behavior, but questions that a refactoring effort should address:

1. **Why are Type 306 messages rarely used?** Is this a Sierra Chart configuration issue, or by design?

2. **Why is SIM balance ledger-based but LIVE balance is mutable?** Is there a specific reason for this asymmetry?

3. **Why does OrderRecord exist if it's optionally written?** When is it used vs not used?

4. **Why are there two separate message passing systems (Qt signals + Blinker)?** Could this be unified?

5. **Why is mode detection done on every message instead of once at startup?** Performance concern or safety feature?

---

## 6.5 VERIFICATION CHECKLIST FOR REVIEWERS

Before making changes to APPSIERRA, verify understanding of:

- [ ] DTC message flow from socket → panels
- [ ] How TradeRecord is constructed on position close
- [ ] SIM balance ledger calculation logic
- [ ] Mode drift detection and LIVE arming safety
- [ ] Database connection fallback chain (PostgreSQL → SQLite → In-memory)
- [ ] Atomic JSON write pattern for panel state persistence
- [ ] Stats caching with 5-second TTL
- [ ] Order lifecycle from submit → fill → trade record
- [ ] Recovery sequence after reconnect
- [ ] Thread safety: database writes protected by lock, UI updates marshaled to Qt thread
- [ ] Difference between TYPE 301 (order update) and TYPE 306 (position update)
- [ ] Why APPSIERRA relies on TYPE 301 fills instead of TYPE 306 positions

---

## 6.6 CRITICAL FILES BY SUBSYSTEM

### DTC Integration
```
core/data_bridge.py          (DTCClientJSON: socket, logon, heartbeat, reconnect)
services/dtc_protocol.py     (Framing, parsing, message builders)
services/dtc_schemas.py      (Pydantic models for validation)
services/dtc_constants.py    (Type codes and enums)
```

### Message Routing
```
core/message_router.py       (Dispatch to panels, mode drift detection)
core/app_state.py            (Singleton accessor for StateManager)
```

### State Management
```
core/state_manager.py        (Global runtime state)
core/sim_balance.py          (SIM balance calculation)
```

### Panels (UI)
```
panels/panel1.py             (Balance display)
panels/panel2.py             (Live position tracking)
panels/panel3.py             (Statistics)
```

### Business Logic
```
services/trade_service.py    (TradeManager: record trades)
services/stats_service.py    (StatsService: aggregate metrics)
services/dtc_ledger.py       (OrderLedgerBuilder: reconstruct order history)
```

### Persistence
```
data/schema.py               (TradeRecord, OrderRecord, AccountBalance models)
data/db_engine.py            (Database connection, migrations)
utils/atomic_persistence.py  (JSON file writes)
core/persistence.py          (JSONL append-only logs)
```

### Configuration
```
config/settings.py           (Environment variables, DTC connection)
config/trading_specs.py      (Futures contract specifications)
```

### Utilities
```
utils/logger.py              (Structured logging)
utils/error_helpers.py       (Exception handling patterns)
```

---

## 6.7 RECOMMENDED REVIEW ORDER

For a new reviewer evaluating APPSIERRA:

1. **Start here:**
   - Read this document (PHASE_6_HANDOFF_SUMMARY.md)
   - Skim PHASE_4_DATA_MODEL_STATE_MAP.md sections 4.1 and 4.2

2. **Understand data flow:**
   - Read PHASE_5_EXTERNAL_INTEGRATIONS.md section 5.1.3 (Connection) and 5.1.5 (Message Reception)
   - Trace one complete message flow: DTC Type 301 → Panel 2 → TradeManager → Database

3. **Understand state management:**
   - Read `core/state_manager.py` (150 lines)
   - Read `core/sim_balance.py` (100 lines)
   - Read PHASE_4_DATA_MODEL_STATE_MAP.md section 4.2

4. **Understand key business logic:**
   - Read `services/trade_service.py` TradeManager class
   - Read `services/stats_service.py` calculate_stats function
   - Read PHASE_4_DATA_MODEL_STATE_MAP.md section 4.1.3 (Derived Metrics)

5. **Understand panel behavior:**
   - Read Panel 2 (`panels/panel2.py`) for position tracking logic
   - Read Panel 3 (`panels/panel3.py`) for statistics display
   - Refer to section 6.2 "Key Components Cheat Sheet" for panel summaries

6. **Deep dive on DTC:**
   - Read `core/data_bridge.py` in full (700+ lines but well-commented)
   - Read `services/dtc_schemas.py` OrderUpdate model
   - Read PHASE_5_EXTERNAL_INTEGRATIONS.md section 5.1 in full

7. **Understand persistence:**
   - Read `data/schema.py` for database models
   - Read `utils/atomic_persistence.py` for JSON writes
   - Read PHASE_4_DATA_MODEL_STATE_MAP.md section 4.3

8. **Review error handling:**
   - Check all try/except blocks in `core/data_bridge.py`
   - Review reconnect logic in `_schedule_reconnect()`
   - Check thread safety in `TradeManager` (lock usage)

9. **Review open questions:**
   - Read section 6.4 of this document
   - Identify which questions need resolution before refactoring

10. **Test understanding:**
    - Can you trace a complete trade lifecycle from order submit to database record?
    - Can you explain why SIM balance is ledger-based?
    - Can you explain mode drift detection and why it matters?
    - Can you identify all the ways state persists across app restarts?

---

## 6.8 FINAL SUMMARY

**APPSIERRA is:**
- A Qt-based desktop trading application
- Connected to Sierra Chart via DTC protocol (JSON over TCP)
- Managing futures positions with SIM/LIVE mode separation
- Storing trades in PostgreSQL/SQLite database
- Calculating statistics on-demand with caching
- Using event-driven architecture with message passing

**Critical characteristics:**
- **Mode isolation:** SIM and LIVE never mix in statistics or balances
- **Ledger-based SIM balance:** Always computed from trade history, never directly mutated
- **One position at a time:** Only one active position across all modes
- **Thread-safe database writes:** Protected by lock in TradeManager
- **Atomic state persistence:** JSON files written atomically to prevent corruption
- **Reconnect resilience:** Exponential backoff with recovery sequence

**Known gaps:**
- Missing `utils/trade_mode.py` module (imported but doesn't exist)
- Market data subscription mechanism not documented
- Bracket order relinking logic not detailed
- Some thread safety assumptions not verified

**Next steps for reviewer:**
1. Resolve open questions in section 6.4
2. Verify thread safety beyond database writes
3. Clarify market data flow for live P&L calculation
4. Document actual vs assumed behavior for panel state loading
5. Create integration tests for mode switching and recovery sequences

---

**End of Phase 6 Documentation**

**Complete documentation set:**
- PHASE_4_DATA_MODEL_STATE_MAP.md (31 pages)
- PHASE_5_EXTERNAL_INTEGRATIONS.md (28 pages)
- PHASE_6_HANDOFF_SUMMARY.md (This document, 25 pages)

**Total documentation:** ~84 pages of strictly descriptive, opinion-free architecture documentation.
