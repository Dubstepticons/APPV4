# Panel1.py Quick Reference Guide

## File Structure Overview

Total: 1820 lines

### Section Breakdown
- Lines 1-50: Imports & setup
- Lines 51-93: MaskedFrame utility class
- Lines 99-123: Helper functions (_pnl_color, _fmt_money, _fmt_pct)
- Lines 128-1820: Panel1 class

---

## Method Organization by Functional Area

### INITIALIZATION & CORE (139-343)
| Lines | Method | Purpose |
|-------|--------|---------|
| 139-243 | `__init__()` | Initialize all subsystems, create state, build UI, wire signals |
| 248-342 | `_connect_signal_bus()` | Subscribe to SignalBus for events (balance, mode, theme, TF) |

### UI BUILDING (345-540)
| Lines | Method | Purpose |
|-------|--------|---------|
| 345-409 | `_build_ui()` | Create main layout with balance, PnL, graph container |
| 413-462 | `_build_header()` | Create header with INVESTING label, badge, connection icon |
| 509-533 | `_attach_plot_to_container()` | Ensure plot fills container via layout stretch |
| 534-539 | `resizeEvent()` | Keep plot synced with container size |

### GRAPH INITIALIZATION & SETUP (543-707)
| Lines | Method | Purpose |
|-------|--------|---------|
| 543-707 | `_init_graph()` | Create PlotWidget, line, trails, glow, endpoint, ripples |
| 51-93 | `MaskedFrame` class | Custom QFrame with rounded background and clipping |
| 66-72 | `_shape_path()` | Define rounded rect geometry |
| 74-92 | `paintEvent()` | Paint background and clip children |

### GRAPH ANIMATION & UPDATES (708-802)
| Lines | Method | Purpose |
|-------|--------|---------|
| 708-723 | `_init_pulse()` | Start 25 FPS pulse timer and 1 sec equity update timer |
| 724-781 | `_on_pulse_tick()` | Animate endpoint breathing, sonar rings, glow, recolor based on PnL |
| 782-802 | `_on_equity_update_tick()` | Add current balance to equity curve every 1 second |

### GRAPH RENDERING & REPLOTTING (1298-1423)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1298-1341 | `_replot_from_cache()` | Filter points by TF, update line/endpoint/trails, auto-range |
| 1342-1361 | `_update_trails_and_glow()` | Update trailing lines with fractional data and glow |
| 1394-1423 | `_auto_range()` | Set X/Y ranges based on data and TF window |
| 1471-1484 | `_recolor_endpoint()` | Update endpoint brush color based on PnL direction |

### GRAPH DATA MANAGEMENT (1362-1386)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1362-1376 | `set_equity_series()` | Legacy API: Store full series and redraw |
| 1378-1385 | `update_equity_series()` | Legacy API: Accept parallel x/y arrays |

### TIMEFRAME MANAGEMENT (806-877)
| Lines | Method | Purpose |
|-------|--------|---------|
| 814-843 | `set_timeframe()` | Public API: Change TF, replot, update pills and PnL |
| 806-813 | `_ensure_live_pill_dot()` | Show/hide LIVE dot on pills |
| 845-877 | `_update_pnl_for_current_tf()` | Calculate PnL for active TF from stats service |
| 1488-1505 | `_on_investing_tf_changed()` | Internal handler: Update visuals and replot |
| 1506-1515 | `_update_live_pill_dot()` | Control LIVE dot visibility and pulsing |
| 1264-1295 | `_filtered_points_for_current_tf()` | Slice equity points to TF window using binary search |

### BALANCE DISPLAY & UPDATES (1176-1178, 370-392)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1176-1178 | `set_account_balance()` | Update balance label text with formatted currency |
| 1751-1782 | `_on_balance_changed()` | Handle StateManager balance change signal |
| 370-392 | Balance UI creation (in `_build_ui`) | Create lbl_balance with theme styling |

### PnL DISPLAY & CALCULATION (1246-1712)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1246-1261 | `set_pnl_for_timeframe()` | Set PnL state and coordinate display updates |
| 1424-1449 | `_compose_pnl_header_text()` | Format PnL as "ICON $amount (percentage%)" |
| 1451-1458 | `_apply_pnl_to_header()` | Update PnL label text and color |
| 1460-1470 | `_apply_pnl_to_pills()` | Update timeframe pills color based on PnL |
| 1657-1682 | `_update_header_for_hover()` | Calculate PnL for hovered point relative to baseline |
| 1683-1712 | `_get_baseline_for_tf()` | Get opening balance for TF using binary search |

### EQUITY CURVE STATE MANAGEMENT (926-1245)
| Lines | Method | Purpose |
|-------|--------|---------|
| 926-955 | `_load_equity_curve_from_database()` | Build equity curve from trade history (background thread) |
| 957-1011 | `_get_equity_curve()` | Get cached curve or initiate async load (**CRITICAL**: thread-safe) |
| 1013-1043 | `_on_equity_curve_loaded()` | Callback when async load completes (**CRITICAL**: mutex-protected) |
| 1179-1245 | `update_equity_series_from_balance()` | Add balance point to scoped curve (**CRITICAL FIX**: thread-safe) |

### HOVER & SCRUBBING (1518-1728)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1519-1551 | `_init_hover_elements()` | Create hover line, timestamp text, connect mouse signal |
| 1568-1654 | `_on_mouse_move()` | Handle hover: map coords, find nearest point, update display |
| 1552-1567 | `eventFilter()` | Hide hover elements when cursor leaves viewport |
| 1714-1728 | `_find_nearest_index()` | Binary search for closest data point |

### THEME & BADGE STYLING (464-507, 893-924, 1130-1170)
| Lines | Method | Purpose |
|-------|--------|---------|
| 464-507 | `_update_badge_style()` | Apply neon pill styling with conditional glow |
| 893-924 | `set_mode_live()` | Legacy compat: Update badge for LIVE/SIM |
| 1130-1133 | `_build_theme_stylesheet()` | Return stylesheet using THEME colors (ThemeAwareMixin) |
| 1135-1142 | `_get_theme_children()` | Return list of child panels for theme cascade |
| 1144-1166 | `_on_theme_refresh()` | Update all theme-dependent widgets (ThemeAwareMixin) |
| 1167-1169 | `_refresh_theme_colors()` | Wrapper calling `refresh_theme()` from mixin |

### MODE SWITCHING & TRADING (1044-1126)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1044-1116 | `set_trading_mode()` | **CRITICAL**: Switch mode/account scope, load equity, replot |
| 1118-1125 | `switch_equity_curve_for_mode()` | Deprecated: Wrapper calling `set_trading_mode()` |

### SIGNAL WIRING & EVENT HANDLING (1732-1804)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1732-1750 | `_wire_balance_signal()` | Connect StateManager balance signal |
| 1783-1804 | `_on_mode_changed()` | Handle mode switch from StateManager |

### PUBLIC API & UTILITIES (881-892, 1171-1175, 1387-1391)
| Lines | Method | Purpose |
|-------|--------|---------|
| 881-884 | `set_stats_panel()` | Store Panel3 reference |
| 886-891 | `set_panel_references()` | Store Panel2/Panel3 references for theme cascade |
| 1171-1174 | `set_connection_status()` | Update connection indicator |
| 1387-1390 | `refresh()` | Force UI repaint |
| 136-137 | `has_graph()` | Check if graph initialized |

### DIAGNOSTICS (1807-1819)
| Lines | Method | Purpose |
|-------|--------|---------|
| 1808-1818 | `_debug_sizes()` | Log widget sizes for debugging |

### HELPER FUNCTIONS (99-123)
| Lines | Function | Purpose |
|-------|----------|---------|
| 99-103 | `_pnl_color()` | Return color hex from direction (up/down/neutral) |
| 106-112 | `_fmt_money()` | Format float to currency string |
| 115-121 | `_fmt_pct()` | Format float to percentage string |

---

## Critical State Variables

### Equity Curve Management (Lines 155-174)
```python
self._equity_curves: dict[(mode, account), list[(timestamp, balance)]]  # CRITICAL
self._equity_mutex: QMutex  # CRITICAL THREAD-SAFETY
self._equity_points: list[(timestamp, balance)]  # Active scope
self._active_scope: tuple(mode, account)  # Current scope
self._pending_loads: set[(mode, account)]  # In-progress async loads
self.current_mode: str  # Active mode
self.current_account: str  # Active account
```

### Timeframe State (Lines 144, 196-204)
```python
self._tf: str  # Current timeframe (LIVE, 1D, 1W, 1M, 3M, YTD)
self._tf_configs: dict  # Window sizes and snap intervals
```

### PnL State (Lines 148-151)
```python
self._pnl_up: Optional[bool]  # Direction (True/False/None)
self._pnl_val: Optional[float]  # Dollar amount
self._pnl_pct: Optional[float]  # Percentage
```

### Graph State (Lines 176-195)
```python
self._plot: pg.PlotWidget  # Main pyqtgraph widget
self._vb: pg.ViewBox  # View box reference
self._line: pg.PlotDataItem  # Main curve line
self._endpoint: pg.ScatterPlotItem  # Breathing dot
self._trail_lines: list[pg.PlotDataItem]  # Trailing effect
self._glow_line: pg.PlotDataItem  # Soft halo
self._ripple_items: list[pg.ScatterPlotItem]  # Sonar rings
self._hover_seg: QGraphicsLineItem  # Vertical scrubber
self._hover_text: pg.TextItem  # Timestamp text
self._pulse_phase: float  # Animation phase
self._perf_safe: bool  # Performance toggle
```

### UI Widgets
```python
self.lbl_balance: QLabel  # Balance display
self.lbl_pnl: QLabel  # PnL display
self.mode_badge: QLabel  # Mode indicator (DEBUG/SIM/LIVE)
self.lbl_title: QLabel  # "INVESTING" header
self.conn_icon: ConnectionIcon  # Connection status
self.graph_container: MaskedFrame  # Graph wrapper
```

---

## Signal Connections

### SignalBus Connections (Lines 302-336)
| Signal | Handler | Purpose | Connection Type |
|--------|---------|---------|-----------------|
| `balanceUpdated(balance, account)` | `_on_balance_updated()` | Update balance display and equity curve (LIVE only) | Queued |
| `modeChanged(mode)` | `set_trading_mode(mode, None)` | Switch trading mode | Queued |
| `balanceDisplayRequested(balance, mode)` | `set_account_balance(balance)` | Display balance | Queued |
| `equityPointRequested(balance, mode)` | `update_equity_series_from_balance(balance, mode)` | Add equity point | Queued |
| `themeChangeRequested()` | `_refresh_theme_colors()` | Refresh all colors | Queued |
| `timeframeChangeRequested(tf)` | `set_timeframe(tf)` | Change timeframe | Queued |

### Qt Signals
| Signal | Type | Emitted By | Purpose |
|--------|------|-----------|---------|
| `timeframeChanged(str)` | QtCore.pyqtSignal | `_on_investing_tf_changed()` | Notify others of TF change |

---

## Data Dependencies Map

### What Each Module Needs

**equity_chart.py:**
- Inputs: `_equity_points`, `_tf`, `_tf_configs`, `_pnl_up`, THEME colors
- Outputs: Visual chart, hover artifacts

**balance_display.py:**
- Inputs: `balance` from StateManager/signal, THEME colors/fonts
- Outputs: `lbl_balance` text

**timeframe_manager.py:**
- Inputs: `_equity_points`, `_tf_configs`, stats_service, StateManager
- Outputs: `_tf` state, PnL recalculation

**pnl_calculator.py:**
- Inputs: `_equity_points`, `_tf`, stats_service, THEME colors
- Outputs: `_pnl_up`, `_pnl_val`, `_pnl_pct`, `lbl_pnl` text

**equity_state_manager.py:**
- Inputs: stats_service (equity curves), StateManager (balance)
- Outputs: `_equity_curves`, `_equity_points`, `_active_scope`

**theme_manager.py:**
- Inputs: THEME (global), `_pnl_up`
- Outputs: Badge style, label colors, graph colors

**signal_wiring.py:**
- Inputs: StateManager signals, SignalBus signals
- Outputs: Calls to all other modules

**ui_builder.py:**
- Inputs: THEME colors/fonts/sizing
- Outputs: Widget hierarchy

---

## Critical Paths (Must Not Break)

### Path 1: Equity Curve Loading
```
user switches mode
  → set_trading_mode()
    → _get_equity_curve() [MUTEX LOCK]
      → QtConcurrent.run(_load_equity_curve_from_database())
        → [Background thread] stats_service.get_equity_curve_for_scope()
        → QFutureWatcher fires on main thread
          → _on_equity_curve_loaded() [MUTEX LOCK/UNLOCK]
            → Update _equity_curves[scope]
            → Update _equity_points
            → _replot_from_cache()
```

### Path 2: Balance Update
```
DTC sends balance
  → SignalBus.balanceUpdated()
    → _on_balance_updated() [Main thread]
      → StateManager.set_balance_for_mode()
      → set_account_balance() → lbl_balance.setText()
      → update_equity_series_from_balance() [MUTEX LOCK/UNLOCK]
        → Add point to _equity_curves[scope]
        → Update _equity_points
        → _replot_from_cache() [Main thread, safe]
```

### Path 3: Timeframe Change
```
User clicks pill
  → set_timeframe()
    → _replot_from_cache()
      → _filtered_points_for_current_tf()
      → Update line/endpoint/trails
    → _update_pnl_for_current_tf()
      → stats_service.compute_trading_stats_for_timeframe()
      → set_pnl_for_timeframe()
        → _apply_pnl_to_header()
        → _apply_pnl_to_pills()
        → _recolor_endpoint()
```

### Path 4: Hover Update
```
Mouse moves over graph
  → _on_mouse_move()
    → _filtered_points_for_current_tf()
    → _find_nearest_index() [Binary search]
    → Update _hover_seg and _hover_text
    → _update_header_for_hover()
      → _get_baseline_for_tf() [Binary search]
      → Calculate and display hover PnL
```

---

## Thread Safety Checklist

When modifying Panel1:

- [ ] Does code access `_equity_curves`? → Must use `_equity_mutex.lock()/unlock()`
- [ ] Does code access `_pending_loads`? → Must use `_equity_mutex.lock()/unlock()`
- [ ] Does code run in background thread? → NO UI CALLS! Will deadlock
- [ ] Does code call from Qt signal? → Use QueuedConnection for cross-thread safety
- [ ] Does code hold mutex during UI call? → BUG! Will deadlock. Unlock first.
- [ ] Does code create QFutureWatcher? → Store it in `_future_watchers` to prevent GC

---

## Performance Considerations

### Memory Management
- Equity curve limited to last 2 hours (line 1222: `cutoff_time = now - 7200`)
- Prevents unbounded memory growth from continuous balance updates

### Graphics Optimization
- Performance mode (`_perf_safe`) reduces trail lines and glow for lower-end systems
- Pulse animation: 25 FPS (40ms) is reasonable for smooth breathing effect
- Equity update: 1 second interval avoids excessive repaints

### Database Async Loading
- Equity curves loaded in background thread (QtConcurrent)
- Prevents UI freeze when loading large trade histories
- QMutex prevents race conditions between loader and UI

---

## Common Patterns

### Pattern 1: Trigger Repaint After State Change
```python
# After updating _equity_points or _tf:
self._replot_from_cache()  # Always call this to refresh graph
```

### Pattern 2: Thread-Safe Equity Update
```python
self._equity_mutex.lock()
try:
    # Access _equity_curves or _pending_loads here
    ...
finally:
    self._equity_mutex.unlock()
# UI calls AFTER unlock (prevents deadlock)
```

### Pattern 3: Coordinate Multiple Updates
```python
# When multiple things change:
def set_pnl_for_timeframe(self, ...):
    self._pnl_up = ...  # Update state
    self._apply_pnl_to_header()  # Update UI
    self._apply_pnl_to_pills()   # Update pills
    self._recolor_endpoint()      # Update graph
```

### Pattern 4: Safe Widget Access
```python
# Check widget exists before updating:
if hasattr(self, "lbl_balance") and self.lbl_balance:
    self.lbl_balance.setText(...)
```

---

## Common Gotchas

1. **Forget to call `_replot_from_cache()` after updating `_equity_points`**
   - Result: Graph doesn't update
   - Fix: Always call after any equity point changes

2. **Access `_equity_curves` without mutex in async path**
   - Result: Race condition, corrupted data
   - Fix: Use `_equity_mutex.lock()/unlock()` pair

3. **Hold mutex during UI calls**
   - Result: Deadlock
   - Fix: Unlock BEFORE any UI updates

4. **Forget to store QFutureWatcher**
   - Result: Callback never fires (GC'd before completion)
   - Fix: Store in `_future_watchers` list

5. **Direct method calls instead of SignalBus**
   - Result: Cross-thread safety broken
   - Fix: Use SignalBus with QueuedConnection

---

## Testing Checklist

When modifying Panel1:

- [ ] Test balance updates (fast, slow, zero)
- [ ] Test mode switching (SIM ↔ LIVE)
- [ ] Test timeframe changes (all 6 options)
- [ ] Test hover scrubbing (all timeframes)
- [ ] Test theme switching
- [ ] Test PnL calculation with trades
- [ ] Stress test with rapid balance updates
- [ ] Verify no deadlocks on background thread edge cases
- [ ] Check memory doesn't bloat (2-hour limit works)
- [ ] Verify startup completes in reasonable time

