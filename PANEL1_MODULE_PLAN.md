# Panel1 Modularization Plan

**Current State**: panels/panel1.py (1,889 lines, 58 methods)
**Target**: 5 focused modules in panels/panel1/

---

## Module Breakdown

### 1. `__init__.py` (~350 lines) - Main Panel Orchestration

**Responsibility**: Layout, signal routing, mode management, module delegation

**Methods**:
- `__init__()` - Initialize panel, create module instances
- `_build_ui()` - Layout construction (lines 341-408)
- `_build_header()` - Header widget (lines 409-459)
- `_connect_signal_bus()` - SignalBus subscriptions (lines 244-340)
- `set_trading_mode()` - Mode switching (lines 1106-1181)
- `resizeEvent()` - Handle resize (lines 530-540)
- `_wire_balance_signal()` - Balance signal wiring (lines 1801-1819)
- `_on_balance_changed()` - Balance updates (lines 1820-1851)
- `_on_mode_changed()` - Mode change handler (lines 1852-1876)
- `refresh()` - Main refresh (lines 1455-1461)

**State**:
- Module instances (balance_display, equity_graph, header_display, timeframe_pills)
- Core panel state (mode, account, balance)
- Timers (equity_update_timer, pulse_timer)

---

### 2. `balance_display.py` (~250 lines) - Balance & Connection Status

**Responsibility**: Display account balance, connection icon, mode badge

**Methods**:
- `__init__(header_widget)` - Create balance display cells
- `set_account_balance(balance)` - Update balance display (lines 1240-1242)
- `set_connection_status(connected)` - Update connection icon (lines 1235-1239)
- `_update_badge_style(mode)` - Mode badge styling (lines 460-504)
- `update_from_state(balance, mode, connected)` - Update all displays

**Cells/Widgets**:
- Balance label
- Connection icon (ConnectionIcon widget)
- Mode badge (SIM/LIVE/DEBUG)

**Dependencies**:
- StateManager for balance
- Theme constants

---

### 3. `equity_graph.py` (~600 lines) - Equity Curve Graph

**Responsibility**: Equity graph plotting, timeframe windowing, auto-ranging, hover crosshairs

**Methods**:
- `__init__(container_widget)` - Create PyQtGraph widget
- `_init_graph()` - Initialize plot (lines 541-707)
- `_init_pulse()` - LIVE pulse animation (lines 708-723)
- `_init_hover_elements()` - Crosshair initialization (lines 1587-1619)
- `_attach_plot_to_container(plot)` - Attach to layout (lines 505-529)
- `set_equity_series(points)` - Set equity data (lines 1430-1445)
- `update_equity_series(xs, ys)` - Update graph data (lines 1446-1454)
- `_replot_from_cache()` - Redraw from cache (lines 1362-1409)
- `_filtered_points_for_current_tf()` - Filter by timeframe (lines 1328-1361)
- `_auto_range(xs, ys)` - Auto-scale axes (lines 1462-1491)
- `_update_trails_and_glow()` - Update visual effects (lines 1410-1429)
- `_recolor_endpoint()` - Color endpoint based on P&L (lines 1539-1555)
- `_on_pulse_tick()` - LIVE pulse animation (lines 724-783)
- `_on_equity_update_tick()` - Periodic equity updates (lines 784-807)
- Event handlers: `eventFilter()`, `_on_mouse_move()` (lines 1620-1724)
- `_update_header_for_hover(x, y)` - Crosshair hover (lines 1725-1750)

**State**:
- PyQtGraph PlotWidget
- Equity points cache `_equity_points`
- Current timeframe
- Pulse animation timer
- Hover crosshair elements

**Dependencies**:
- PyQtGraph library
- Theme constants

---

### 4. `header_display.py` (~250 lines) - P&L Header Display

**Responsibility**: Display P&L value, percentage, timeframe in header

**Methods**:
- `__init__(header_widget)` - Create header label
- `set_pnl_for_timeframe(pnl_value, pnl_pct, up)` - Update P&L display (lines 1310-1327)
- `_compose_pnl_header_text()` - Format header text (lines 1492-1518)
- `_apply_pnl_to_header()` - Apply P&L to header (lines 1519-1527)
- `_update_pnl_for_current_tf()` - Calculate P&L for TF (lines 850-915)
- `_get_baseline_for_tf(at_time)` - Get baseline balance (lines 1751-1781)
- `_find_nearest_index(xs, target_x)` - Find nearest point (lines 1782-1800)

**State**:
- Header label widget
- Current P&L value, percentage
- P&L direction (up/down/neutral)

**Dependencies**:
- Equity graph data
- Timeframe state

---

### 5. `timeframe_pills.py` (~200 lines) - Timeframe Pills & Mode Sync

**Responsibility**: Timeframe pill buttons, LIVE dot, pill color sync

**Methods**:
- `__init__(parent)` - Create pill widgets
- `set_timeframe(tf)` - Set active timeframe (lines 819-849)
- `_ensure_live_pill_dot(initial)` - Ensure LIVE dot exists (lines 808-818)
- `_update_live_pill_dot(pulsing)` - Update LIVE dot (lines 1574-1586)
- `_apply_pnl_to_pills(up)` - Color pills based on P&L (lines 1528-1538)
- `_on_investing_tf_changed(tf)` - Handle TF change (lines 1556-1573)
- Event handler: timeframeChanged signal emission

**Widgets**:
- InvestingTimeframePills widget
- LIVE dot overlay

**Dependencies**:
- P&L direction (from header_display)
- Theme constants

---

### 6. `database_integration.py` (~300 lines) - Database & Mode Management

**Responsibility**: Load/save equity curves from database, mode switching

**Methods**:
- `__init__(panel: Panel1)` - Reference to main panel
- `_load_equity_curve_from_database(mode, account)` - Load from DB (lines 961-1018)
- `_get_equity_curve(mode, account)` - Get equity data (lines 1019-1074)
- `_on_equity_curve_loaded(mode, account, equity_points)` - Process loaded data (lines 1075-1105)
- `switch_equity_curve_for_mode(mode)` - Switch curve (lines 1182-1193)
- `update_equity_series_from_balance(balance, mode)` - Add point (lines 1243-1309)

**State Managed**:
- Equity curves cache (per mode)
- Session start balance (SIM/LIVE)
- Loading state

**Dependencies**:
- Database (PositionRepository or similar)
- StateManager

---

## Extraction Strategy

### Phase 1: Create Module Structure
1. Create `panels/panel1/` directory
2. Create empty module files with class stubs
3. Define module interfaces

### Phase 2: Extract Equity Graph (Core Complexity)
1. Move graph initialization to `equity_graph.py`
2. Move plotting methods
3. Move hover/crosshair logic
4. Test graph display works

### Phase 3: Extract Balance Display
1. Move balance/connection/badge to `balance_display.py`
2. Update `__init__.py` to use BalanceDisplay module
3. Test balance updates

### Phase 4: Extract Header Display
1. Move P&L header logic to `header_display.py`
2. Update `__init__.py` to use HeaderDisplay module
3. Test P&L display

### Phase 5: Extract Timeframe Pills
1. Move pill logic to `timeframe_pills.py`
2. Update `__init__.py` to use TimeframePills module
3. Test timeframe switching

### Phase 6: Extract Database Integration
1. Move DB/mode logic to `database_integration.py`
2. Update `__init__.py` to use DatabaseIntegration module
3. Test equity curve loading

### Phase 7: Final Integration & Testing
1. Remove duplicate code
2. Verify all functionality works
3. Run manual tests
4. Commit final refactor

---

## Success Criteria

- ✅ Each module < 600 lines
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

**Estimated Time**: 6-8 hours (1 hour per module extraction)
**Current Line Count**: 1,889
**Target Line Count**: ~1,650 (eliminate ~240 lines of duplication/spacing)

---

## Key Differences from Panel2

Panel1 is more complex due to:
- **PyQtGraph integration** - Equity graph is stateful and complex
- **Timeframe windowing** - Multiple timeframes (LIVE, 1D, 1W, 1M, 3M, YTD)
- **Hover crosshairs** - Interactive mouse tracking
- **Pulse animations** - LIVE mode pulsing endpoint
- **Database loading** - Async equity curve loading

Will require careful extraction to maintain all functionality.
