# Panel2 Modularization Plan

**Current State**: panels/panel2.py (1853 lines, 53 methods)
**Target**: 6 focused modules in panels/panel2/

---

## Module Breakdown

### 1. `__init__.py` (~400 lines) - Main Panel Orchestration

**Responsibility**: Layout, signal routing, mode management, delegation to modules

**Methods**:
- `__init__()` - Initialize panel, create module instances
- `_build()` - Layout construction (lines 660-791)
- `_connect_signal_bus()` - SignalBus subscriptions (lines 141-187)
- `_setup_timers()` - Timer setup (lines 792-808)
- `set_trading_mode()` - Mode switching (lines 1042-1099)
- `set_symbol()` - Symbol switching (lines 1148-1159)
- `refresh()` - Main refresh (lines 1680-1687)
- `_refresh_all_cells()` - Delegate to modules (lines 1298-1358)
- `_build_theme_stylesheet()` - Theme (lines 1810-1853)
- **Properties** (compatibility layer, lines 188-244):
  - `entry_price`, `entry_qty`, `is_long`
  - `target_price`, `stop_price`
  - `entry_vwap`, `entry_delta`, `entry_poc`
  - `entry_time_epoch`
  - `_trade_min_price`, `_trade_max_price`

**State**:
- Module instances (position_display, pnl_display, etc.)
- Core panel state (mode, account, symbol)
- Position domain object (`_position`)
- Market feed state (last_price, vwap, cum_delta, poc)
- Timers (csv_timer, clock_timer)

---

### 2. `position_display.py` (~200 lines) - Position Info Display

**Responsibility**: Display entry qty, price, time, duration, heat timer

**Methods**:
- `__init__(grid_layout, row_offset)` - Create cells
- `update_from_position(position: Position)` - Update all cells from Position object
- `update_time_and_heat()` - Entry time, duration, heat (lines 1366-1420)
- `set_position(qty, entry_price, is_long)` - Update position cells (lines 1100-1141)
- `has_active_position() -> bool` - Check if position open (lines 1788-1794)
- `refresh_pill_colors()` - Entry pill styling (lines 1275-1297)

**Cells**:
- `c_entry_qty` - Entry quantity + side pill
- `c_entry_price` - Entry price
- `c_entry_time` - Entry timestamp
- `c_duration` - Time in position
- `c_heat` - Heat timer

**Dependencies**:
- Position domain model
- Theme constants

---

### 3. `pnl_display.py` (~250 lines) - P&L Metrics Display

**Responsibility**: Display unrealized P&L, MAE, MFE, efficiency, R-multiple

**Methods**:
- `__init__(grid_layout, row_offset)` - Create cells
- `update_from_position(position: Position, last_price: float)` - Calculate & display P&L
- `update_price_cell(last_price)` - Current P&L (lines 1359-1365)
- `update_secondary_metrics(position, last_price)` - MAE/MFE/efficiency/R (lines 1447-1616)
- `clear()` - Reset all cells to "--"

**Cells**:
- `c_pnl` - Unrealized P&L (gross)
- `c_mae` - Maximum Adverse Excursion
- `c_mfe` - Maximum Favorable Excursion
- `c_efficiency` - Capture ratio %
- `c_rmult` - R-multiple
- `c_risk` - Planned risk (calculated from stop)

**Dependencies**:
- Position domain model (for P&L calculations)
- COMM_PER_CONTRACT constant

---

### 4. `vwap_display.py` (~150 lines) - VWAP Entry Snapshot Display

**Responsibility**: Display VWAP, POC, CumDelta entry snapshots

**Methods**:
- `__init__(grid_layout, row_offset)` - Create cells
- `update_entry_snapshots(position: Position)` - Show entry VWAP/POC/Delta
- `update_live_values(vwap, poc, cum_delta)` - Update current values
- `clear()` - Reset cells

**Cells**:
- `c_entry_vwap` - VWAP at entry
- `c_entry_delta` - Cumulative delta at entry
- `c_entry_poc` - POC at entry

**Dependencies**:
- Position domain model (for entry snapshots)
- Theme constants

---

### 5. `chart_integration.py` (~300 lines) - Market Data & CSV Feed

**Responsibility**: Read CSV ticks, update market data, heat detection, proximity alerts

**Methods**:
- `__init__(panel: Panel2)` - Reference to main panel
- `on_csv_tick()` - Process CSV feed (lines 809-869)
- `read_snapshot_csv() -> bool` - Read market data file (lines 874-920)
- `on_clock_tick()` - Update live banner (lines 870-873)
- `update_heat_state_transitions(prev_price, new_price)` - Detect heat (lines 1658-1679)
- `update_proximity_alerts()` - Target/stop proximity (lines 1643-1657)
- `update_live_banner()` - Live mode banner (lines 1617-1642)

**State Managed**:
- `last_price`, `session_high`, `session_low`
- `vwap`, `cum_delta`, `poc`
- Heat timer state

**Dependencies**:
- CSV file path configuration
- Position object (for extremes tracking)
- Theme constants

---

### 6. `bracket_orders.py` (~250 lines) - Target/Stop Management

**Responsibility**: Display and manage target/stop prices, risk calculation

**Methods**:
- `__init__(grid_layout, row_offset)` - Create cells
- `set_targets(target, stop)` - Update target/stop (lines 1142-1147)
- `update_target_stop_cells(position)` - Display targets (lines 1421-1446)
- `calculate_risk(position) -> float` - Planned risk calc
- `clear()` - Reset cells

**Cells**:
- `c_target` - Target price
- `c_stop` - Stop price
- `c_risk` - Planned risk ($)

**Dependencies**:
- Position domain model (for stop_price)
- DOLLARS_PER_POINT, COMM_PER_CONTRACT constants

---

## Database/Signal Methods (Stay in __init__.py)

These are core orchestration methods that coordinate across modules:

- `notify_trade_closed(trade)` - Emit trade closed signal (lines 245-296)
- `_close_position_in_database(trade)` - Persist to DB (lines 297-359)
- `_close_position_legacy(trade)` - Legacy DB close (lines 360-418)
- `on_order_update(payload)` - Handle order updates (lines 419-549)
- `on_position_update(payload)` - Handle position updates (lines 550-659)
- `_write_position_to_database()` - Persist position (lines 1160-1219)
- `_update_trade_extremes_in_database()` - Update MAE/MFE (lines 1220-1254)
- `_load_position_from_database()` - Load on startup (lines 980-1041)
- `_load_state()` / `_save_state()` - State persistence (lines 932-979)
- `get_current_trade_data()` - Export position data (lines 1688-1759)
- `get_live_feed_data()` - Export market data (lines 1760-1772)
- `get_trade_state()` - Export state (lines 1773-1787)

---

## Extraction Strategy

### Phase 7.1: Create Module Structure
1. Create `panels/panel2/` directory
2. Create empty module files with class stubs
3. Define module interfaces

### Phase 7.2: Extract Position Display (Easiest First)
1. Move position display cells to `position_display.py`
2. Update `__init__.py` to use PositionDisplay module
3. Test position display works

### Phase 7.3: Extract P&L Display
1. Move P&L cells and logic to `pnl_display.py`
2. Update `__init__.py` to use PnLDisplay module
3. Test P&L calculations

### Phase 7.4: Extract VWAP Display
1. Move VWAP cells to `vwap_display.py`
2. Update `__init__.py` to use VWAPDisplay module
3. Test VWAP display

### Phase 7.5: Extract Bracket Orders
1. Move target/stop cells to `bracket_orders.py`
2. Update `__init__.py` to use BracketOrders module
3. Test target/stop display

### Phase 7.6: Extract Chart Integration
1. Move CSV feed logic to `chart_integration.py`
2. Update `__init__.py` to use ChartIntegration module
3. Test market data feed

### Phase 7.7: Final Integration & Testing
1. Remove duplicate code
2. Verify all functionality works
3. Run manual tests
4. Commit final refactor

---

## Success Criteria

- ✅ Each module < 400 lines
- ✅ Clear single responsibility per module
- ✅ No functionality regression
- ✅ All tests passing (if any exist)
- ✅ Application works end-to-end
- ✅ Total line count reduced (eliminate duplicates)
- ✅ Easier to navigate and maintain

---

## Risk Mitigation

1. **Extract one module at a time** - Easier to debug if something breaks
2. **Test after each extraction** - Catch regressions early
3. **Keep compatibility** - Use delegation pattern to avoid breaking external code
4. **Git commit after each phase** - Easy rollback if needed
5. **Manual testing** - Verify UI works as expected

---

**Estimated Time**: 6 hours (1 hour per module extraction)
**Current Line Count**: 1853
**Target Line Count**: ~1550 (eliminate ~300 lines of duplication/spacing)
