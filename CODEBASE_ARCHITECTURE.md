# APPSIERRA Codebase Architecture - Comprehensive Analysis

## 1. CORE DATA STRUCTURES/MODELS

### A. PRIMARY TRADING ENTITIES (data/schema.py, lines 19-110)

#### TradeRecord (SQLModel) - Lines 19-73
**Location:** `/home/user/APPV4/data/schema.py:19`
**Purpose:** Complete trade record from entry to exit
**Critical Fields:**
- `id`: Primary key (Optional[int])
- `symbol`: Trade symbol (str)
- `side`: "LONG" or "SHORT" (str)
- `qty`: Position quantity (int)
- `mode`: "SIM" or "LIVE" (str, indexed for mode filtering)
- `entry_time`: Order entry time (datetime, indexed)
- `entry_price`: Average entry price (float)
- `exit_time`: Position exit time (Optional[datetime], indexed)
- `exit_price`: Exit price (Optional[float])
- `is_closed`: Trade completion flag (bool)
- `realized_pnl`: Closed trade P&L (Optional[float])
- `commissions`: Commission paid (Optional[float])
- `r_multiple`: Risk multiple (Optional[float])
- `mae`: Maximum Adverse Excursion (Optional[float])
- `mfe`: Maximum Favorable Excursion (Optional[float])
- `efficiency`: Capture ratio = realized_pnl / mfe (Optional[float])
- `entry_vwap`, `entry_cum_delta`: Entry snapshot data
- `exit_vwap`, `exit_cum_delta`: Exit snapshot data
- `account`: Trading account ID (Optional[str])

**Indexes:**
- `idx_trade_mode_exit_time`: Composite on (mode, exit_time)
- `idx_trade_closed_mode`: Composite on (is_closed, mode)

#### OrderRecord (SQLModel) - Lines 75-95
**Location:** `/home/user/APPV4/data/schema.py:75`
**Purpose:** Track individual order execution for trade reconstruction
**Key Fields:**
- `id`: Primary key
- `order_id`: Server order ID (str, indexed)
- `symbol`: Symbol (str, indexed)
- `side`: "BUY" or "SELL" (str)
- `qty`: Order quantity (int)
- `price`: Order price (float)
- `filled_qty`: Filled quantity (int)
- `filled_price`: Fill price (Optional[float])
- `status`: "PENDING", "FILLED", "CANCELLED" (str)
- `mode`: "SIM" or "LIVE" (str, indexed)
- `timestamp`: Order time (datetime, indexed)
- `account`: Account ID (Optional[str])

#### AccountBalance (SQLModel) - Lines 97-109
**Location:** `/home/user/APPV4/data/schema.py:97`
**Purpose:** Store account balance snapshots
**Key Fields:**
- `account_id`: Account identifier (str, indexed)
- `balance`: Current balance (float)
- `mode`: "LIVE" or "SIM" (str, indexed)
- `timestamp`: Snapshot time (datetime, indexed)

---

### B. DTC PROTOCOL MESSAGES (services/dtc_schemas.py)

#### OrderUpdate (Pydantic BaseModel) - Lines 111-315
**Location:** `/home/user/APPV4/services/dtc_schemas.py:111`
**Type:** DTC Message Type 301
**Purpose:** Most important message for order tracking
**Critical Fields:**
- `ServerOrderID`, `ClientOrderID`: Order identifiers
- `TradeAccount`: Account for trade
- `Symbol`, `Exchange`: Security identifier
- `BuySell`: 1=BUY, 2=SELL (int)
- `OrderType`: 1=Market, 2=Limit, 3=Stop, 4=StopLimit, 5=MIT
- `OrderStatus`: 0-9 (0=Unspec, 1=New, 2=Submitted, 3=PendingCancel, 4=Open, 5=PendingReplace, 6=Canceled, 7=Filled, 8=Rejected, 9=PartiallyFilled)
- `OrderUpdateReason`: 0-9 reason codes
- Quantity fields (with aliases): `OrderQuantity`, `Quantity`, `TotalQuantity`, `FilledQuantity`, `RemainingQuantity`
- Price fields (with aliases): `Price1`, `Price2`, `Price`, `LimitPrice`, `StopPrice`
- Fill data: `AverageFillPrice`, `AvgFillPrice`, `LastFillPrice`, `LastFillQuantity`, `LastFillDateTime`
- Position extremes: `HighDuringPosition`, `HighPriceDuringPosition`, `LowDuringPosition`, `LowPriceDuringPosition`
- Timestamps: `OrderReceivedDateTime`, `LatestTransactionDateTime` (Unix epoch seconds)
- Text/Info (with aliases): `InfoText`, `TextMessage`, `FreeFormText`, `RejectText`
- Sequencing: `MessageNumber`, `TotalNumberMessages`, `NoOrders`
- `RequestID`: Links response to request (0=unsolicited)

**Helper Methods:**
- `get_side()`: Returns "Buy" or "Sell"
- `get_order_type()`: Returns human-readable order type
- `get_status()`: Returns human-readable status
- `get_reason()`: Returns human-readable update reason
- `is_terminal()`: True if Filled/Canceled/Rejected
- `is_fill_update()`: True if fill-related update
- `get_quantity()`: Coalesces quantity fields
- `get_price()`: Coalesces price fields
- `get_avg_fill_price()`: Coalesces fill price fields
- `get_high_during_position()`, `get_low_during_position()`: Coalesce position extremes
- `get_timestamp()`: Returns best available Unix timestamp
- `get_text()`: Coalesces text fields with priority

#### PositionUpdate (Pydantic BaseModel) - Lines 339-390
**Location:** `/home/user/APPV4/services/dtc_schemas.py:339`
**Type:** DTC Message Type 306
**Purpose:** Position data (rarely used - Sierra doesn't send unsolicited)
**Key Fields:**
- `TradeAccount`, `Symbol`, `Exchange`
- `Quantity`, `AveragePrice`
- `OpenProfitLoss`, `DailyProfitLoss`
- `HighPriceDuringPosition`, `LowPriceDuringPosition`
- `UpdateReason`: 0=Unsolicited, 1=CurrentPositionsResponse, 2=PositionsResponse
- Sequencing fields: `MessageNumber`, `TotalNumberMessages`, `NoPositions`

#### TradeAccountResponse (Pydantic BaseModel) - Lines 395-403
**Location:** `/home/user/APPV4/services/dtc_schemas.py:395`
**Type:** DTC Message Type 401
**Purpose:** Account information response
**Key Fields:**
- `TradeAccount`: Account ID
- `AccountName`: Display name
- `RequestID`: Request correlation ID

#### AccountBalanceUpdate (Pydantic BaseModel) - Lines 405-427
**Location:** `/home/user/APPV4/services/dtc_schemas.py:405`
**Type:** DTC Message Type 600
**Purpose:** Account balance and equity snapshot
**Key Fields:**
- `TradeAccount`, `CashBalance`
- `BalanceAvailableForNewPositions`, `AccountValue`, `NetLiquidatingValue`
- `AvailableFunds`, `MarginRequirement`, `SecuritiesValue`
- `OpenPositionsProfitLoss`, `DailyProfitLoss`
- `RequestID`, `MessageNumber`, `TotalNumberMessages`

---

### C. ORDER LEDGER & FILL TRACKING (services/dtc_ledger.py)

#### OrderLedgerEntry (dataclass) - Lines 49-71
**Location:** `/home/user/APPV4/services/dtc_ledger.py:49`
**Purpose:** Terminal state summary for one order
**Fields:**
- `server_order_id`: Unique order identifier
- `symbol`, `trade_account`, `side`: "Buy"/"Sell"
- `order_type`: "Market", "Limit", "Stop", "StopLimit"
- `qty`, `price`: Order specifications
- `filled_qty`, `avg_fill_price`: Execution data
- `status`, `reason`: Terminal status and reason
- `exit_kind`: "Stop", "Limit", "Market" (only for fills)
- `high_during_pos`, `low_during_pos`: Position extremes
- `first_time`, `last_time`: Timestamps (Unix seconds)
- `duration_sec`: Order lifetime in seconds
- `text`: Info/error text

#### OrderSnapshot (dataclass) - Lines 74-87
**Location:** `/home/user/APPV4/services/dtc_ledger.py:74`
**Purpose:** Latest state for one order
**Fields:**
- `server_order_id`, `symbol`, `trade_account`
- `side`, `order_type`, `qty`, `price`
- `status`, `reason`, `text`

#### FillEntry (dataclass) - Lines 89-104
**Location:** `/home/user/APPV4/services/dtc_ledger.py:89`
**Purpose:** Single fill event in chronological order
**Fields:**
- `time`: Timestamp (Unix seconds)
- `server_order_id`, `symbol`, `trade_account`
- `side`, `order_type`
- `last_fill_qty`, `last_fill_price`
- `status`, `reason`, `text`

#### OrderLedgerBuilder (class) - Lines 148-369
**Location:** `/home/user/APPV4/services/dtc_ledger.py:148`
**Purpose:** Builds order ledgers from DTC OrderUpdate messages
**Key Methods:**
- `build_ledger()`: Returns list[OrderLedgerEntry] - terminal state summaries
- `build_snapshot()`: Returns list[OrderSnapshot] - latest updates
- `build_fill_stream()`: Returns list[FillEntry] - chronological fills

---

### D. MARKET DATA (services/market_data_service.py)

#### MarketSnapshot (dataclass) - Lines 26-34
**Location:** `/home/user/APPV4/services/market_data_service.py:26`
**Purpose:** Current market conditions snapshot
**Fields:**
- `last_price`: Last trade price (float)
- `session_high`: Session high (float)
- `session_low`: Session low (float)
- `vwap`: Volume-weighted average price (float)
- `cum_delta`: Cumulative delta (float)
- `poc`: Point of control (float)

#### MarketDataService (class) - Lines 37-100+
**Location:** `/home/user/APPV4/services/market_data_service.py:37`
**Purpose:** CSV-based market data feed service
**Key Methods:**
- `read_snapshot()`: Reads current market snapshot from CSV

---

### E. TRADE METRICS & STATISTICS (services/trade_math.py)

#### TradeMath (class) - Lines 8-169
**Location:** `/home/user/APPV4/services/trade_math.py:8`
**Purpose:** Core math utility for trade statistics
**Key Methods:**
- `calculate_r_multiple()`: R-multiple = Realized P&L / Initial Risk
- `calculate_mae_mfe()`: Returns (MAE, MFE) in dollars
  - Long: MAE = entry - trade_min (adverse), MFE = trade_max - entry (favorable)
  - Short: MAE = trade_max - entry (adverse), MFE = entry - trade_min (favorable)
- `realized_pnl()`: Calculate realized P&L in USD
- `drawdown_runup()`: Returns (max_drawdown, max_runup)
- `mfe_mae()`: Returns (MFE, MAE) from price list
- `expectancy()`: (Win% x AvgWin) - (Loss% x AvgLoss)
- `fmt_time_human()`: Format seconds as "20s", "1:20s", etc.

---

## 2. STATE MANAGEMENT

### A. PRIMARY STATE MANAGER (core/state_manager.py, lines 1-503)

#### StateManager (class inherits QtCore.QObject) - Line 16
**Location:** `/home/user/APPV4/core/state_manager.py:16`
**Purpose:** Lightweight app-wide runtime state registry with mode-aware tracking
**Signals Emitted:**
- `balanceChanged(float)`: When balance updates
- `modeChanged(str)`: When mode changes (SIM->LIVE or vice versa)

**Key Attributes:**
- `current_mode`: "SIM", "LIVE", or "DEBUG" (default "SIM")
- `current_account`: Optional[str] - current trading account
- `mode_history`: list[tuple[datetime, str, str]] - (timestamp, mode, account)
- `sim_balance`: float = 10000.0 - SIM mode starting balance
- `sim_balance_start_of_month`: float - track starting balance for reset
- `live_balance`: float = 0.0 - LIVE mode balance

**Position Tracking (MODE-AWARE):**
- `position_symbol`: Optional[str]
- `position_qty`: float (positive=long, negative=short)
- `position_entry_price`: float
- `position_entry_time`: Optional[datetime]
- `position_side`: "LONG" or "SHORT"
- `position_mode`: "SIM" or "LIVE" - what mode this position is in

**Entry/Exit Snapshots:**
- `entry_vwap`, `entry_cum_delta`: Entry market snapshot
- `exit_vwap`, `exit_cum_delta`: Exit market snapshot
- `entry_poc`: Point of control at entry

**Core Methods:**
- `load_sim_balance_from_trades()`: Restore SIM balance from DB (sum of realized P&L)
- `set()`, `get()`, `delete()`, `clear()`: Generic state access
- `update_balance()`: Record current account balance
- `update_position()`: Record or remove a position
- `record_order()`: Record order event for statistics
- `get_balance_for_mode(mode)`: Get balance for specific mode
- `set_balance_for_mode(mode, balance)`: Update mode-specific balance
- `reset_sim_balance_to_10k()`: Reset SIM to $10K
- `adjust_sim_balance_by_pnl()`: Adjust SIM by realized P&L
- `detect_and_set_mode(account)`: Detect mode from account string
- `has_active_position()`: Check if ANY position open
- `get_open_trade_mode()`: Returns mode of open trade (SIM/LIVE/None)
- `is_mode_blocked(requested_mode)`: Check if mode switch is blocked
- `open_position()`: Open new position in mode
- `close_position()`: Close position and return trade record
- `handle_mode_switch()`: Handle switching modes with rules

---

### B. GLOBAL STATE ACCESSOR (core/app_state.py)

**Location:** `/home/user/APPV4/core/app_state.py`
**Purpose:** Singleton accessor for StateManager
**Key Functions:**
- `get_state_manager()`: Get global StateManager instance
- `set_state_manager(state)`: Set global StateManager (called once during init)
- `reset_state_manager()`: Reset global instance (testing/restart)

---

### C. SIM BALANCE MANAGER (core/sim_balance.py, lines 23-235)

#### SimBalanceManager (class) - Line 23
**Location:** `/home/user/APPV4/core/sim_balance.py:23`
**Purpose:** Manages simulated account balances with account-scoped storage
**Key Attributes:**
- `_balances`: dict[str, float] - in-memory account balances
- `_initialized_accounts`: set[str] - accounts that have been initialized
- `SIM_STARTING_BALANCE`: 10000.00 - default starting balance

**Key Methods:**
- `get_balance(account)`: Get current SIM balance (lazy load from disk)
- `set_balance(account, balance)`: Set and persist balance
- `adjust_balance(account, delta)`: Adjust by amount
- `reset_balance(account)`: Reset to starting balance
- `get_all_accounts()`: Get list of SIM accounts

**Persistence:**
- Account-scoped JSON files: `data/sim_balance_{account_safe}.json`
- Format: `{"account": str, "balance": float, "last_updated_utc": ISO8601}`

---

## 3. DATA FLOW & PERSISTENCE

### A. DATABASE ENGINE (data/db_engine.py)

**Location:** `/home/user/APPV4/data/db_engine.py`
**Purpose:** SQLAlchemy engine setup, migrations, session management

**Key Functions:**
- `init_db()`: Create all tables from SQLModel metadata
- `get_session()`: Context-managed session provider (auto-rollback on error)
- `health_check()`: Lightweight DB connectivity probe

**Database Configuration (config/settings.py):**
- Priority chain: explicit DB_URL -> POSTGRES_DSN -> SQLite local
- Default: SQLite at `data/appsierra.db`
- Fallback: In-memory SQLite if all else fails

---

### B. TRADE MANAGEMENT SERVICE (services/trade_service.py)

#### TradeManager (class) - Lines 25-325
**Location:** `/home/user/APPV4/services/trade_service.py:25`
**Purpose:** Unified trade management (logging, storage, analysis)

**Key Attributes:**
- `_open_positions`: dict[str, dict] - symbol -> position info
- `_account`: str - current trading account
- `_db_write_lock`: threading.Lock - serialize DB writes (CRITICAL for race conditions)

**Key Methods:**
- `set_account(account)`: Set current trading account
- `on_position_update(payload)`: Handle Type 306 position updates
  - Logs opens when qty goes from 0->N
  - Logs closes when qty goes from N->0
- `on_order_fill(payload)`: Handle Type 307 order fills
- `record_closed_trade()`: Save closed trade to database
  - Accepts: symbol, pos_info, exit_price, realized_pnl, commissions, r_multiple, mae, mfe, efficiency, mode, entry_vwap, entry_cum_delta, exit_vwap, exit_cum_delta
  - Updates state manager balance
  - Invalidates stats cache on new trade
  - Thread-safe database writes

---

### C. TRADE LOGGING SERVICE (services/trade_logger.py)

#### TradeLogger (class) - Lines 19-143
**Location:** `/home/user/APPV4/services/trade_logger.py:19`
**Purpose:** Capture and log position opens/closes to database

**Similar to TradeManager but simpler:**
- `_open_positions`: dict[str, dict]
- `on_position_update()`: Track opens and closes
- `on_order_fill()`: Log fills
- `_log_trade_to_db()`: Save to database

---

### D. STATISTICS SERVICE (services/stats_service.py)

**Location:** `/home/user/APPV4/services/stats_service.py`
**Purpose:** Panel 3 trading statistics calculator

**Key Function:**
- `compute_trading_stats_for_timeframe(tf, mode)`: Calculate comprehensive metrics
  - Input: Timeframe ("1D", "1W", "1M", "3M", "YTD"), optional mode filter
  - Returns: Dict with metrics
    - Total PnL
    - Max Drawdown, Max Run-Up
    - Expectancy
    - Avg Time, Trade Count
    - Best/Worst trades
    - Hit Rate (win %)
    - Commissions sum
    - Average R
    - Profit Factor
    - Max Streak (consecutive wins/losses)
    - Average MAE/MFE

**Caching:**
- 5-second TTL cache with key: `(timeframe, mode)`
- `invalidate_stats_cache()`: Clear on new trade

---

### E. PERSISTENCE UTILITIES (core/persistence.py)

**Location:** `/home/user/APPV4/core/persistence.py`
**Purpose:** JSONL and cache helpers

**Key Functions:**
- `ensure_cache_dir()`: Ensure ~/.sierra_pnl_monitor exists
- `read_jsonl(path)`: Read line-delimited JSON
- `append_jsonl(path, obj)`: Append line to JSONL
- `append_cache(key, value)`: Append to key-value cache
- `read_cache_between(key, t_start, t_end)`: Query cached data by timestamp range

---

## 4. MESSAGE ROUTING & DATA BRIDGE

### A. MESSAGE ROUTER (core/message_router.py)

#### MessageRouter (class) - Lines 29-800+
**Location:** `/home/user/APPV4/core/message_router.py:29`
**Purpose:** Central dispatcher for normalized DTC AppMessages

**Key Attributes:**
- `state`: StateManager reference
- `_dtc_client`: DTC client reference
- `panel_balance`, `panel_live`, `panel_stats`: UI panels
- `_trade_manager`: TradeManager instance
- `_handlers`: dict mapping event types to handlers
- `_current_mode`, `_current_account`: Mode drift tracking
- `_ui_refresh_pending`, `_ui_refresh_timer`: Coalesced UI updates (10Hz)

**Key Methods:**
- `_check_mode_drift()`: Detect if incoming account disagrees with active mode
- `_on_trade_account()`: Handle Type 401 (TradeAccountResponse)
- `_on_balance_update()`: Handle Type 600 (AccountBalanceUpdate)
- `_on_position_update()`: Handle Type 306 (PositionUpdate)
- `_on_order_update()`: Handle Type 301 (OrderUpdate)
- `_on_market_trade()`: Handle Type 107 (MarketDataUpdateTrade)
- `_on_market_bidask()`: Handle Type 108 (MarketDataUpdateBidAsk)

---

### B. DATA BRIDGE (core/data_bridge.py)

#### AppMessage (Pydantic BaseModel) - Lines 50-55
**Location:** `/home/user/APPV4/core/data_bridge.py:50`
**Purpose:** App-internal normalized envelope
**Fields:**
- `type`: Event type (TRADE_ACCOUNT | BALANCE_UPDATE | POSITION_UPDATE | ORDER_UPDATE)
- `payload`: dict with normalized data

**Normalization Functions:**
- `_normalize_trade_account()`: Extract account
- `_normalize_balance()`: Pick best balance field
- `_normalize_position()`: Normalize symbol, qty, avg_entry
- `_normalize_order()`: (shown in data_bridge.py)

---

## 5. CONFIGURATION & SETTINGS

### A. MAIN SETTINGS (config/settings.py)

**Location:** `/home/user/APPV4/config/settings.py`
**Key Configuration Variables:**
- `HOME`: User home directory
- `CACHE_DIR`: ~/.sierra_pnl_monitor
- `LOG_DIR`: Desktop/APPSIERRA/logs
- `DEBUG_MODE`, `DEBUG_DTC`, `DEBUG_CORE`, `DEBUG_UI`, `DEBUG_DATA`, `DEBUG_NETWORK`, `DEBUG_ANALYTICS`, `DEBUG_PERF`: Feature flags
- `TRADING_MODE`: "SIM", "LIVE", or "DEBUG"
- `DTC_HOST`: 127.0.0.1 (default)
- `DTC_PORT`: 11099 (default)
- `LIVE_ACCOUNT`: "120005" (default)
- `SYMBOL_BASE`: "ES" (default)
- `DB_URL`: Database connection string (with fallback chain)
- `POSTGRES_DSN`: PostgreSQL DSN (optional)
- `TF_CONFIGS`: Timeframe configuration dict

**LIVE Trading Arming Gate:**
- `_LIVE_ARMED`: Private flag
- `arm_live_trading()`: Explicitly arm LIVE mode
- `disarm_live_trading(reason)`: Disarm with reason
- `is_live_armed()`: Check if armed

---

### B. TRADING SPECIFICATIONS (config/trading_specs.py)

**Location:** `/home/user/APPV4/config/trading_specs.py`
**Key Configurations:**
- `PANEL2_METRICS`: ["Price", "Heat", "Time", "Target", "Stop", "Qty", "Avg", "MAE", "MFE", "R", "VWAP", "POC", "Delta", "ATR", "Notes"]
- `PANEL3_METRICS`: ["Total PnL", "Max Drawdown", "Max Run-Up", "Expectancy", "Avg Time", "Trades", "Best", "Worst", "Hit Rate", "Commissions", "Avg R", "Profit Factor", "Streak", "MAE", "MFE"]
- `SPEC_OVERRIDES`: Futures specs by symbol (ES, MES, NQ, MNQ, YM, MYM)
  - Each: {"tick": 0.25, "pt_value": 50.0, "rt_fee": 4.50}
- Helper functions:
  - `match_spec(symbol)`: Get spec for symbol
  - `point_value_for(symbol)`: Get point value
  - `tick_size_for(symbol)`: Get tick size

---

## 6. DTC PROTOCOL CONSTANTS & UTILITIES

### A. DTC CONSTANTS (services/dtc_constants.py)

**Location:** `/home/user/APPV4/services/dtc_constants.py`
**Key Message Types:**
- Core: LOGON_REQUEST=1, LOGON_RESPONSE=2, HEARTBEAT=3, LOGOFF=4, ENCODING_REQUEST=5, ENCODING_RESPONSE=6
- Market Data: MARKET_DATA_REQUEST=101, MARKET_DATA_SNAPSHOT=104, MARKET_DATA_UPDATE_TRADE=107, MARKET_DATA_UPDATE_BID_ASK=108
- Orders: SUBMIT_NEW_SINGLE_ORDER=300, ORDER_UPDATE=301, ORDER_CANCEL_REQUEST=302, HISTORICAL_ORDER_FILL_RESPONSE=304, OPEN_ORDERS_REQUEST=305, POSITION_UPDATE=306, ORDER_FILL_RESPONSE=307
- Accounts: TRADE_ACCOUNTS_REQUEST=400, TRADE_ACCOUNT_RESPONSE=401, CURRENT_POSITIONS_REQUEST=500, ACCOUNT_BALANCE_REQUEST=601, ACCOUNT_BALANCE_UPDATE=600
- Historical: HISTORICAL_PRICE_DATA_REQUEST=700, HISTORICAL_PRICE_DATA_RESPONSE_HEADER=701, HISTORICAL_PRICE_DATA_RECORD_RESPONSE=702

**Enum Constants:**
- `BuySellEnum`: BUY=1, SELL=2
- `OrderTypeEnum`: MARKET=1, LIMIT=2, STOP=3, STOP_LIMIT=4, MARKET_IF_TOUCHED=5
- `OrderStatusEnum`: 0=UNSPECIFIED, 1=NEW, 2=SUBMITTED, 3=PENDING_CANCEL, 4=OPEN, 5=PENDING_REPLACE, 6=CANCELED, 7=FILLED, 8=REJECTED, 9=PARTIALLY_FILLED
- `OrderUpdateReasonEnum`: 0=UNKNOWN, 1=NEW_ORDER_ACCEPTED, 2=GENERAL_UPDATE, 3=ORDER_FILLED, 4=ORDER_FILLED_PARTIALLY, 5=ORDER_CANCELED, 6=ORDER_CANCEL_REPLACE_COMPLETE, 7=NEW_ORDER_REJECTED, 8=ORDER_CANCEL_REJECTED, 9=ORDER_CANCEL_REPLACE_REJECTED
- `PositionUpdateReasonEnum`: 0=UNSOLICITED, 1=CURRENT_POSITIONS_REQUEST_RESPONSE, 2=POSITIONS_REQUEST_RESPONSE
- `TRADE_MODE_LIVE=1`, `TRADE_MODE_SIMULATED=2`

---

## 7. KEY RELATIONSHIPS & DATA FLOW

### Position/Trade Lifecycle:

1. **Position Open:**
   - DTC Type 306 (PositionUpdate) arrives with qty > 0
   - StateManager.open_position() stores: symbol, qty, entry_price, entry_time, mode
   - TradeManager.on_position_update() logs position open
   - Entry snapshots captured (VWAP, delta, POC)

2. **Position Update:**
   - Additional Type 301 (OrderUpdate) messages track fills
   - OrderLedgerBuilder processes order updates
   - High/Low during position tracked

3. **Position Close:**
   - Type 306 arrives with qty = 0
   - StateManager.close_position() returns trade record
   - TradeManager.record_closed_trade() saves to DB:
     - Calculates or uses provided: realized_pnl, commissions, r_multiple, mae, mfe, efficiency
     - Updates StateManager balance (mode-specific)
     - Invalidates stats cache
   - TradeRecord persisted with full details

4. **Statistics Calculation:**
   - stats_service queries TradeRecord filtered by (timeframe, mode)
   - Calculates: PnL, drawdown, expectancy, win rate, MAE/MFE, streaks
   - Results cached for 5 seconds
   - Cache invalidated on new trade

### Mode Detection & Switching:

1. **Mode Detection:**
   - From DTC TradeAccount field (account string)
   - Detection logic: (would be in utils/trade_mode.py - not yet implemented)
   - Account patterns: "Sim*" -> SIM, "120005" (LIVE_ACCOUNT) -> LIVE

2. **Mode Tracking:**
   - StateManager.current_mode: Active mode for new trades
   - StateManager.position_mode: Mode of currently open trade
   - StateManager.mode_history: List of mode changes with timestamps
   - Prevents simultaneous SIM/LIVE positions

3. **Mode Switching Rules:**
   - SIM -> LIVE: Closes SIM position automatically
   - LIVE -> SIM: Blocked if LIVE position open (prevents accidental closure)

### Balance Tracking:

**SIM Mode:**
- Starting balance: $10,000
- Persistence: Ledger-based (start + sum(realized_pnl) from DB)
- Account-scoped storage: sim_balance_{account}.json
- Restored on app startup via load_sim_balance_from_trades()

**LIVE Mode:**
- From DTC Type 600 (AccountBalanceUpdate)
- Real-time updates from broker
- No persistence (always live from DTC)

---

## 8. CRITICAL FIXES & INVARIANTS

1. **Thread Safety:** `TradeManager._db_write_lock` serializes all DB writes
2. **Single SIM/LIVE Position:** Only ONE open trade at a time
3. **Mode-Scoped Data:** Trades, positions, balances all segregated by mode
4. **Composite Indexes:** TradeRecord has indexes on (mode, exit_time) and (is_closed, mode) for efficient mode filtering
5. **Caching:** Stats results cached with 5-second TTL, invalidated on new trades
6. **Field Aliases:** DTC messages support multiple field names (handled by helper methods)
7. **Timestamp Format:** Unix epoch seconds (can be converted to datetime with `datetime.fromtimestamp()`)

---

## 9. FILE LOCATIONS SUMMARY

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| TradeRecord, OrderRecord, AccountBalance | `data/schema.py` | 19-109 | Core trading data models |
| DTC Schemas | `services/dtc_schemas.py` | 1-467 | Pydantic models for DTC messages |
| StateManager | `core/state_manager.py` | 16-503 | Central state registry, mode tracking |
| TradeManager | `services/trade_service.py` | 25-325 | Unified trade logging & storage |
| OrderLedgerBuilder | `services/dtc_ledger.py` | 148-369 | Order ledger construction |
| Stats Service | `services/stats_service.py` | 49-200+ | Panel 3 statistics calculation |
| MessageRouter | `core/message_router.py` | 29-800+ | DTC message dispatcher |
| MarketDataService | `services/market_data_service.py` | 37-100+ | CSV market data feed |
| SimBalanceManager | `core/sim_balance.py` | 23-235 | SIM account balance tracking |
| Settings | `config/settings.py` | 1-382 | Global configuration |
| Trading Specs | `config/trading_specs.py` | 1-105 | Futures specs and metrics |
| DTC Constants | `services/dtc_constants.py` | 1-150+ | Protocol message types |

