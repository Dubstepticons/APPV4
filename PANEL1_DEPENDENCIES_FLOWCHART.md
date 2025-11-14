# Panel1 Module Dependencies & Data Flow

## Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PANEL1 (Orchestrator)                        │
│  - __init__() - Initialize all subsystems                           │
│  - set_trading_mode() - Route to mode changes                       │
│  - set_account_balance() - Route to balance display                 │
│  - set_timeframe() - Route to timeframe changes                     │
└──────────────────────────┬──────────────────────────────────────────┘
         │
         ├─────────────────────────────────┬──────────────────────────┐
         │                                 │                          │
         ▼                                 ▼                          ▼
   ┌──────────────┐            ┌──────────────────┐      ┌────────────────┐
   │  SIGNAL      │            │   UI BUILDER     │      │  EQUITY STATE  │
   │  WIRING      │            │                  │      │   MANAGER      │
   └──────────────┘            │  - _build_ui()   │      │                │
   - _wire_balance             │  - _build_header │      │ - _equity_curv │
   - _on_balance_changed       │  - MaskedFrame   │      │ - _equity_poin │
   - _on_mode_changed          └──────────────────┘      │ - _active_scop │
   - _connect_signal_bus()                              │ - _equity_mute │
        │                             │                  │                │
        │                             │                  │ CRITICAL MUTEX │
        │                             ▼                  │ THREAD-SAFETY  │
        │                  Creates:  lbl_balance         │                │
        │                           lbl_pnl              │ Methods:       │
        │                           mode_badge           │ - _get_equity_ │
        │                           graph_container      │ - _load_equity │
        │                           lbl_title            │ - _on_equity_c │
        │                           conn_icon            │ - update_equit │
        │                                                └────────────────┘
        │                                                         │
        ├────────────────────────────────────────┬────────────────┤
        │                                        │                │
        ▼                                        ▼                ▼
┌──────────────────┐              ┌───────────────────┐   ┌─────────────┐
│  TIMEFRAME       │              │  EQUITY CHART     │   │   BALANCE   │
│  MANAGER         │              │                   │   │   DISPLAY   │
└──────────────────┘              │ - _init_graph()   │   └─────────────┘
│                  │              │ - _replot_from_   │   │ set_account_│
│ - _tf            │              │ - _on_pulse_tick  │   │ balance()   │
│ - _tf_configs    │              │ - _on_mouse_move  │   └─────────────┘
│                  │              │ - _auto_range()   │
│ Methods:         │              │ - _init_hover_    │
│ - set_timeframe()│              │ - _update_trails_ │   Called by:
│ - _filtered_     │              │ - _recolor_endpo  │   - Signal handlers
│ - _update_pnl_   │              │                   │   - Mode changes
│ - _ensure_live_  │              │ State:            │   - Hover events
│   pill_dot()     │              │ - _plot, _vb      │
└──────────────────┘              │ - _line           │
        │                         │ - _endpoint       │
        │                         │ - _pulse_phase    │
        │                         │ - _hovering       │
        │                         │ - _hover_seg      │
        ▼                         │ - _hover_text     │
    Needs:                        │ - _pulse_timer    │
    - _equity_points              │ - _trail_lines    │
    - _tf                         │ - _glow_line      │
    - _tf_configs                 │ - _ripple_items   │
    - PnL methods                 └───────────────────┘
                                           │
                                    Needs:
                                    - _equity_points
                                    - _tf, _tf_configs
                                    - _pnl_up (color)
                                    - THEME colors
```

---

## Data Flow: Balance Update

```
DTC Balance Update
        │
        ▼
┌─────────────────────────────────────┐
│  SignalBus.balanceUpdated           │
│  (QueuedConnection - thread-safe)   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Panel1._on_balance_updated()        │
│  (from _connect_signal_bus)         │
│                                     │
│  1. Get StateManager                │
│  2. Only process LIVE mode          │
│  3. Call set_balance_for_mode()     │
└──────────────┬──────────────────────┘
               │
               ├─────────────────┬──────────────────┐
               │                 │                  │
               ▼                 ▼                  ▼
    StateManager       Panel1.set_account_  Panel1.update_equity_
    (LIVE balance)     balance() ─────────▶  series_from_balance()
                       │                     │
                       │                  MUTEX LOCK
                       ▼                  Add timestamp+balance
                    lbl_balance           to _equity_curves
                    Text UPDATE           MUTEX UNLOCK
                                          │
                                          ▼
                                     _replot_from_cache()
                                     (if active scope)
                                     │
                                     ├─► Update line/endpoint/trails
                                     ├─► Auto-range graph
                                     └─► Update PnL for TF
```

---

## Data Flow: Timeframe Change

```
User clicks timeframe pill
        │
        ▼
Pills emit signal or set_timeframe(tf)
        │
        ▼
┌──────────────────────────────────────┐
│  Panel1.set_timeframe(tf)            │
│  - Validate timeframe               │
│  - Update _tf state                 │
└──────────────┬───────────────────────┘
               │
               ├──────────────┬──────────────────┬──────────────┐
               │              │                  │              │
               ▼              ▼                  ▼              ▼
     _on_investing_   _replot_from_cache()  _update_pnl_   _ensure_live_
     tf_changed()     │                     for_current_    pill_dot()
                      │                     tf()            │
                      ▼                     │               ▼
                1. Call _filtered_          ▼           Update pills
                   points_for_current_   Call stats_     visuals
                   tf() using _tf         service:
                   and _tf_configs        compute_
                   │                      trading_
                   ▼                      stats_
                2. Update line with       for_timeframe()
                   filtered data          │
                3. Update endpoint        ▼
                   (LIVE/1D only)      Calculate PnL
                4. Update trails/        from trades
                   glow                  │
                5. Auto-range axis       ▼
                6. Emit timeframe        set_pnl_for_
                   Changed signal        timeframe()
                                         │
                                         ├─► _apply_pnl_to_header()
                                         ├─► _apply_pnl_to_pills()
                                         └─► _recolor_endpoint()
```

---

## Data Flow: Mode Switch

```
User switches SIM ↔ LIVE
        │
        ▼
┌──────────────────────────────────────┐
│  SignalBus.modeChanged or            │
│  Panel1.set_trading_mode()           │
└──────────────┬───────────────────────┘
               │
               ├─────────────────┬──────────────────────┬──────────────┐
               │                 │                      │              │
               ▼                 ▼                      ▼              ▼
         1. Validate        switch_theme()      Update badge    Get balance
            mode            │                    text & style    from
            │               ▼                    │              StateManager
            │           Update THEME         _update_badge_     │
            │           global colors        style()            ▼
            │           │                    │              set_account_
            │           ▼                    ▼              balance()
            │       All subsequent UI   Apply neon pill    │
            │       uses new colors     (with glow)        ▼
            │                           │              Update
            ▼                           ▼              lbl_balance
         2. Update         3. Load equity     text
            _active_scope     curve for new
            (mode, account)   scope
                            │
                            ▼
                    _get_equity_curve()
                    │
                    ├─► Check cache
                    │   (MUTEX LOCK)
                    │
                    ├─► If cached:
                    │   return immediately
                    │
                    └─► If not cached:
                        ├─► Mark as pending
                        │   (MUTEX)
                        │
                        └─► QtConcurrent.run(
                            _load_equity_curve_
                            from_database()
                            )
                            │
                            ▼
                        _on_equity_curve_
                        loaded()
                        │
                        ├─► MUTEX LOCK
                        ├─► Update cache
                        ├─► Update _equity_points
                        ├─► Clear pending
                        └─► MUTEX UNLOCK
                            │
                            ▼
                        _replot_from_cache()
                        │
                        └─► Graph refreshes
                            with new mode's data
```

---

## Data Flow: Hover/Scrubbing

```
Mouse move over graph
        │
        ▼
┌──────────────────────────────────────┐
│  pyqtgraph.sigMouseMoved.connect()   │
│  → Panel1._on_mouse_move(pos)        │
└──────────────┬───────────────────────┘
               │
               ▼
      Map scene pos to data coords
               │
               ▼
      Clamp to visible range
               │
               ▼
      Get filtered points for current TF:
      _filtered_points_for_current_tf()
      │ (Uses _equity_points + _tf + _tf_configs)
      │
      ▼
      Binary search find nearest point:
      _find_nearest_index(xs, target_x)
               │
               ├──┐
               │  └─→ Snap to actual data
               │      (never interpolate)
               ▼
      Get x, y of nearest point
               │
               ├─────────────────┬──────────────────┬──────────────┐
               │                 │                  │              │
               ▼                 ▼                  ▼              ▼
      Draw hover   Draw hover    Update header   Format
      vertical     timestamp      for hover:      timestamp
      line         text           │              for display
      │            │             ├─► Balance     │
      │            │             │   (y value)   ▼
      _hover_seg   _hover_text    │              Show time
      (85% height)                ├─► PnL        (HH:MM or
      │                           │   from       date-based)
      │                           │   baseline   │
      │                           │              ▼
      │                           └─► Color      _hover_text
      ▼                               from       setText()
      setVisible(True)                direction  setPos()
                                      │          setVisible()
                                      ▼
                                  _get_baseline_
                                  for_tf(at_time)
                                  │
                                  ├─► Binary search
                                  │   for baseline time
                                  │   based on _tf
                                  │
                                  └─► Return opening
                                      balance for TF
```

---

## State Update Synchronization

```
┌────────────────────────────────────────────────────────────┐
│  CRITICAL SHARED STATE UPDATES                             │
└────────────────────────────────────────────────────────────┘

When _equity_points changes:
    │
    └─► _replot_from_cache() MUST be called
        │
        ├─► _filtered_points_for_current_tf()
        │   (uses _tf, _tf_configs)
        │
        ├─► Update graph line/endpoint/trails
        │   (uses _pnl_up for colors)
        │
        ├─► _auto_range()
        │   (uses _tf_configs for window)
        │
        └─► Update PnL display
            (uses stats_service, _tf)


When _tf changes:
    │
    ├─► _replot_from_cache()
    │   (re-filter _equity_points with new window)
    │
    └─► _update_pnl_for_current_tf()
        (recalculate using new TF)


When _pnl_up changes:
    │
    ├─► _apply_pnl_to_header()
    │   (update label color/text)
    │
    ├─► _apply_pnl_to_pills()
    │   (update timeframe pills color)
    │
    ├─► _recolor_endpoint()
    │   (update curve endpoint brush)
    │
    └─► _on_pulse_tick() (automatic)
        (use for continuous animation)


When _active_scope changes:
    │
    ├─► Update _equity_points to point to
    │   _equity_curves[_active_scope]
    │
    └─► _replot_from_cache()
        (redraw with new scope's data)
```

---

## Thread Safety Boundaries

```
MAIN THREAD (Qt GUI)
  │
  ├─────────────────────────────────┐
  │   Safe Zone (No Mutex Needed)    │
  │  - UI updates (labels, colors)   │
  │  - Signal emissions             │
  │  - Timer callbacks              │
  │  - Event handlers               │
  └─────────────────────────────────┘
  │
  │  ┌──────────────────────────────────────────┐
  │  │  CRITICAL ZONE (Mutex Required)          │
  │  │                                          │
  │  │  _equity_mutex.lock()                    │
  │  │  ├─► Access _equity_curves dict         │
  │  │  ├─► Access _pending_loads set          │
  │  │  └─► Keep LOCKED only for dict access  │
  │  │                                          │
  │  │  _equity_mutex.unlock()                  │
  │  │  └─► Before any UI updates!             │
  │  │      (prevents deadlock)                │
  │  └──────────────────────────────────────────┘
  │
  └─────────────────────────────────┐
      BACKGROUND THREADS             │
      (QtConcurrent pool)             │
      │                              │
      ├─ _load_equity_curve_from_   │
      │  database()                 │
      │  ├─► Query database         │
      │  ├─► Build equity list      │
      │  └─► NO UI ACCESS!          │
      │      (will deadlock)        │
      │                              │
      └─► QFutureWatcher fires      │
          on main thread             │
          └─► _on_equity_curve_      │
              loaded()               │
              ├─► MUTEX LOCK         │
              ├─► Update cache       │
              ├─► MUTEX UNLOCK       │
              └─► UI update          │
                  (main thread safe)
```

---

## Module Integration Points

### 1. equity_chart.py ← → equity_state_manager.py
**Interface**:
- equity_chart needs: `_equity_points` (current data)
- Call pattern: `_replot_from_cache()` after equity_state_manager updates points

### 2. equity_chart.py ← → timeframe_manager.py
**Interface**:
- equity_chart needs: `_tf`, `_tf_configs` (for filtering)
- Call pattern: Both call shared helper `_filtered_points_for_current_tf()`

### 3. equity_chart.py ← → pnl_calculator.py
**Interface**:
- equity_chart needs: `_pnl_up` (for colors)
- equity_chart reads: `_pnl_val`, `_pnl_pct` (for display)
- Call pattern: pnl_calculator updates state, equity_chart auto-reflects

### 4. timeframe_manager.py ← → pnl_calculator.py
**Interface**:
- timeframe_manager calls: `_update_pnl_for_current_tf()`
- pnl_calculator calls: `set_pnl_for_timeframe()` (which updates colors)

### 5. pnl_calculator.py ← → theme_manager.py
**Interface**:
- pnl_calculator needs: Color mapping from `_pnl_up`
- Both read: `THEME` global colors
- Call pattern: Use `_pnl_color()` helper for colors

### 6. equity_state_manager.py ← → signal_wiring.py
**Interface**:
- signal_wiring calls: `update_equity_series_from_balance()`, `set_trading_mode()`
- Both access: `_active_scope`, `_equity_curves`, `_equity_mutex`
- Call pattern: Signal handlers route to state manager methods

### 7. All modules ← → ui_builder.py
**Interface**:
- ui_builder creates: widgets used by all modules
- All modules read/write: `lbl_balance`, `lbl_pnl`, `_plot`, etc.

### 8. All modules ← → THEME (global)
**Interface**:
- All modules read: `THEME.get(key, default)`
- Colors, fonts, sizes, configuration
- Updated by: `switch_theme()` and `refresh_theme()` from signal_wiring

---

## API Contracts (Public Methods)

```
CALLER (MainWindow, Controller)
  │
  ├─► Panel1.set_trading_mode(mode, account)
  │   └─► Routes to: equity_state_manager, theme_manager,
  │                  balance_display, equity_chart
  │
  ├─► Panel1.set_timeframe(tf)
  │   └─► Routes to: timeframe_manager, equity_chart,
  │                  pnl_calculator
  │
  ├─► Panel1.set_account_balance(balance)
  │   └─► Routes to: balance_display
  │
  ├─► Panel1.update_equity_series_from_balance(balance, mode)
  │   └─► Routes to: equity_state_manager
  │
  ├─► Panel1.set_pnl_for_timeframe(pnl_value, pnl_pct, up)
  │   └─► Routes to: pnl_calculator, theme_manager, equity_chart
  │
  └─► Panel1.set_panel_references(panel2, panel3)
      └─► Routes to: theme_manager (for cascade refresh)

SIGNAL CONNECTIONS (Auto-routed)
  │
  ├─► SignalBus.balanceUpdated()
  │   └─► _connect_signal_bus() routes to:
  │       - StateManager.set_balance_for_mode()
  │       - set_account_balance()
  │       - update_equity_series_from_balance()
  │
  ├─► SignalBus.modeChanged()
  │   └─► _connect_signal_bus() routes to:
  │       - set_trading_mode()
  │
  ├─► SignalBus.themeChangeRequested()
  │   └─► _connect_signal_bus() routes to:
  │       - _refresh_theme_colors() → refresh_theme()
  │
  └─► SignalBus.timeframeChangeRequested()
      └─► _connect_signal_bus() routes to:
          - set_timeframe()
```

