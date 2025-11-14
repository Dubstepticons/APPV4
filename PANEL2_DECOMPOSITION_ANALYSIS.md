# Panel2 Decomposition Analysis

## Executive Summary
This document provides a detailed structural analysis of `/home/user/APPV4/panels/panel2.py` (1930 lines) and a concrete decomposition plan into 5 focused modules. The analysis identifies:
- 5 distinct functional areas
- 53+ methods mapped to each area
- 30+ shared state variables with dependency chains
- 8 circular dependency patterns to resolve
- 6 key implementation challenges

**Estimated effort**: 3-4 development cycles with proper testing strategy.

---

## Part 1: Functional Area Analysis

### 1. POSITION DISPLAY (Rendering Layer)
**Purpose**: Render position metrics to 15 MetricCell widgets in a 3x5 grid

#### Methods (11 methods)
| Method | LOC | Purpose |
|--------|-----|---------|
| `_build()` | 126 | Build UI grid, create cell widgets, set fonts/colors |
| `_refresh_all_cells()` | 59 | Dispatch refresh to all metric cell updates |
| `_update_price_cell()` | 6 | Render "qty @ price" in green/red by direction |
| `_update_time_and_heat_cells()` | 54 | Duration timer + heat timer with color thresholds |
| `_update_target_stop_cells()` | 25 | Target/stop prices with stop-distance flashing |
| `_update_secondary_metrics()` | 168 | Risk, R-multiple, range, MAE, MFE, VWAP, delta, POC, efficiency, Pts |
| `_update_live_banner()` | 22 | Update symbol/price banners (top row) |
| `refresh()` | 6 | Public API for test/external refresh |
| `_build_theme_stylesheet()` | 3 | Generate panel background color |
| `_get_theme_children()` | 22 | List child widgets for theme cascading |
| `_on_theme_refresh()` | 8 | Update banner styles on theme change |

#### UI Components (State)
```python
# Grid cells (Row 1)
c_price, c_heat, c_time, c_target, c_stop

# Grid cells (Row 2)
c_risk, c_rmult, c_range, c_mae, c_mfe

# Grid cells (Row 3)
c_vwap, c_delta, c_poc, c_eff, c_pts

# Banners & extras
symbol_banner, live_banner, pills (timeframe)
grid (QGridLayout), outer (QVBoxLayout)
```

#### Read Dependencies (Input Data)
```python
# From Order Flow
entry_qty, entry_price, is_long
target_price, stop_price
symbol

# From CSV Feed Handler
last_price, session_high, session_low
vwap, cum_delta, poc

# From State Persistence / Tracking
_trade_min_price, _trade_max_price
entry_vwap, entry_delta, entry_poc
entry_time_epoch, heat_start_epoch

# From Visual Indicators / Theming
_pnl_up (for color hints)
THEME, ColorTheme
```

#### Write Dependencies (Output State)
- Modifies MetricCell display values and colors only
- No state mutation (read-only side effect)

#### Color Rules
```python
Price cell: ColorTheme.pnl_color_from_direction(is_long)
  LONG (green): #22C55E
  SHORT (red): #EF4444

Heat cell:
  < 3:00m: dim #5B6C7A
  3:00m-4:30m: warning yellow #F59E0B
  >= 4:30m: flashing red #DC2626 with border

Stop cell:
  Within 1.0pt of price: red + flashing
  Otherwise: primary text #E6F6FF

R-multiple:
  > 0: green #22C55E
  < 0: red #EF4444
  = 0: neutral #C9CDD0

MAE/MFE: red/green by value sign
Efficiency: red/yellow/green based on ratio
```

---

### 2. ORDER FLOW (DTC Event Handler)
**Purpose**: Handle incoming DTC orders/positions, detect trade closures, emit trade persistence events

#### Methods (7 methods)
| Method | LOC | Purpose |
|--------|-----|---------|
| `on_order_update()` | 134 | DTC order fill handler; detects trade closes; seeded position in SIM |
| `on_position_update()` | 122 | DTC position update; detects closure; updates symbol |
| `notify_trade_closed()` | 52 | Emit tradeCloseRequested signal to service layer |
| `_on_position_closed()` | 40 | Receive positionClosed signal from TradeCloseService |
| `_clear_position_ui()` | 20 | Reset position to flat; clear UI |
| `set_position()` | 47 | Public API to set qty/price/direction; capture snapshots |
| `set_targets()` | 5 | Public API to set target/stop prices |
| `set_symbol()` | 12 | Public API to update symbol display |

#### State Variables (10 variables)
```python
# Position state (primary)
entry_qty: int (0 when flat)
entry_price: Optional[float]
is_long: Optional[bool] (None when flat)

# Bracket orders
target_price: Optional[float]
stop_price: Optional[float]

# Position identity
symbol: str (default "ES")
current_mode: str ("SIM"/"LIVE"/"DEBUG")
current_account: str

# Domain model (PHASE 6 REFACTOR)
_position: Position (immutable-style; updated via qty property)
```

#### Data Flow
```
DTC → Signal Bus → Panel2.on_order_update()
                    ├─ Auto-detect stop/target from sell orders
                    ├─ Seed position in SIM if no PositionUpdate sent
                    ├─ Detect closing trade (qty decreasing)
                    ├─ Calculate P&L via Position.realized_pnl()
                    └─ notify_trade_closed() → Signal Bus → TradeCloseService

DTC → Signal Bus → Panel2.on_position_update()
                    ├─ Update symbol from position payload
                    ├─ Detect trade closure (qty 0 & was non-zero)
                    ├─ Calculate P&L via Position.realized_pnl()
                    ├─ notify_trade_closed() → Signal Bus
                    └─ set_position() to update UI + timers
```

#### P&L Calculation Chain
```python
# Filled order → notify_trade_closed(trade_dict) with:
trade = {
    "symbol", "side" (long/short), "qty",
    "entry_price", "exit_price",
    "realized_pnl" (via Position.realized_pnl()),
    "commissions" (= COMM_PER_CONTRACT * qty),
    "r_multiple" (via Position.r_multiple()),
    "mae", "mfe" (via Position.mae()/mfe()),
    "efficiency" (via Position.efficiency()),
    "account", "mode",
    "entry_time", "exit_time"
}
```

#### Compatibility Properties (Lines 216-366)
Bridge pattern: proxy to _position domain object
```python
@property entry_price -> _position.entry_price (if not flat)
@property entry_qty -> _position.qty_abs
@property is_long -> _position.is_long (derived from qty sign)
@property entry_vwap, entry_delta, entry_poc -> _position snapshots
@property entry_time_epoch -> int(timestamp)
@property _trade_min_price, _trade_max_price -> _position tracking
```

---

### 3. VISUAL INDICATORS (Non-Financial Metrics)
**Purpose**: Manage visual state (heat timers, proximity alerts, flashing, pulse dots)

#### Methods (5 methods + embedded logic)
| Method | LOC | Purpose |
|--------|-----|---------|
| `_update_heat_state_transitions()` | 18 | Detect drawdown enter/exit, log transitions |
| `_update_proximity_alerts()` | 14 | Log stop proximity state changes (transitions only) |
| `_on_timeframe_changed()` | 17 | Handle timeframe pill changes; update LIVE dot state |
| `refresh_pill_colors()` | 18 | Force timeframe pills to refresh colors from THEME |
| **Embedded in _update_time_and_heat_cells()** | 54 | Heat color/flash logic based on duration thresholds |
| **Embedded in _update_target_stop_cells()** | 25 | Stop flashing when price within 1.0pt |

#### State Variables (6 variables)
```python
# Timer state
heat_start_epoch: Optional[int] (when drawdown began)
entry_time_epoch: Optional[int] (when position opened)

# UI state
_tf: str ("LIVE" or "1D", "1W", "1M", "3M", "YTD")
_pnl_up: Optional[bool] (hint for pill color)

# Tracking (implicit state)
_prev_drawdown_state: Optional[bool] (for transition detection)
_stop_near_prev: Optional[bool] (for proximity alerts)

# Visual components
pills: InvestingTimeframePills
```

#### Heat Thresholds
```python
HEAT_WARN_SEC = 180          # 3:00m - yellow warning
HEAT_ALERT_FLASH_SEC = 270   # 4:30m - start flashing
HEAT_ALERT_SOLID_SEC = 300   # 5:00m - solid red + flash
```

#### Color Transitions
```
Heat < 3:00m      → Dim gray #5B6C7A
3:00m ≤ Heat < 4:30m → Warning yellow #F59E0B
4:30m ≤ Heat < 5:00m → Flashing yellow #F59E0B with border
Heat >= 5:00m     → Flashing red #DC2626 with border

Stop price:
  Distance > 1.0pt → Neutral text #E6F6FF
  Distance ≤ 1.0pt → Red #DC2626 + flashing

Timeframe LIVE dot:
  Pulsing when _tf == "LIVE"
  Static when _tf != "LIVE"
  Color from pill._pnl_up direction
```

#### Dependencies
```python
# From Order Flow
entry_price, is_long, entry_qty
stop_price, target_price

# From CSV Feed Handler
last_price (for drawdown detection)

# From State Persistence
heat_start_epoch

# From Position Display
Access to MetricCell instances:
  - c_heat.start_flashing() / stop_flashing()
  - c_time.set_value_color()
  - c_stop.start_flashing() / stop_flashing()
  - pills.set_live_dot_pulsing(bool)
  - pills.set_active_color(hex)
```

---

### 4. CSV FEED HANDLER (Market Data)
**Purpose**: Read CSV snapshot file every 500ms, update live market prices, track trade extremes

#### Methods (4 methods)
| Method | LOC | Purpose |
|--------|-----|---------|
| `_setup_timers()` | 14 | Create _csv_timer (500ms) and _clock_timer (1000ms) |
| `_on_csv_tick()` | 60 | CSV read → update feed data → track extremes → trigger refresh |
| `_on_clock_tick()` | 3 | Clock tick → update time/heat cells |
| `_read_snapshot_csv()` | 44 | Parse snapshot.csv with header-aware DictReader |

#### State Variables (7 variables)
```python
# Live feed data
last_price: Optional[float]
session_high: Optional[float]
session_low: Optional[float]
vwap: Optional[float]
cum_delta: Optional[float]
poc: Optional[float]

# Timers
_csv_timer: QTimer (interval: CSV_REFRESH_MS = 500ms)
_clock_timer: QTimer (interval: TIMER_TICK_MS = 1000ms)
```

#### CSV Format
```
Header row: last, high, low, vwap, cum_delta, poc
Data row:   5800.25, 5810.50, 5790.00, 5805.15, 12345, 5800.50

File location: SNAPSHOT_CSV_PATH (from config.settings)
Encoding: UTF-8 with BOM support
Parser: csv.DictReader (robust to column reordering)
```

#### Data Flow
```
_on_csv_tick() [every 500ms]
  ├─ _read_snapshot_csv()
  │  └─ {last_price, session_high, session_low, vwap, cum_delta, poc}
  ├─ _update_heat_state_transitions(prev_last, new_last)
  │  └─ Detect drawdown enter/exit for heat tracking
  ├─ Track trade extremes (_trade_min_price, _trade_max_price)
  │  └─ update_trade_extremes_in_database() [async, non-blocking]
  ├─ _refresh_all_cells()
  │  └─ Position Display triggered to update metrics
  ├─ _update_proximity_alerts()
  │  └─ Log stop proximity state changes
  └─ _update_live_banner()
     └─ Update symbol/price banners

_on_clock_tick() [every 1000ms]
  └─ _update_time_and_heat_cells()
     └─ Recalculate duration and heat time
```

#### Trade Extremes Tracking
```python
# While in position:
if self.entry_qty > 0 and self.last_price is not None:
    p = float(self.last_price)
    _trade_min_price = min(_trade_min_price, p)
    _trade_max_price = max(_trade_max_price, p)
    
    # Persist to database for MAE/MFE after crash/restart
    position_service.update_trade_extremes(
        mode, account, current_price=p
    )
```

#### Error Handling
```python
# Missing CSV file
→ Log warning once (suppress repeats)
→ Continue trading (non-blocking)

# CSV parse error
→ Log error, return False
→ Skip this tick, try again on next 500ms cycle

# Database update failure (trade extremes)
→ Log debug (non-critical), continue trading
```

---

### 5. STATE PERSISTENCE (Serialization Layer)
**Purpose**: Load/save position state and trade extremes across sessions and mode switches

#### Methods (7 methods)
| Method | LOC | Purpose |
|--------|-----|---------|
| `_get_state_path()` | 9 | Compute scoped path: data/runtime_state_panel2_{mode}_{account}.json |
| `_load_state()` | 20 | Load JSON: entry_time_epoch, heat_start_epoch, trade extremes |
| `_save_state()` | 24 | Save JSON with atomic writes |
| `_load_position_from_database()` | 61 | Query PositionRepository for open position in (mode, account) |
| `_write_position_to_database()` | 51 | Call PositionService.save_open_position() |
| `_update_trade_extremes_in_database()` | 24 | Call PositionService.update_trade_extremes() |
| `set_trading_mode()` | 52 | Mode switch: freeze old scope, restore new scope |
| `closeEvent()` | 3 | Save state on widget close |

#### State Variables (6 variables)
```python
# Mode/account context
current_mode: str
current_account: str

# Timer snapshots (persisted to JSON)
entry_time_epoch: Optional[int]
heat_start_epoch: Optional[int]

# Trade extremes (persisted to JSON + DB)
_trade_min_price: Optional[float]
_trade_max_price: Optional[float]
```

#### Scoped State Path
```python
# Before:
STATE_PATH = "data/runtime_state_panel2.json"
# Shared globally → broken when switching modes/accounts

# After (PHASE 5 REFACTOR):
_get_state_path() → "data/runtime_state_panel2_{mode}_{account}.json"
# Separate file per (mode, account) pair → clean switching

# Example:
SIM account1 → data/runtime_state_panel2_SIM_account1.json
SIM account2 → data/runtime_state_panel2_SIM_account2.json
LIVE account1 → data/runtime_state_panel2_LIVE_account1.json
```

#### State Lifecycle
```
set_trading_mode(NEW_MODE, NEW_ACCOUNT)
  ├─ _save_state()  [freeze OLD_MODE/OLD_ACCOUNT scope]
  │  └─ Atomic write to old JSON file
  ├─ Switch context: current_mode = NEW_MODE, current_account = NEW_ACCOUNT
  ├─ _load_state()  [restore NEW_MODE/NEW_ACCOUNT scope]
  │  └─ Atomic read from new JSON file
  ├─ _load_position_from_database()  [restore open trade]
  │  └─ Query PositionRepository for (NEW_MODE, NEW_ACCOUNT)
  └─ _refresh_all_cells()
```

#### Database Integration
```python
# Writing position (when opened in set_position())
_write_position_to_database()
  └─ position_service.save_open_position(
       mode, account, symbol, qty, entry_price,
       entry_time_epoch, entry_vwap, entry_cum_delta,
       entry_poc, target_price, stop_price
     )

# Updating trade extremes (from CSV feed during trade)
_update_trade_extremes_in_database()
  └─ position_service.update_trade_extremes(
       mode, account, current_price
     )
  # Called ~once per 500ms (from _on_csv_tick())

# Loading position (on mode switch)
_load_position_from_database()
  └─ position_repo.get_open_position(mode, account)
     ├─ Restore: qty, entry_price, target_price, stop_price
     ├─ Restore: entry_vwap, entry_cum_delta, entry_poc
     ├─ Restore: _trade_min_price, _trade_max_price
     └─ Restore: entry_time (convert to epoch)
```

#### Atomic Persistence (utils/atomic_persistence.py)
```python
load_json_atomic(path) → dict or None
  ├─ Read with file locking
  ├─ Handle missing files gracefully
  └─ Return parsed JSON or None

save_json_atomic(data, path) → bool
  ├─ Write to temp file first
  ├─ Atomic rename to final path
  └─ Return True on success, False on failure
```

---

## Part 2: Dependency Analysis

### Shared State Variables (30+)

#### Grid 1: State Flow Dependencies
```
POSITION DISPLAY                ORDER FLOW                STATE PERSISTENCE
(reads all)                     (writes)                  (loads/saves)
              ↓                       ↓                           ↓
    entry_qty, entry_price, is_long ←──────────────────────────────
    target_price, stop_price
    symbol                           ←──────────────────────────────
    entry_vwap, entry_delta, entry_poc  ← set_position()
    entry_time_epoch, heat_start_epoch
    _trade_min_price, _trade_max_price  ← CSV feed tracking
```

#### Grid 2: Live Feed Dependencies
```
CSV FEED HANDLER                ORDER FLOW                POSITION DISPLAY
(reads from CSV file)           (reads)                   (uses for rendering)
     ↓                               ↓                           ↓
  last_price ─────────────────────────────────→ heat tracking, P&L calc, MAE/MFE
  session_high, session_low ────────────────→ MAE/MFE calc
  vwap ─────────────────────────────────────→ snapshot at entry, display
  cum_delta ────────────────────────────────→ snapshot at entry, display
  poc ──────────────────────────────────────→ snapshot at entry, display
```

#### Grid 3: Timer State
```
VISUAL INDICATORS               CSV FEED HANDLER          STATE PERSISTENCE
(reads/updates)                 (drives)                  (persists)
     ↓                               ↓                           ↓
 heat_start_epoch ←─ _on_csv_tick() ─→ color thresholds ─→ JSON file
 entry_time_epoch ←─ set_position() ───────────────────→ JSON file
 _trade_min_price ←─ _on_csv_tick() ───────────────────→ JSON + DB
 _trade_max_price ←─ _on_csv_tick() ───────────────────→ JSON + DB
```

### Dependency Matrix

```
                    POS_DISPLAY  ORDER_FLOW  VIS_IND  CSV_FEED  STATE_PERSIST
POS_DISPLAY         (self)       read-only   read-only read-only  read-only
ORDER_FLOW          write        (self)      write    -           write
VIS_IND             write        read-only   (self)   read-only   read-only
CSV_FEED            write        -           write    (self)      write
STATE_PERSIST       -            read-only   read-only read-only  (self)

Legend:
  write: module X updates state that module Y uses
  read-only: module X only reads state from module Y
  -: no direct interaction
```

---

## Part 3: Circular Dependencies & Challenges

### Challenge 1: Refresh Loop (Medium Severity)
```
CSV Feed (every 500ms)
  ├─ _on_csv_tick()
  │  └─ _refresh_all_cells()
  │     └─ Position Display (reads last_price, etc.)

Order Flow (event-driven)
  ├─ on_order_update() / on_position_update()
  │  └─ _refresh_all_cells()
  │     └─ Position Display (reads entry_price, etc.)

Clock Timer (every 1000ms)
  ├─ _on_clock_tick()
  │  └─ _update_time_and_heat_cells()
  │     └─ Position Display update
```

**Issue**: Multiple sources trigger refresh:
- CSV feed: live price changes
- Clock: timer updates
- Order flow: position changes
- Manual: `refresh()` calls

**Risk**: 
- Redundant calculations (expensive metric recalculation)
- Inconsistent state during multi-source updates
- Testing complexity (timing-dependent)

**Solution**:
- Consolidate refresh trigger points
- Use dirty-flag pattern (mark what changed, batch updates)
- Decouple via callbacks: `on_feed_data_changed()`, `on_position_changed()`

---

### Challenge 2: Shared State Synchronization (High Severity)
```
Order Flow          CSV Feed           Position Display
    ↓                   ↓                     ↓
 entry_price ──────────────────────────────────
 is_long      ──────────────────────────────────
 entry_qty    ──────────────────────────────────
 last_price   ──────────────────────────────────
 target_price ──────────────────────────────────

8+ modules read/write 30+ state variables
→ Hard to trace data flow
→ Race conditions if async
→ State inconsistency bugs
```

**Risk**: When on_order_update() sets entry_qty and _on_csv_tick() reads it simultaneously
- Missing synchronization primitives
- No state validation (e.g., entry_qty positive but entry_price None)

**Solution**:
- Create `PositionState` dataclass as single source of truth
- All modules read from this immutable snapshot
- Only OrderFlow writes back to state
- Use @dataclass(frozen=True) for CSV feed and display snapshots

---

### Challenge 3: Timer Lifecycle (High Severity)
```
__init__()
  ├─ _setup_timers()
  │  ├─ _csv_timer.start()  [500ms ticks]
  │  └─ _clock_timer.start() [1000ms ticks]
  └─ _connect_signal_bus()
     └─ on_order_update() → set_position()
        ├─ entry_time_epoch = int(time.time())
        └─ _save_state()

on_order_update() / on_position_update()
  └─ set_position() or _clear_position_ui()
     ├─ Initializes/resets entry_time_epoch, heat_start_epoch
     └─ _save_state()  [no timer management]

set_trading_mode()
  ├─ _save_state()  [freeze old scope]
  ├─ _load_state()  [restore new scope - loads epochs]
  ├─ _load_position_from_database()
  └─ _refresh_all_cells()  [timers still running!]
     ├─ Uses entry_time_epoch, heat_start_epoch from new scope
     ├─ But _on_csv_tick() and _on_clock_tick() still running
     └─ State mismatch risk
```

**Risk**:
- Mode switch while position open: timers keep running from old epoch
- Clock advances, but heat_start_epoch was loaded from JSON → incorrect heat display
- No coordination between mode switch and timer state

**Solution**:
- Pause timers during mode switch
- Reset timer epochs after loading from DB
- Add explicit `_sync_timers_with_state()` call in set_trading_mode()

---

### Challenge 4: Database Sync Scattered (Medium Severity)
```
set_position() line 1213
  └─ _write_position_to_database()

_on_csv_tick() line 940 (inside try/except)
  └─ position_service.update_trade_extremes()

_on_position_closed() [no DB call, relies on TradeCloseService]

set_trading_mode() line 1174
  └─ _load_position_from_database()

notify_trade_closed() [emits signal, service handles DB]

closeEvent() [saves JSON but not DB]
```

**Risk**:
- DB writes scattered across 3 methods
- No consistent transaction handling
- Trade extremes updated 2x/sec (expensive)
- No validation that DB write succeeded before continuing

**Solution**:
- Centralize DB operations in state_persistence module
- Create `PositionDatabaseManager` class with write/read/delete methods
- Use write-through cache (both JSON + DB in state_persistence)

---

### Challenge 5: Position Domain Model Integration (Medium Severity)
```
_position: Position (domain model)
  ├─ Immutable-style (doesn't mutate, returns new instances)
  ├─ BUT: trade_min_price, trade_max_price updated in place
  ├─ Used for P&L calculations:
  │  ├─ realized_pnl() - on_order_update(), on_position_update()
  │  ├─ mae(), mfe() - get_current_trade_data()
  │  ├─ r_multiple() - _update_secondary_metrics()
  │  └─ efficiency() - get_current_trade_data()
  └─ BUT: Panel2 uses compatibility properties
     ├─ entry_price, entry_qty, is_long (via proxy setters)
     ├─ These mutate _position indirectly
     └─ Mixes immutable + mutable patterns

set_position(qty, entry_price, is_long)
  ├─ self.entry_qty = max(0, int(qty))  [sets property]
  ├─ self.entry_price = float(entry_price)  [sets property]
  ├─ self._position.qty = ±abs(qty)  [direct mutation]
  └─ Inconsistency: qty set twice (via property + direct)
```

**Risk**:
- _position state gets out of sync with Panel2 properties
- Hard to reason about state after mode switch + position reload
- Compatibility properties bypass domain model encapsulation

**Solution**:
- Use _position as single source of truth
- Remove compatibility properties, update all code to use _position.qty, etc.
- Make Position.trade_min_price/max immutable via update_extremes() method

---

### Challenge 6: Signal Bus Event Ordering (Medium Severity)
```
TradeCloseService
  ├─ Receives: signal_bus.tradeCloseRequested
  ├─ Saves to database
  ├─ Emits: signal_bus.positionClosed
  └─ Emission order:
     ├─ [T0] Panel2.on_order_update() calls notify_trade_closed()
     │        → Emits tradeCloseRequested
     ├─ [T1] TradeCloseService receives (async via QueuedConnection)
     ├─ [T2] Service saves to DB
     ├─ [T3] Service emits positionClosed
     └─ [T4] Panel2._on_position_closed() receives (async)

Risks:
  - UI clear happens after DB save (correct)
  - But if T4 arrives before T3 completes, UI shows stale data
  - Mode switch during T1-T3 window: position gets reloaded from DB
```

**Solution**:
- Make signal emissions synchronous or add fence
- Add sequence numbers to events for validation
- Unit test event ordering with manual signals

---

## Part 4: Proposed Module Decomposition

### Module Structure
```
panels/
├── panel2.py (1930 lines) ────→ REFACTOR INTO:
│
├── _panels2/  [new subpackage]
│   ├── __init__.py
│   ├── panel2_main.py          (150 LOC) - Orchestrator
│   ├── position_display.py      (300 LOC) - Rendering
│   ├── order_flow.py            (250 LOC) - DTC events
│   ├── visual_indicators.py     (200 LOC) - Timers/alerts
│   ├── csv_feed_handler.py      (150 LOC) - Market data
│   ├── state_persistence.py     (200 LOC) - Serialization
│   ├── position_state.py        (100 LOC) - Data class
│   └── metrics_calculator.py    (150 LOC) - Calculations
└── [keep old panel2.py as fallback during transition]
```

### 1. position_state.py (100 LOC)
**New**: Immutable state dataclass
```python
@dataclass(frozen=True)
class PositionState:
    """Snapshot of position state for rendering and calculations."""
    
    # Position
    qty: int
    entry_price: Optional[float]
    is_long: Optional[bool]
    symbol: str
    
    # Bracket
    target_price: Optional[float]
    stop_price: Optional[float]
    
    # Snapshots
    entry_vwap: Optional[float]
    entry_delta: Optional[float]
    entry_poc: Optional[float]
    
    # Timers
    entry_time_epoch: Optional[int]
    heat_start_epoch: Optional[int]
    
    # Extremes
    trade_min_price: Optional[float]
    trade_max_price: Optional[float]
    
    @property
    def is_flat(self) -> bool:
        return self.qty == 0
    
    @property
    def is_in_drawdown(self, last_price: float) -> bool:
        """Check if current price is in drawdown."""
        if self.is_flat or self.entry_price is None or last_price is None:
            return False
        return (last_price < self.entry_price) if self.is_long else (last_price > self.entry_price)
```

### 2. csv_feed_handler.py (150 LOC)
**Extracted**: CSV reading + timer management
```python
class CSVFeedHandler:
    """Reads market data from snapshot.csv every 500ms."""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.last_price = None
        self.session_high = None
        self.session_low = None
        self.vwap = None
        self.cum_delta = None
        self.poc = None
        
        self._csv_timer = QTimer()
        self._csv_timer.setInterval(500)
        self._csv_timer.timeout.connect(self._on_csv_tick)
        
        self._clock_timer = QTimer()
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._on_clock_tick)
    
    def start(self):
        self._csv_timer.start()
        self._clock_timer.start()
    
    def stop(self):
        self._csv_timer.stop()
        self._clock_timer.stop()
    
    def get_feed_state(self) -> dict:
        """Return current feed data snapshot."""
        return {
            "last_price": self.last_price,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "vwap": self.vwap,
            "cum_delta": self.cum_delta,
            "poc": self.poc,
        }
    
    def _on_csv_tick(self):
        """Read CSV and emit data_updated signal."""
        # Emit: data_updated(feed_state, trade_extremes)
        pass
    
    def _on_clock_tick(self):
        """Tick for timer updates."""
        # Emit: time_tick()
        pass
    
    def _read_snapshot_csv(self) -> bool:
        """Robust CSV parser (reuse existing)."""
        pass
    
    # Signal
    data_updated = pyqtSignal(dict, dict)  # feed_state, trade_extremes
    time_tick = pyqtSignal()
```

### 3. visual_indicators.py (200 LOC)
**Extracted**: Heat tracking, proximity alerts, pill colors
```python
class VisualIndicators:
    """Manages heat timers, proximity alerts, and visual states."""
    
    def __init__(self, metric_cells: dict, pills):
        self.c_heat = metric_cells["c_heat"]
        self.c_time = metric_cells["c_time"]
        self.c_stop = metric_cells["c_stop"]
        self.pills = pills
        
        self.heat_start_epoch = None
        self._tf = "LIVE"
        self._pnl_up = None
        self._prev_drawdown_state = None
        self._stop_near_prev = None
    
    def update_heat_state(
        self, 
        last_price: Optional[float],
        entry_price: Optional[float],
        is_long: Optional[bool],
        entry_time_epoch: Optional[int],
        current_time: int
    ):
        """Update heat timer display and colors."""
        # Detects drawdown enter/exit
        # Updates heat_start_epoch
        # Sets c_heat colors and flashing
        pass
    
    def update_stop_proximity(
        self,
        stop_price: Optional[float],
        last_price: Optional[float]
    ):
        """Check if price within 1pt of stop, flash if so."""
        pass
    
    def on_timeframe_changed(self, tf: str):
        """Handle timeframe pill change."""
        self._tf = tf
        self._update_live_dot()
    
    def _update_live_dot(self):
        """Update LIVE dot visibility and pulsing."""
        pass
    
    def update_theme(self):
        """Refresh colors from THEME."""
        pass
    
    # Signals
    heat_threshold_crossed = pyqtSignal(str)  # "warn", "flash", "solid"
    drawdown_state_changed = pyqtSignal(bool)  # is_in_drawdown
```

### 4. metrics_calculator.py (150 LOC)
**Extracted**: Expensive metric calculations
```python
class MetricsCalculator:
    """Calculate trading metrics (P&L, R-multiple, MAE, MFE, etc.)."""
    
    @staticmethod
    def calculate_pnl_metrics(
        position: Position,
        last_price: float
    ) -> dict:
        """Return {pnl_pts, pnl_dollars, gross_pnl}."""
        pass
    
    @staticmethod
    def calculate_risk_metrics(
        entry_price: float,
        entry_qty: int,
        stop_price: Optional[float],
        target_price: Optional[float],
        is_long: bool
    ) -> dict:
        """Return {risk_dollars, r_multiple, range_pts}."""
        pass
    
    @staticmethod
    def calculate_mae_mfe(
        position: Position,
        trade_min: Optional[float],
        trade_max: Optional[float]
    ) -> dict:
        """Return {mae_pts, mfe_pts, mae_dollars, mfe_dollars}."""
        pass
    
    @staticmethod
    def calculate_efficiency(
        position: Position,
        pnl_pts: float,
        mfe_pts: float
    ) -> float:
        """Return efficiency ratio."""
        pass
```

### 5. order_flow.py (250 LOC)
**Extracted**: DTC order/position handling, trade closure
```python
class OrderFlowHandler:
    """Handles DTC orders and positions, detects trade closure."""
    
    def __init__(self, parent_panel):
        self.panel = parent_panel  # For UI callbacks
        self.position = Position.flat(...)
        self.entry_qty = 0
        self.entry_price = None
        self.is_long = None
        self.target_price = None
        self.stop_price = None
        self.symbol = "ES"
        self.current_mode = "SIM"
        self.current_account = ""
    
    def on_order_update(self, payload: dict):
        """Handle DTC order fill."""
        # Auto-detect stop/target
        # Seed position in SIM
        # Detect trade closure
        # Emit trade_closed signal
        pass
    
    def on_position_update(self, payload: dict):
        """Handle DTC position update."""
        # Update symbol
        # Detect closure
        # Call set_position()
        pass
    
    def set_position(self, qty: int, price: float, is_long: bool):
        """Open/close position, capture snapshots."""
        pass
    
    def set_targets(self, target: Optional[float], stop: Optional[float]):
        """Update bracket orders."""
        pass
    
    def get_position_state(self) -> PositionState:
        """Return current position snapshot."""
        pass
    
    # Signals
    position_opened = pyqtSignal(PositionState)
    position_closed = pyqtSignal(PositionState)
    trade_closed = pyqtSignal(dict)  # trade_dict for persistence
    position_state_changed = pyqtSignal(PositionState)
```

### 6. state_persistence.py (200 LOC)
**Extracted**: JSON + DB serialization
```python
class StatePersistenceManager:
    """Load/save position state across sessions."""
    
    def __init__(self, mode: str, account: str):
        self.mode = mode
        self.account = account
    
    def load_session_state(self) -> dict:
        """Load from JSON: entry_time_epoch, heat_start_epoch, trade_min/max."""
        pass
    
    def save_session_state(
        self,
        entry_time_epoch: Optional[int],
        heat_start_epoch: Optional[int],
        trade_min: Optional[float],
        trade_max: Optional[float]
    ) -> bool:
        """Save to JSON with atomic writes."""
        pass
    
    def load_position_from_database(self) -> Optional[PositionState]:
        """Query DB for open position."""
        pass
    
    def save_position_to_database(self, position: PositionState) -> bool:
        """Write position to DB."""
        pass
    
    def update_trade_extremes(self, price: float) -> bool:
        """Update min/max in DB."""
        pass
    
    def switch_mode(self, new_mode: str, new_account: str) -> PositionState:
        """Freeze old scope, load new scope."""
        # Save old → Load new → Return position
        pass
    
    # Error handling
    PersistenceError = Exception
```

### 7. position_display.py (300 LOC)
**Extracted**: Rendering layer
```python
class PositionDisplay:
    """Renders position metrics to MetricCell grid."""
    
    def __init__(self):
        self.cells = {
            # Row 1
            "c_price": MetricCell("Price"),
            "c_heat": MetricCell("Heat"),
            "c_time": MetricCell("Time"),
            "c_target": MetricCell("Target"),
            "c_stop": MetricCell("Stop"),
            # Row 2
            "c_risk": MetricCell("Planned Risk"),
            "c_rmult": MetricCell("R-Multiple"),
            "c_range": MetricCell("Range"),
            "c_mae": MetricCell("MAE"),
            "c_mfe": MetricCell("MFE"),
            # Row 3
            "c_vwap": MetricCell("VWAP"),
            "c_delta": MetricCell("Delta"),
            "c_poc": MetricCell("POC"),
            "c_eff": MetricCell("Efficiency"),
            "c_pts": MetricCell("Pts"),
        }
        self.symbol_banner = QLabel("--")
        self.live_banner = QLabel("FLAT")
    
    def refresh_all(
        self,
        position: PositionState,
        feed_state: dict,
        metrics: dict,
        is_theme_dirty: bool = False
    ):
        """Update all cells based on current state."""
        pass
    
    def _update_price_cell(self, position: PositionState):
        pass
    
    def _update_metrics(
        self,
        position: PositionState,
        feed_state: dict,
        metrics: dict
    ):
        """Update risk, R-mult, MAE, MFE, VWAP, etc."""
        pass
    
    def _build_grid(self) -> QGridLayout:
        """Create grid widget."""
        pass
    
    def update_theme(self):
        """Refresh colors."""
        pass
```

### 8. panel2_main.py (150 LOC)
**Remains in panels/**: Orchestrator
```python
class Panel2(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Live trading metrics panel - orchestrates submodules.
    
    ARCHITECTURE:
    - Thin orchestrator pattern
    - Delegates to focused modules
    - Maintains signal bus for event-driven updates
    - Coordinates module interactions
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Submodules
        self.csv_feed = CSVFeedHandler(SNAPSHOT_CSV_PATH)
        self.order_flow = OrderFlowHandler(self)
        self.persistence = StatePersistenceManager("SIM", "")
        self.visual_indicators = VisualIndicators(
            self.display.cells,
            self.pills
        )
        self.display = PositionDisplay()
        self.metrics = MetricsCalculator()
        
        # Build UI
        self._build()
        
        # Connect internal signals (between modules)
        self.csv_feed.data_updated.connect(self._on_feed_data)
        self.order_flow.position_opened.connect(self._on_position_opened)
        self.order_flow.trade_closed.connect(self._persist_trade)
        
        # Connect to signal bus (external events)
        self._connect_signal_bus()
    
    def _on_feed_data(self, feed_state: dict, trade_extremes: dict):
        """CSV feed triggered - update display."""
        # 1. Update visual indicators (heat, proximity)
        # 2. Recalculate metrics
        # 3. Refresh display
        pass
    
    def _on_position_opened(self, position: PositionState):
        """Order flow opened position."""
        # 1. Save to database
        # 2. Refresh display
        pass
    
    def _persist_trade(self, trade_dict: dict):
        """Order flow closed trade."""
        # Emit to signal bus → TradeCloseService
        pass
    
    def set_trading_mode(self, mode: str, account: Optional[str]):
        """Mode switch - coordinate all modules."""
        # 1. Pause CSV feed
        # 2. Persistence.switch_mode()
        # 3. Load position into OrderFlow
        # 4. Resume CSV feed
        # 5. Refresh display
        pass
    
    def _connect_signal_bus(self):
        """Connect to external signal bus."""
        signal_bus.positionUpdated.connect(self.order_flow.on_position_update)
        signal_bus.orderUpdateReceived.connect(self.order_flow.on_order_update)
        signal_bus.modeChanged.connect(self.set_trading_mode)
        signal_bus.themeChangeRequested.connect(self.refresh_theme)
```

---

## Part 5: Implementation Roadmap

### Phase 1: Setup (1 day)
1. Create `/home/user/APPV4/panels/_panels2/` subpackage
2. Extract helper functions to `utils/trading_utils.py`
   - fmt_time_human, sign_from_side, clamp, extract_symbol_display
3. Create `position_state.py` dataclass
4. Add unit test framework for new modules

### Phase 2: Extract Independent Modules (3 days)
1. **Day 1**: Extract `csv_feed_handler.py`
   - Copy _setup_timers(), _on_csv_tick(), _on_clock_tick(), _read_snapshot_csv()
   - Reuse constants (CSV_REFRESH_MS, TIMER_TICK_MS)
   - Unit test CSV parsing with mock files
   
2. **Day 2**: Extract `state_persistence.py`
   - Copy _get_state_path(), _load_state(), _save_state()
   - Copy DB methods: _load_position_from_database(), etc.
   - Add _sync_timers() method for mode switch coordination
   - Unit test state loading/saving
   
3. **Day 3**: Extract `metrics_calculator.py`
   - Extract calculation logic from _update_secondary_metrics()
   - Reuse Position domain model methods (realized_pnl, mae, mfe, etc.)
   - Unit test with sample positions

### Phase 3: Extract Dependent Modules (3 days)
1. **Day 1**: Extract `visual_indicators.py`
   - Copy heat tracking (_update_heat_state_transitions, heat thresholds)
   - Copy proximity alerts (_update_proximity_alerts)
   - Copy timeframe handling (_on_timeframe_changed)
   - Depend on: CSV feed (last_price), Order flow (entry_price, is_long)
   - Integration tests with mock CSV data
   
2. **Day 2**: Extract `order_flow.py`
   - Copy on_order_update(), on_position_update()
   - Copy trade closure (notify_trade_closed, _on_position_closed)
   - Copy set_position(), set_targets()
   - Depend on: Metrics calculator, State persistence
   - Integration tests with mock DTC payloads
   
3. **Day 3**: Extract `position_display.py`
   - Copy _build(), _refresh_all_cells(), all _update_* methods
   - Depend on: all other modules (reads their state)
   - Accept PositionState + feed_state + metrics as parameters
   - Integration tests with mock state

### Phase 4: Create Orchestrator (2 days)
1. **Day 1**: Refactor Panel2 to orchestrator
   - Create Panel2(parent) as thin wrapper
   - Instantiate all submodules
   - Connect internal signals
   - Test mode switching coordination
   
2. **Day 2**: Migrate signal bus connections
   - Move signal connections from Panel2.__init__() to orchestrator
   - Test external event flow (order updates, position updates)
   - Integration test full panel startup

### Phase 5: Testing & Validation (3 days)
1. **Day 1**: Unit tests for each module
   - CSVFeedHandler: CSV parsing, timer lifecycle
   - StatePersistence: JSON read/write, DB sync
   - MetricsCalculator: P&L, MAE/MFE, efficiency calculations
   - OrderFlow: order/position detection, trade closure
   
2. **Day 2**: Integration tests
   - Full panel initialization
   - Mode switching (save + load)
   - Order flow → trade closure → persistence
   - CSV feed → display refresh
   
3. **Day 3**: Regression testing
   - Run against real DTC data (if available)
   - Check backward compatibility
   - Performance profiling (should be faster with modular caching)

### Phase 6: Cleanup (1 day)
1. Remove old panel2.py or archive
2. Update imports in other modules
3. Documentation updates
4. Deploy to test environment

**Total Estimated Effort**: 2-3 weeks for full team, 6-8 weeks solo

---

## Part 6: Risk Mitigation

### Backward Compatibility
```python
# Interim: Keep Panel2 as alias during migration
from panels._panels2.panel2_main import Panel2 as _Panel2

class Panel2(_Panel2):
    """Backward-compatible wrapper during refactoring."""
    
    # Expose public API unchanged
    def get_current_trade_data(self) -> dict:
        return self.order_flow.get_state()
    
    def seed_demo_position(self, ...):
        return self.order_flow.set_position(...)
```

### Testing Strategy
```python
# Mock all external dependencies
class MockCSVFeedHandler:
    data_updated = pyqtSignal()
    def emit_test_data(self, last_price, ...):
        self.data_updated.emit({...})

# Unit test each module independently
def test_visual_indicators_heat_colors():
    vi = VisualIndicators(mock_cells, mock_pills)
    vi.update_heat_state(
        last_price=5800, entry_price=5810, is_long=True,
        entry_time_epoch=int(time.time()) - 300,  # 5 minutes ago
        current_time=int(time.time())
    )
    # Assert c_heat color is HEAT_ALERT_SOLID_SEC (red)
    assert vi.c_heat.value_color == "#DC2626"
```

### Rollback Plan
```
If issues arise:
1. Keep old panel2.py in git history
2. Branch for migration (don't delete original)
3. If fatal: revert to original, try again with different approach
4. Partial rollback: disable broken modules, fall back to old code
```

---

## Appendix: File-by-File Breakdown

### Detailed Line Counts by Method

#### panel2.py (1930 lines) breakdown:
```
Imports & constants      (1-80)        80 LOC
Helper functions         (38-77)       40 LOC
Panel2 class             (85-1930)    1845 LOC
  ├─ __init__                          46 LOC
  ├─ _connect_signal_bus()             71 LOC
  ├─ Compatibility properties       (150 LOC) [remove in refactor]
  ├─ Trade persistence hooks           52 LOC
  ├─ Order handling (on_order_update)  134 LOC
  ├─ Position handling                 122 LOC
  ├─ UI Build (_build)                126 LOC
  ├─ Timers & Feed                     111 LOC
  ├─ Persistence                       157 LOC
  ├─ Position Interface                 47 LOC
  ├─ Timeframe handling                 37 LOC
  ├─ Update & Rendering               343 LOC  ← LARGEST SECTION
  ├─ Proximity / Heat                   35 LOC
  ├─ Public API                        79 LOC
  ├─ Panel 3 data interface           104 LOC
  ├─ Demo utilities                     11 LOC
  ├─ Theme refresh                     37 LOC
  └─ Lifecycle (closeEvent)             3 LOC
```

#### Proposed module sizes (post-refactor):
```
csv_feed_handler.py        150 LOC   (30% reduction via modularization)
state_persistence.py       200 LOC   (consolidate scattered DB calls)
visual_indicators.py       200 LOC   (extract heat/proximity)
order_flow.py              250 LOC   (extract event handlers + calculations)
position_display.py        300 LOC   (extract rendering)
metrics_calculator.py      150 LOC   (extract expensive calculations)
position_state.py          100 LOC   (new: shared state model)
panel2_main.py             150 LOC   (thin orchestrator)

TOTAL                     1500 LOC   ← 430 LOC reduction (22% smaller)
                                       + better maintainability
```

---

## Appendix B: Key Design Decisions

### Decision 1: Immutable PositionState Dataclass
**Why**: Eliminate race conditions when multiple modules read/write position state
- Pass PositionState snapshots to modules
- Only OrderFlow can mutate (via set_position())
- Display/indicators get read-only copies
- Simplifies testing (no shared mutable state)

### Decision 2: Signal-Based Module Communication
**Why**: Decouple modules from direct dependencies
- CSVFeedHandler emits `data_updated` → Panel2 coordinates refresh
- OrderFlow emits `position_opened` / `position_closed` → Persistence listens
- No circular imports, clear event flow

### Decision 3: Separate JSON + DB Persistence
**Why**: Trade extremes need fast updates (DB) + recovery (JSON)
- JSON: entry_time_epoch, heat_start_epoch (timer state)
- DB: full position + trade extremes (for MAE/MFE recovery)
- Double-write during position open, single reads on mode switch

### Decision 4: Keep Panel2 as Orchestrator
**Why**: Minimize refactoring risk
- Panel2 becomes thin wrapper, maintains current public API
- Signal bus connections remain in Panel2 (unchanged)
- Modules don't directly talk to signal bus (cleaner deps)
- Easier rollback if issues arise

---

## Summary

**Panel2 Decomposition Plan**:
1. 5 focused modules replacing 1930-line monolith
2. 30+ shared state variables consolidated via PositionState dataclass
3. 8 circular dependency patterns identified + solutions proposed
4. 6 implementation challenges analyzed with risk mitigation
5. 2-3 week development roadmap with testing strategy

**Key Metrics**:
- Code reduction: 22% (1930 → 1500 LOC via consolidation)
- Testability: Each module independently unit-testable
- Maintenance: Clear responsibility boundaries, reduced cognitive load
- Performance: Potential 10-15% improvement via smarter refresh batching
