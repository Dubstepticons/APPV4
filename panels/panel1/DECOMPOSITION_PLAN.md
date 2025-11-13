# panel1.py Decomposition Plan

## Original File Analysis

**Original**: `panels/panel1.py` (1784 lines)
**Target**: 6 modules, max 400 lines each

## Module Breakdown

### 1. **__init__.py** (~25 lines)
**Purpose**: Package interface

**Contents:**
- Export Panel1 class
- Export MaskedFrame helper class
- Clean package imports

---

### 2. **masked_frame.py** (~80 lines)
**Purpose**: Reusable rounded frame widget with theme support

**Contents:**
- MaskedFrame class (lines 51-126 from original)
- Helper widget for graph container
- Theme-aware background painting
- Rounded corners with proper masking

---

### 3. **balance_panel.py** (~380 lines)
**Purpose**: Panel1 main class skeleton, UI construction, and initialization

**Contents:**
- Panel1 class definition (inherits QWidget, ThemeAwareMixin)
- `__init__()` - initialization orchestration
- `_build_ui()` - main UI layout
- `_build_header()` - header with balance, badges, connection icon
- `_update_badge_style()` - badge appearance
- `_attach_plot_to_container()` - attach graph to frame
- `resizeEvent()` - handle window resizing
- `set_stats_panel()`, `set_panel_references()` - panel linkage
- Signal wiring: `_wire_balance_signal()`, `_on_balance_changed()`, `_on_mode_changed()`

**Delegation:**
- Calls equity_graph module for graph initialization
- Calls pnl_manager for PnL calculations
- Calls hover_handler for mouse interactions
- Calls animations for pulse/glow effects

**Lines from original**: 128-245, 313-445, 1696-1784

---

### 4. **equity_graph.py** (~350 lines)
**Purpose**: Graph initialization, plotting, and visual updates

**Contents:**
- `init_graph()` - create PyQtGraph widget with all components
  - Create PlotWidget
  - Configure axes, grid, background
  - Create plot items (equity line, endpoint marker)
  - Create trail lines and glow effects
  - Create crosshair (vertical/horizontal lines)
- `_replot_from_cache()` - redraw graph from equity points
- `_update_trails_and_glow()` - animate trailing lines and glow
- `set_equity_series()` - update graph data
- `update_equity_series()` - update with x/y arrays
- `_auto_range()` - automatic axis scaling
- `_recolor_endpoint()` - update endpoint color based on PnL
- `refresh()` - full graph refresh

**Key Data:**
- `_plot_widget` - PyQtGraph PlotWidget
- `_equity_line` - main equity curve
- `_endpoint_marker` - current balance marker
- `_trail_lines` - animated trailing lines
- `_glow_effect` - glow around endpoint

**Lines from original**: 445-612, 1257-1350, 1434-1451

---

### 5. **pnl_manager.py** (~380 lines)
**Purpose**: PnL calculations, equity curve loading, timeframe management

**Contents:**
- **Timeframe Management:**
  - `set_timeframe()` - switch timeframe (LIVE/1D/1W/1M/3M/YTD)
  - `_update_pnl_for_current_tf()` - recalculate PnL for current timeframe
  - `_filtered_points_for_current_tf()` - filter equity points by timeframe
  - `_get_baseline_for_tf()` - get baseline balance for timeframe

- **Database Loading:**
  - `_load_equity_curve_from_database()` - load historical equity from TradeRepository
  - `_get_equity_curve()` - get equity curve (with caching)
  - `_on_equity_curve_loaded()` - handle async loaded data

- **Balance/Equity Updates:**
  - `set_account_balance()` - set current balance
  - `update_equity_series_from_balance()` - add new equity point
  - `set_pnl_for_timeframe()` - set PnL label for timeframe
  - `_compose_pnl_header_text()` - format PnL header text
  - `_apply_pnl_to_header()` - update header with PnL
  - `_apply_pnl_to_pills()` - update pill colors

- **Mode Management:**
  - `set_trading_mode()` - switch between SIM/LIVE
  - `switch_equity_curve_for_mode()` - load equity curve for mode
  - `set_mode_live()` - enable/disable live mode

**Key Data:**
- `_equity_points` - list of (timestamp, balance) tuples
- `_current_display_mode` - SIM or LIVE
- `_current_tf` - current timeframe
- `_session_start_balance_sim` - session baseline
- `_pnl_up` - PnL direction (True/False/None)

**Lines from original**: 723-1001, 1077-1089, 1135-1223, 1387-1434, 1646-1677

---

### 6. **hover_handler.py** (~280 lines)
**Purpose**: Mouse hover interactions, crosshair, tooltip

**Contents:**
- `_init_hover_elements()` - initialize crosshair lines and hover state
- `eventFilter()` - intercept mouse events on graph
- `_on_mouse_move()` - handle mouse movement over graph
- `_update_header_for_hover()` - update header during hover
- `_find_nearest_index()` - find nearest data point to mouse
- `_on_investing_tf_changed()` - handle pills timeframe change

**Key Data:**
- `_hover_vline` - vertical crosshair line
- `_hover_hline` - horizontal crosshair line
- `_hover_active` - hover state flag
- `_hover_x`, `_hover_y` - hover coordinates
- `_hover_label` - tooltip label

**Features:**
- Crosshair follows mouse over graph
- Header shows balance/PnL at hover position
- Tooltip displays timestamp and value
- Smooth crosshair animations

**Lines from original**: 1451-1469, 1482-1696

---

### 7. **animations.py** (~200 lines)
**Purpose**: Pulse effects, glow animations, update timers

**Contents:**
- `_init_pulse()` - initialize pulse timer and animation
- `_on_pulse_tick()` - pulse animation frame update
- `_on_equity_update_tick()` - periodic equity update check
- `_ensure_live_pill_dot()` - ensure live indicator dot exists
- `_update_live_pill_dot()` - update pulsing live dot
- `_debug_sizes()` - debug widget sizes

**Key Data:**
- `_pulse_timer` - QTimer for pulse animation
- `_pulse_phase` - current pulse animation phase
- `_equity_update_timer` - QTimer for equity updates
- `_live_dot` - pulsing live indicator

**Features:**
- Smooth pulse animation on endpoint marker
- Live mode indicator pulsing
- Glow effect intensity modulation
- Periodic equity curve updates

**Lines from original**: 612-712, 1469-1482, 1772-1784

---

## Module Dependencies

```
__init__.py (exports)
    └── balance_panel.py (main class)
            ├── masked_frame.py (UI widget)
            ├── equity_graph.py (graph plotting)
            ├── pnl_manager.py (PnL calculations)
            ├── hover_handler.py (mouse interactions)
            └── animations.py (pulse/glow effects)
```

## Implementation Strategy

### Phase 1: Extract Helper Classes
1. Create `masked_frame.py` with MaskedFrame class
2. Test independently

### Phase 2: Extract Pure Logic Modules
1. Create `pnl_manager.py` with calculation logic
2. Create `animations.py` with timer logic
3. Test without UI dependencies

### Phase 3: Extract UI Modules
1. Create `equity_graph.py` with graph initialization
2. Create `hover_handler.py` with event handling
3. Test graph rendering

### Phase 4: Create Main Class
1. Create `balance_panel.py` with Panel1 class
2. Delegate to helper modules
3. Wire all signals and slots

### Phase 5: Integration
1. Create `__init__.py` to export Panel1
2. Update imports in app_manager
3. Test full integration

## Benefits

1. **Clear Separation**: Each module has single, focused responsibility
2. **Testability**: Can test PnL calculations without UI
3. **Maintainability**: Max 380 lines per file (vs 1784 original)
4. **Reusability**: MaskedFrame, hover logic can be reused
5. **Performance**: Can optimize individual modules

## File Size Targets

| Module | Target Lines | Purpose |
|--------|-------------|---------|
| `__init__.py` | ~25 | Package interface |
| `masked_frame.py` | ~80 | Rounded frame widget |
| `balance_panel.py` | ~380 | Main Panel1 class |
| `equity_graph.py` | ~350 | Graph plotting |
| `pnl_manager.py` | ~380 | PnL calculations |
| `hover_handler.py` | ~280 | Mouse interactions |
| `animations.py` | ~200 | Pulse/glow effects |
| **Total** | **~1695** | **7 modules** |

All modules under 400 lines! ✓

---

**Status**: Ready to implement
**Original**: 1784 lines (monolithic)
**Target**: 7 modules averaging 242 lines each
**Max Module**: 380 lines (79% reduction from original)
