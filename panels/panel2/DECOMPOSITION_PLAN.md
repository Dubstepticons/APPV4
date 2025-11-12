# panel2.py Decomposition Plan

## Original File Analysis

**Original**: `panels/panel2.py` (1538 lines)
**Target**: 5 modules, max 500 lines each

## Module Breakdown

### 1. **__init__.py** (~25 lines)
**Purpose**: Package interface

**Contents:**
- Export Panel2 class
- Clean package imports

---

### 2. **helpers.py** (~60 lines)
**Purpose**: Utility functions

**Contents:**
- `fmt_time_human()` - Format seconds as "20s", "1:20s", "10:00s"
- `sign_from_side()` - Convert is_long bool to +1/-1/0
- `clamp()` - Clamp value between min/max
- `extract_symbol_display()` - Extract 3-letter symbol from full DTC symbol (e.g., "MES" from "F.US.MESZ25")

**Lines from original**: 36-76

---

### 3. **state_manager.py** (~180 lines)
**Purpose**: State persistence and mode management

**Contents:**
- **State Persistence:**
  - `get_state_path()` - Get state file path scoped by (mode, account)
  - `load_state()` - Load position state from JSON file
  - `save_state()` - Save position state to JSON file

- **Mode Management:**
  - `set_trading_mode()` - Switch between DEBUG/SIM/LIVE modes
  - Mode-specific state loading/saving

**Key Data:**
- State file format: `panel2_state_{mode}_{account}.json`
- Persisted fields: qty, entry_price, is_long, target_price, stop_price, entry_time

**Lines from original**: 760-870

---

### 4. **trade_handlers.py** (~420 lines)
**Purpose**: Trade notification and position update handlers

**Contents:**
- **Trade Notifications:**
  - `notify_trade_closed()` - Handle trade closure from Panel3
  - Extract trade data, calculate realized PnL
  - Emit tradesChanged signal

- **Order Updates:**
  - `on_order_update()` - Handle DTC order status messages
  - Parse OrderUpdate payloads
  - Update position state on fills

- **Position Updates:**
  - `on_position_update()` - Handle DTC position updates
  - Parse PositionUpdate payloads
  - Synchronize position state

**Key Signals:**
- `tradesChanged` - Emitted when trade closes with full trade dict

**Lines from original**: 148-512

---

### 5. **metrics_updater.py** (~520 lines)
**Purpose**: Live metrics calculation and cell updates

**Contents:**
- **Price Updates:**
  - `update_price_cell()` - Update last price display

- **Time/Heat Updates:**
  - `update_time_and_heat_cells()` - Duration, heat state, warnings
  - Heat state machine: OFF → COOLING → WARM → WARNING → ALERT
  - Flash logic for 4:30-5:00 range

- **Target/Stop Updates:**
  - `update_target_stop_cells()` - Target and stop loss prices
  - Proximity alerts (within 2 ticks)

- **Secondary Metrics:**
  - `update_secondary_metrics()` - Qty, Entry, P&L, Commission, Risk/Reward, Distance to Target/Stop
  - Complex calculations for unrealized PnL, R:R ratios

- **Banner & Alerts:**
  - `update_live_banner()` - "LIVE POSITION" banner visibility
  - `update_proximity_alerts()` - Warning colors near target/stop
  - `update_heat_state_transitions()` - Heat state machine transitions

- **Orchestration:**
  - `refresh_all_cells()` - Refresh all metrics
  - CSV feed integration

**Key Metrics:**
- Last Price, Qty, Entry, P&L, Commission
- Duration, Heat, Target, Stop
- Risk/Reward ratios, Distance calculations

**Lines from original**: 1035-1355

---

### 6. **live_panel.py** (~400 lines)
**Purpose**: Panel2 main class, UI construction, delegation

**Contents:**
- **Panel2 Class:**
  - `__init__()` - Initialize panel and state
  - Delegation to helper modules

- **UI Construction:**
  - `_build()` - Create 3x5 grid layout
  - Header with "TRADING" title and badge
  - 15 MetricCell widgets
  - LIVE banner

- **Timer Setup:**
  - `_setup_timers()` - CSV feed (500ms) and clock (1s) timers
  - `_on_csv_tick()` - CSV feed handler
  - `_on_clock_tick()` - Clock tick handler
  - `_read_snapshot_csv()` - Read CSV file

- **Public API:**
  - `set_position()` - Set position externally
  - `set_targets()` - Set target/stop prices
  - `set_symbol()` - Change symbol
  - `refresh()` - Force refresh
  - `get_current_trade_data()` - Export trade data
  - `get_live_feed_data()` - Export feed data
  - `get_trade_state()` - Export position state
  - `has_active_position()` - Check if position active
  - `seed_demo_position()` - Demo mode helper

- **Theme Integration:**
  - `_build_theme_stylesheet()` - Build theme CSS
  - `_get_theme_children()` - Get child widgets for theme
  - `_on_theme_refresh()` - Custom theme refresh
  - `refresh_pill_colors()` - Update pill colors
  - `_on_timeframe_changed()` - Handle timeframe changes

- **Lifecycle:**
  - `closeEvent()` - Save state on close

**Delegation:**
- Calls state_manager for persistence
- Calls trade_handlers for notifications
- Calls metrics_updater for cell updates
- Calls helpers for formatting

**Lines from original**: 93-147, 513-661, 662-759, 871-930, 931-973, 974-1034, 1356-1538

---

## Module Dependencies

```
__init__.py (exports)
    └── live_panel.py (main class)
            ├── helpers.py (utility functions)
            ├── state_manager.py (persistence)
            ├── trade_handlers.py (notifications)
            └── metrics_updater.py (calculations)
```

## Implementation Strategy

### Phase 1: Extract Helper Functions
1. Create `helpers.py` with utility functions
2. Test independently

### Phase 2: Extract State Management
1. Create `state_manager.py` with persistence logic
2. Test state loading/saving without UI

### Phase 3: Extract Trade Handlers
1. Create `trade_handlers.py` with notification logic
2. Test signal emission

### Phase 4: Extract Metrics Logic
1. Create `metrics_updater.py` with calculation logic
2. Test calculations without UI

### Phase 5: Create Main Class
1. Create `live_panel.py` with Panel2 class
2. Delegate to helper modules
3. Wire all signals and slots

### Phase 6: Integration
1. Create `__init__.py` to export Panel2
2. Update imports in app_manager
3. Test full integration

## Benefits

1. **Clear Separation**: Each module has single, focused responsibility
2. **Testability**: Can test PnL calculations without UI
3. **Maintainability**: Max 520 lines per file (vs 1538 original)
4. **Reusability**: Helpers and state_manager can be reused
5. **Performance**: Can optimize individual modules

## File Size Targets

| Module | Target Lines | Purpose |
|--------|-------------|---------|
| `__init__.py` | ~25 | Package interface |
| `helpers.py` | ~60 | Utility functions |
| `state_manager.py` | ~180 | State persistence |
| `trade_handlers.py` | ~420 | Trade notifications |
| `metrics_updater.py` | ~520 | Metrics calculations |
| `live_panel.py` | ~400 | Main Panel2 class |
| **Total** | **~1605** | **6 modules** |

All modules under 600 lines! ✓

---

**Status**: Ready to implement
**Original**: 1538 lines (monolithic)
**Target**: 6 modules averaging 268 lines each
**Max Module**: 520 lines (66% reduction from original)
