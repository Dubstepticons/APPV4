# app_manager.py Decomposition Plan

## Original File Analysis

**Original**: `core/app_manager.py` (823 lines)
**Target**: 5 modules, max 200 lines each

## Module Breakdown

### 1. **window.py** (~200 lines)
**Purpose**: MainWindow class skeleton and initialization orchestration

**Contents:**
- MainWindow class definition
- `__init__()` - orchestrates initialization sequence
- `_setup_window()` - window properties
- `_setup_state_manager()` - StateManager initialization and database init
- `_setup_theme()` - theme system setup
- `closeEvent()` - cleanup on application exit
- Module imports and logger setup

**Imports from other modules:**
- UIBuilder for `_build_ui()`
- SignalCoordinator for `_setup_cross_panel_linkage()`
- ThemeManager for theme methods
- DTCManager for `_init_dtc()`

---

### 2. **ui_builder.py** (~180 lines)
**Purpose**: UI construction - panels, layout, initial state

**Contents:**
- `build_ui(main_window)` - creates central widget, panels, layout
- Panel instantiation (Panel1, Panel2, Panel3)
- DTC initialization call
- Timeframe pill color sync
- Session start balance initialization
- Equity curve loading

**Dependencies:**
- Needs access to MainWindow instance
- Creates panels and adds them to MainWindow
- Calls DTCManager methods

---

### 3. **signal_coordinator.py** (~220 lines)
**Purpose**: Cross-panel signal wiring and UI controls setup

**Contents:**
- `setup_cross_panel_linkage(main_window, layout)` - massive signal wiring method
- `setup_theme_toolbar(main_window)` - theme switcher buttons
- `setup_mode_selector(main_window)` - SIM/LIVE mode dropdown
- `setup_reset_balance_hotkey(main_window)` - Ctrl+R hotkey
- `_on_reset_sim_balance_hotkey()` - balance reset handler
- Timeframe change handlers:
  - `_on_tf_changed()`
  - `_on_timeframe_changed()`
  - `_on_live_pills_tf_changed()`
  - `_on_stats_tf_changed()`

**Signal Wiring:**
- Panel1 ↔ Panel3 (timeframe changes)
- Panel2 trade signals → Panel1/Panel3
- Mode switching signals
- Theme change propagation

---

### 4. **theme_manager.py** (~130 lines)
**Purpose**: Theme switching logic and visual updates

**Contents:**
- `set_theme_mode(main_window, mode)` - apply theme to all panels
- `on_theme_changed(main_window, mode)` - theme change handler
- `optimize_archives_ui(main_window)` - UI optimizations post-theme
- `sync_pills_color_from_panel1(main_window)` - PnL-based color sync
- `pnl_color_from_direction(direction)` - helper for PnL colors

**Responsibilities:**
- Theme application across all panels
- Visual state synchronization
- Color palette management

---

### 5. **dtc_manager.py** (~130 lines)
**Purpose**: DTC client initialization and signal handling

**Contents:**
- `init_dtc(main_window)` - DTC client creation with circuit breaker
- `connect_dtc_signals(main_window)` - wire DTC signals to handlers
- `run_diagnostics_and_push(main_window)` - startup diagnostics

**Signal Handlers:**
- `_on_dtc_connected()` - update connection icon
- `_on_dtc_disconnected()` - clear connection state
- `_on_dtc_error(msg)` - error handling
- `_on_dtc_message(msg)` - heartbeat and data activity tracking
- `_on_connection_healthy()` - circuit breaker closed
- `_on_connection_degraded(reason)` - circuit breaker open
- `_on_dtc_stats_updated(stats)` - update connection icon with stats

**Integration:**
- Creates MessageRouter
- Creates ProtectedDTCClient
- Wires circuit breaker health monitoring

---

## Module Dependencies

```
window.py (main entry)
    ├── ui_builder.py (builds UI)
    ├── signal_coordinator.py (wires signals)
    ├── theme_manager.py (applies themes)
    └── dtc_manager.py (DTC connection)
```

## Import Strategy

Each module will:
1. Import only what it needs
2. Accept `main_window` parameter to access state
3. Return nothing (modifies main_window in place)
4. Use helper functions instead of methods where possible

## Benefits

1. **Modularity**: Each file has single responsibility
2. **Testability**: Can test UI building without DTC
3. **Readability**: ~150 lines per file vs 823 lines
4. **Maintainability**: Easy to locate and modify specific functionality
5. **Reusability**: Helper functions can be used independently

## Migration Strategy

1. Create new package: `core/app_manager/`
2. Create each module with helper functions
3. Create `window.py` with MainWindow that delegates to helpers
4. Test that application still works
5. Update imports in `main.py`: `from core.app_manager import MainWindow`
6. Keep old `core/app_manager.py` as backup until verified
7. Delete old file after testing complete

---

**Status**: Ready to implement
**Target Line Count**: ~860 lines (5 modules × ~170 avg)
**Reduction**: From 1 file of 823 lines to 5 files averaging 170 lines each
