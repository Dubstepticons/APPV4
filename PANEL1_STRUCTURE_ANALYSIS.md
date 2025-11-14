# Panel1.py Structural Analysis (1820 lines)

## Overview
Panel1 is a complex equities/trading panel with pyqtgraph integration for charting, balance display, timeframe management, and theme-aware UI. It handles scoped equity curves per (mode, account) with thread-safe concurrent loading.

---

## FUNCTIONAL AREA 1: EQUITY CHART RENDERING & ANIMATION

### State Variables (Chart-related)
- `self._plot` (PlotWidget): Main pyqtgraph plot widget
- `self._vb` (ViewBox): pyqtgraph viewbox reference
- `self._line` (PlotDataItem): Main equity curve line
- `self._trail_lines` (list): Trailing effect lines for visual depth
- `self._glow_line` (PlotDataItem): Soft halo effect around main line
- `self._endpoint` (ScatterPlotItem): Breathing dot at curve end
- `self._ripple_items` (list): Sonar rings emanating from endpoint
- `self._hover_seg` (QGraphicsLineItem): Vertical hover scrubber line
- `self._hover_text` (pg.TextItem): Timestamp text on hover
- `self._perf_safe` (bool): Toggle for performance vs. visual fidelity
- `self._current_color` (QColor): Active curve color
- `self._target_color` (QColor): Target color for transitions
- `self.graph_container` (MaskedFrame): Container with rounded background

### Core Chart Methods
- **_init_graph()** (L543-707)
  - Creates PlotWidget with pyqtgraph
  - Initializes line, trails, glow, endpoint, ripples
  - Sets up ViewBox with proper axis configuration
  - Handles layout attachment
  
- **_attach_plot_to_container()** (L509-533)
  - Ensures plot fills container via layout stretch
  - Syncs geometry to prevent 640x480 default sizing
  - Sets size policies for responsive layout

- **_replot_from_cache()** (L1298-1341)
  - Filters equity points by current timeframe window
  - Updates line, endpoint, trails, glow with filtered data
  - Auto-ranges viewbox to fit visible data
  - Hides ripples/endpoint for non-LIVE/1D timeframes
  - **Dependencies**: Uses `self._equity_points`, timeframe config, filtered points

- **_update_trails_and_glow()** (L1342-1361)
  - Updates trailing lines with fractional dataset copies
  - Updates glow line with full visible data
  - Called from `_replot_from_cache()`

- **_auto_range()** (L1394-1423)
  - Sets X-axis range based on timeframe window (not just data extent)
  - Y-axis auto-ranges with padding
  - Prevents over-zooming with sparse data
  - **Shared state**: Uses `self._tf_configs` for window size

### Pulse/Animation Methods
- **_init_pulse()** (L708-723)
  - Creates 25 FPS timer for breathing endpoint
  - Starts 1-second equity update timer for hover timeline
  
- **_on_pulse_tick()** (L724-781)
  - Updates endpoint size with sinusoidal breathing
  - Updates sonar rings with phased ripple effect
  - Re-colors endpoint/trails based on PnL direction (green/red)
  - Updates glow alpha in sync with pulse
  - **Shared state**: Uses `self._pnl_up`, `self._pnl_val`, `self._pulse_phase`

- **_on_equity_update_tick()** (L782-802)
  - Adds current balance to equity curve every 1 second
  - Ensures continuous timeline for hover even when balance static
  - **Dependencies**: Calls `update_equity_series_from_balance()`

### Endpoint & Color Methods
- **_recolor_endpoint()** (L1471-1484)
  - Re-colors endpoint brush based on PnL direction
  - Called from `set_pnl_for_timeframe()`

### MaskedFrame (L51-93) - Utility Class
- Custom QFrame with theme background and shape clipping
- `set_background_color()`: Updates background dynamically
- `_shape_path()`: Defines rounded rect geometry
- `paintEvent()`: Paints background and clips children to shape

---

## FUNCTIONAL AREA 2: BALANCE DISPLAY

### State Variables (Balance-related)
- `self.lbl_balance` (QLabel): Main balance display label
- No separate balance value storage (displayed from StateManager)

### Balance Display Methods
- **set_account_balance()** (L1176-1178)
  - Updates balance label text with formatted currency
  - Called from mode changes, balance signals, and hover events
  - **Uses**: `_fmt_money()` helper

- **_build_ui()** (L345-409) - Includes balance display setup
  - Creates balance label with fixed sizing
  - Applies theme stylesheet for color and font
  - Sets up container layout with balance above PnL
  - **Dependencies**: Uses THEME colors, fonts, sizing

### Header Building (includes balance)
- **_build_header()** (L413-462)
  - Creates unified header with INVESTING label + badge + connection icon
  - Badge shows trading mode (DEBUG/SIM/LIVE)
  - Connection icon on right

### Display Synchronization
- Balance updates through multiple paths:
  1. `_on_balance_changed()` from StateManager
  2. Hover preview showing historical balance
  3. Mode switch showing new mode's balance

---

## FUNCTIONAL AREA 3: TIMEFRAME MANAGEMENT

### State Variables (Timeframe-related)
- `self._tf` (str): Current active timeframe (LIVE, 1D, 1W, 1M, 3M, YTD)
- `self._tf_configs` (dict): Timeframe window sizes and snap intervals (L196-204)
  - LIVE: 3600s window, 60s snap
  - 1D: 86400s window, 300s snap
  - 1W: 604800s window, 3600s snap
  - 1M: 2592000s window, 14400s snap
  - 3M: 7776000s window, 43200s snap
  - YTD: None window (all data), 86400s snap

### Timeframe Pill Methods
- **set_timeframe()** (L814-843)
  - Public API for timeframe changes
  - Validates timeframe against known set
  - Calls `_on_investing_tf_changed()` handler
  - Replots graph with new window
  - Updates LIVE pill pulse state
  - Recalculates PnL for new timeframe
  - **Emits**: `timeframeChanged` signal

- **_ensure_live_pill_dot()** (L806-813)
  - Ensures LIVE dot visible on pills
  - Controls pulsing based on initial state
  - Safe if pills widget lacks these hooks

- **_on_investing_tf_changed()** (L1488-1505)
  - Internal handler for timeframe selection
  - Updates pill visuals and pulsing
  - Recolors endpoint based on PnL
  - Syncs pill color with PnL direction
  - Emits `timeframeChanged` signal

- **_update_live_pill_dot()** (L1506-1515)
  - Shows/hides LIVE dot
  - Controls pulsing animation
  - Safe fallback if widget doesn't support

### Timeframe Filtering
- **_filtered_points_for_current_tf()** (L1264-1295)
  - Slices equity points to timeframe window
  - Returns all points if window_sec is None (YTD)
  - Uses binary search to find start index
  - **Shared state**: Uses `self._tf_configs`, `self._equity_points`

- **_update_pnl_for_current_tf()** (L845-877)
  - Calculates PnL for active timeframe from actual trades
  - Calls stats service `compute_trading_stats_for_timeframe()`
  - Updates display with direction coloring
  - **Dependencies**: Uses stats_service, StateManager

### Signal
- `timeframeChanged` (L134): Emitted when timeframe changes

---

## FUNCTIONAL AREA 4: THEME SWITCHING & COLOR UPDATES

### State Variables (Theme-related)
- `self._current_color` (QColor): Current line/endpoint color
- `self._target_color` (QColor): Target color for smooth transition
- `self.mode_badge` (QLabel): Badge showing current mode
- `self.lbl_title` (QLabel): "INVESTING" header text
- `self.conn_icon` (ConnectionIcon): Connection status indicator

### Theme Application Methods
- **_update_badge_style()** (L464-507)
  - Applies neon pill styling to mode badge
  - Sets background, border, border-radius, text color from THEME
  - Conditionally applies glow effect (QGraphicsDropShadowEffect)
  - Only glows for SIM/LIVE, not DEBUG
  - Called from `set_trading_mode()`

- **set_mode_live()** (L893-924) - Legacy backward-compat method
  - Updates badge text and color for LIVE/SIM mode
  - Applies neon styling with mode-specific colors
  - Adds glow effect
  - **Uses THEME keys**: `mode_indicator_live`, `mode_indicator_sim`, `badge_text_color`

- **set_trading_mode()** (L1044-1116)
  - Calls `switch_theme(mode.lower())` to switch global THEME
  - Updates badge with `_update_badge_style()`
  - All subsequent theme-dependent UI updates use new THEME
  - **Critical**: Switches theme BEFORE badge styling

### ThemeAwareMixin Implementation (L1129-1170)
- **_build_theme_stylesheet()** (L1130-1133)
  - Returns stylesheet using current THEME bg_panel color
  
- **_get_theme_children()** (L1135-1142)
  - Returns list of child panels (Panel2, Panel3) for cascade refresh
  
- **_on_theme_refresh()** (L1144-1166)
  - Updates graph container background color
  - Updates balance label color and font
  - Updates PnL label color and font
  - **Note**: Badge is NOT updated here (managed by set_trading_mode)

- **_refresh_theme_colors()** (L1167-1169)
  - Legacy wrapper calling `refresh_theme()` from mixin

### Theme Synchronization
- **_connect_signal_bus()** (L248-342) includes theme signal
  - Subscribes to `signalBus.themeChangeRequested`
  - Calls `_refresh_theme_colors()` when fired
  - Thread-safe queued connection

---

## FUNCTIONAL AREA 5: PnL DISPLAY & CALCULATION

### State Variables (PnL-related)
- `self._pnl_up` (Optional[bool]): Direction flag (True=up/green, False=down/red, None=neutral)
- `self._pnl_val` (Optional[float]): Absolute PnL dollar amount
- `self._pnl_pct` (Optional[float]): Percentage PnL
- `self.lbl_pnl` (QLabel): PnL display label

### PnL Calculation Methods
- **_update_pnl_for_current_tf()** (L845-877)
  - Calculates PnL from stats service for active timeframe
  - Determines direction (up/down/none) based on sign
  - Calls `set_pnl_for_timeframe()` with results
  - **Dependencies**: stats_service, StateManager for mode

- **set_pnl_for_timeframe()** (L1246-1261)
  - Sets PnL state variables
  - Calls `_apply_pnl_to_header()` to update label
  - Calls `_apply_pnl_to_pills()` to update timeframe pills
  - Calls `_recolor_endpoint()` to update curve endpoint

### PnL Display Methods
- **_compose_pnl_header_text()** (L1424-1449)
  - Formats PnL as: ICON $amount (percentage%)
  - Shows neutral "-" if PnL near zero
  - Examples: "+ $50.00 (5.80%)" or "- $50.00 (5.80%)"

- **_apply_pnl_to_header()** (L1451-1458)
  - Updates PnL label text and color
  - Gets color from `_pnl_color()` based on direction
  - Applies font styling from THEME

- **_apply_pnl_to_pills()** (L1460-1470)
  - Updates timeframe pills with active color
  - Controls LIVE dot visibility and pulsing
  - Safe if pills lack these methods

### Hover-based PnL
- **_update_header_for_hover()** (L1657-1682)
  - Calculates PnL relative to baseline for hovered point
  - Updates balance and PnL labels with historical values
  - **Calls**: `_get_baseline_for_tf()`

- **_get_baseline_for_tf()** (L1683-1712)
  - Gets opening balance for timeframe using binary search
  - LIVE: 1 hour ago
  - 1D: Start of trading day
  - 1W: 7 days ago
  - 1M: 30 days ago
  - 3M: 90 days ago
  - YTD: Start of year
  - **Returns**: Baseline balance for PnL calculation

### Helper Functions
- **_pnl_color()** (L99-103): Returns color hex from direction
- **_fmt_money()** (L106-112): Formats float to currency string
- **_fmt_pct()** (L115-121): Formats float to percentage string

---

## FUNCTIONAL AREA 6: EQUITY CURVE STATE MANAGEMENT

### State Variables (Equity-related)
- `self._equity_curves` (dict): **CRITICAL** - Scoped curves by (mode, account) tuple
  - Key: `(mode: str, account: str)`
  - Value: `list[tuple[float, float]]` - (timestamp, balance) points
  
- `self._equity_points` (list): Active curve for current scope (legacy compat)
  - Points to current scope's curve from `_equity_curves`
  
- `self._equity_mutex` (QMutex): **CRITICAL** Thread-safety for curve access
  - Protects `_equity_curves` and `_pending_loads` from race conditions
  
- `self._pending_loads` (set): Tracks (mode, account) scopes with async loads in progress
  
- `self._active_scope` (tuple): Current active (mode, account) scope
  - Used to determine which curve to display and update
  
- `self.current_mode` (str): Current trading mode
- `self.current_account` (str): Current account identifier

- `self._session_start_balances` (dict): Opening balances by scope
- `self._session_start_time` (float): Session start timestamp

### Equity Curve Methods

#### Loading & Caching
- **_get_equity_curve()** (L957-1011)
  - **CRITICAL FIX**: Thread-safe with QMutex
  - Gets cached curve or initiates async load
  - Avoids duplicate load requests via `_pending_loads`
  - Uses QtConcurrent for background thread loading
  - Falls back to sync load if QtConcurrent unavailable
  - Returns empty list while load in progress

- **_load_equity_curve_from_database()** (L926-955)
  - Rebuilds equity curve from trade history
  - Queries stats_service `get_equity_curve_for_scope()`
  - Cumulative balance progression from closed trades
  - Handles exceptions gracefully with empty return

- **_on_equity_curve_loaded()** (L1013-1043)
  - Callback when async load completes
  - **CRITICAL FIX**: Thread-safe cache update with QMutex
  - Updates `_equity_curves[scope]` with loaded points
  - Clears scope from `_pending_loads`
  - Updates `_equity_points` if this is active scope
  - Triggers `_replot_from_cache()` if active scope

#### Point Updates
- **update_equity_series_from_balance()** (L1179-1245)
  - **CRITICAL FIX**: Uses strict (mode, account) scoping with thread-safe mutex
  - Adds balance point to scoped equity curve
  - Timestamps with current time
  - Limits curve to last 2 hours to prevent memory bloat
  - Updates both scoped dict and active points
  - Triggers repaint only if this is active scope
  - Called from:
    - DTC balance updates (via signal bus)
    - Mode switching
    - Periodic equity update ticker

- **update_equity_series()** (L1378-1385)
  - Legacy API accepting parallel x/y arrays
    - Calls `set_equity_series(zip(xs, ys))`

- **set_equity_series()** (L1362-1376)
  - **Legacy compat method**
  - Stores full series in cache
  - Calls `_replot_from_cache()` to draw filtered window
  - Calls `_update_pnl_for_current_tf()`

---

## FUNCTIONAL AREA 7: HOVER/SCRUBBING (Interactive Timeline)

### State Variables (Hover-related)
- `self._hovering` (bool): Is cursor over plot
- `self._scrub_x` (Optional[float]): X coordinate of scrubbed point
- `self._hover_seg` (QGraphicsLineItem): Vertical scrubber line
- `self._hover_text` (pg.TextItem): Timestamp text label
- `self._pulse_phase` (float): Animation phase for pulse effect

### Hover Methods
- **_init_hover_elements()** (L1519-1551)
  - Creates 85%-height vertical hover line
  - Creates timestamp text item with proper font
  - Connects mouse move signal
  - Installs event filter on viewport

- **_on_mouse_move()** (L1568-1654)
  - Handles cursor movement over plot
  - Maps scene coords to data coords
  - Clamps to visible range (xr[0]..xr[1])
  - Finds nearest actual data point (not interpolated)
  - Updates hover line and timestamp text
  - Calls `_update_header_for_hover()` to show historical values
  - **Uses**: `_find_nearest_index()` for snap-aware point selection

- **eventFilter()** (L1552-1567)
  - Hides hover line/text when cursor leaves viewport
  - Restores normal PnL display
  - Returns True to consume Leave event

### Hover Utilities
- **_find_nearest_index()** (L1714-1728)
  - Binary search to find closest data point
  - Snaps to actual data, never interpolates
  - Returns index or None if no points

---

## FUNCTIONAL AREA 8: SIGNAL WIRING & CONNECTIONS

### Qt Signals
- `timeframeChanged` (L134): str - emitted when timeframe changes

### Signal Connections
- **_connect_signal_bus()** (L248-342)
  - **Subscribes to**:
    - `balanceUpdated`: Updates StateManager and UI (LIVE mode only)
    - `modeChanged`: Calls `set_trading_mode()`
    - `balanceDisplayRequested`: Calls `set_account_balance()`
    - `equityPointRequested`: Calls `update_equity_series_from_balance()`
    - `themeChangeRequested`: Calls `_refresh_theme_colors()`
    - `timeframeChangeRequested`: Calls `set_timeframe()`
  - All connections use QueuedConnection for thread-safety

- **_wire_balance_signal()** (L1733-1750)
  - Connects StateManager `balanceChanged` signal
  - Calls `_on_balance_changed()` handler
  
- **_on_balance_changed()** (L1751-1782)
  - Called when StateManager balance changes
  - Gets current mode and balance from StateManager
  - Updates balance label
  - Calls `update_equity_series_from_balance()` for curve

- **_on_mode_changed()** (L1783-1804)
  - Called when trading mode switches (SIM <-> LIVE)
  - Updates `_current_display_mode`
  - Gets new balance from StateManager
  - Updates balance label
  - Recalculates PnL for new mode

### Panel References
- `self._peer_panel`: Panel3 reference (stats panel)
- `self._panel2`: Panel2 reference (for theme cascade)
- `self._panel3`: Panel3 reference (for theme cascade)

---

## FUNCTIONAL AREA 9: MODE SWITCHING

### State Variables (Mode-related)
- `self._mode_is_live` (bool): Legacy flag for LIVE mode
- `self._current_display_mode` (str): Current trading mode for display
- `self.current_mode` (str): Active mode
- `self.current_account` (str): Active account

### Mode Methods
- **set_trading_mode()** (L1044-1116)
  - **CRITICAL**: Implements mode change contract:
    1. Freeze current state (automatic via scope switch)
    2. Swap to new (mode, account) scope
    3. Reload equity curve from persistent storage
    4. Single repaint
  - Validates mode against ("DEBUG", "SIM", "LIVE")
  - Calls `switch_theme(mode.lower())` to update global THEME
  - Updates badge text and styling
  - Gets balance from StateManager
  - Calls `_get_equity_curve()` for new scope
  - Calls `_replot_from_cache()` and PnL update
  - **Dependencies**: StateManager, theme system

- **set_mode_live()** (L893-924) - **Legacy backward compat**
  - Updates badge for LIVE/SIM
  - Applies neon styling with mode-specific colors
  - Called from older code paths

- **switch_equity_curve_for_mode()** (L1118-1125) - **Deprecated**
  - Legacy wrapper calling `set_trading_mode()`

---

## CRITICAL DEPENDENCIES & SHARED STATE

### Cross-Functional Dependencies

#### 1. Equity Curves → All Visualization
- Graph rendering depends on `_equity_points`
- Hover depends on `_equity_points`
- PnL calculation depends on `_equity_points`
- Timeframe filtering depends on `_equity_points`

#### 2. Timeframe → Graph & PnL
- Graph calls `_filtered_points_for_current_tf()` using `_tf` and `_tf_configs`
- PnL calls `_update_pnl_for_current_tf()` using `_tf`
- Hover calls `_get_baseline_for_tf()` using `_tf`

#### 3. PnL Direction → Colors & Visuals
- Endpoint color from `_pnl_up`
- Line color from `_pnl_up`
- Pills color from `_pnl_up`
- Label color from `_pnl_up`

#### 4. Mode/Account Scope → State Isolation
- `_active_scope` determines active (mode, account)
- `_equity_curves[(mode, account)]` stores scope-specific data
- `_equity_points` mirrors active scope's curve
- `_pending_loads` tracks in-progress async loads

#### 5. Theme → All Styling
- Colors: line, endpoint, badge, labels, hover elements
- Fonts: balance, PnL, timestamp
- Background: graph container, plot
- Called via ThemeAwareMixin and SignalBus

### Shared State Updates Sequence

**When balance updates:**
1. Signal Bus → `_on_balance_updated()`
2. StateManager → `set_balance_for_mode()`
3. Panel1 → `set_account_balance()` (display)
4. Panel1 → `update_equity_series_from_balance()` (curve point)
5. Triggers `_replot_from_cache()` and PnL update

**When timeframe changes:**
1. Pills emit signal or `set_timeframe()` called
2. Updates `_tf` state
3. Calls `_replot_from_cache()` with timeframe window filtering
4. Calls `_update_pnl_for_current_tf()` to recalculate
5. Updates pill pulsing and endpoint visibility

**When mode switches:**
1. SignalBus → `_on_balance_updated()` or direct call
2. Calls `set_trading_mode(mode, account)`
3. Switches theme via `switch_theme(mode.lower())`
4. Updates badge styling
5. Loads equity curve via `_get_equity_curve()` (async if not cached)
6. Calls `_replot_from_cache()` with new scope's data

---

## THREAD SAFETY MECHANISMS

### QMutex Protection
- `self._equity_mutex` guards:
  - `self._equity_curves` (scoped curve dict)
  - `self._pending_loads` (async load tracking)
- Used in: `_get_equity_curve()`, `_on_equity_curve_loaded()`, `update_equity_series_from_balance()`

### Qt Thread-Safe Signals
- All SignalBus connections use `QueuedConnection` (thread-safe)
- Async equity loads via QtConcurrent with QFutureWatcher

### Best Practices
- Mutex locked only for dict access, unlocked before UI updates
- No UI calls hold the mutex (prevents deadlock)
- Future watchers stored to prevent garbage collection

---

## PROPOSED MODULE DECOMPOSITION

### 1. equity_chart.py (300-350 lines)
**Responsibility**: Pyqtgraph chart rendering and animation

**State:**
- `_plot`, `_vb`, `_line`, `_trail_lines`, `_glow_line`, `_endpoint`, `_ripple_items`
- `_pulse_phase`, `_perf_safe`, `_current_color`, `_target_color`
- `_hover_seg`, `_hover_text`, `_hovering`, `_scrub_x`
- `_pulse_timer`, `_equity_update_timer`
- `graph_container`

**Methods:**
- `_init_graph()`
- `_attach_plot_to_container()`
- `_replot_from_cache()` - **SHARED**: Depends on `_equity_points`, `_tf`, `_tf_configs`, `_pnl_up`
- `_update_trails_and_glow()`
- `_auto_range()` - **SHARED**: Depends on `_tf_configs`
- `_init_pulse()`
- `_on_pulse_tick()` - **SHARED**: Depends on `_pnl_up`, `_equity_points`
- `_on_equity_update_tick()` - **SHARED**: Calls `update_equity_series_from_balance()`
- `_recolor_endpoint()` - **SHARED**: Depends on `_pnl_up`
- `_init_hover_elements()`
- `_on_mouse_move()` - **SHARED**: Depends on `_equity_points`, `_tf`, `_tf_configs`, hover calculation methods
- `eventFilter()`
- `_find_nearest_index()`
- `resizeEvent()`
- `has_graph()` - **Query method**

**Shared Dependencies:**
- Needs `_equity_points` (from state manager)
- Needs `_tf`, `_tf_configs` (from timeframe manager)
- Needs `_pnl_up` (from PnL manager)
- Needs `graph_container` from UI builder
- Needs THEME colors from theme manager
- Needs helper functions: `_pnl_color()`, `_fmt_money()`, `_fmt_pct()`

---

### 2. balance_display.py (80-120 lines)
**Responsibility**: Balance label UI and updates

**State:**
- `lbl_balance` (QLabel)

**Methods:**
- `set_account_balance()` - **SHARED**: Called from multiple sources
- Balance label styling (from `_build_ui`)
- Balance label theme refresh (from `_on_theme_refresh`)

**Shared Dependencies:**
- Needs THEME colors and fonts
- Called by: signal handlers, mode changes, hover events
- Uses helper: `_fmt_money()`

---

### 3. timeframe_manager.py (180-220 lines)
**Responsibility**: Timeframe pill integration and filtering

**State:**
- `_tf` (str)
- `_tf_configs` (dict)

**Methods:**
- `set_timeframe()` - **HUB**: Coordinates multiple subsystems
- `_ensure_live_pill_dot()`
- `_update_pnl_for_current_tf()` - **SHARED**: Calls stats service, updates PnL
- `_filtered_points_for_current_tf()` - **SHARED**: Needs `_equity_points`, `_tf`, `_tf_configs`
- `_on_investing_tf_changed()`
- `_update_live_pill_dot()`

**Shared Dependencies:**
- Needs `_equity_points` (for filtering)
- Needs PnL methods (for recalculation)
- Needs graph methods (for replotting)
- Emits `timeframeChanged` signal
- Depends on stats_service for PnL calculation

---

### 4. theme_manager.py (120-150 lines)
**Responsibility**: Theme switching and color coordination

**State:**
- `_current_color`, `_target_color` (QColor)
- `mode_badge`, `lbl_title` (QLabel)
- `conn_icon` (ConnectionIcon)

**Methods:**
- `_update_badge_style()` - **SHARED**: Called from mode changes
- `set_mode_live()` - **SHARED**: Legacy compat
- Theme stylesheet building (from ThemeAwareMixin)
- `_on_theme_refresh()` - **SHARED**: Updates multiple widgets
- `_refresh_theme_colors()` - **SHARED**: Public API for theme changes
- `_apply_pnl_to_pills()` - **SHARED**: Updates pill colors based on PnL

**Shared Dependencies:**
- Needs THEME system (global)
- Needs `_pnl_up` for color direction
- Updates: badge, labels, graph colors, pill colors
- Called by: mode changes, PnL updates, theme change signals

---

### 5. pnl_calculator.py (150-180 lines)
**Responsibility**: PnL calculation and display formatting

**State:**
- `_pnl_up`, `_pnl_val`, `_pnl_pct` (PnL tracking)
- `lbl_pnl` (QLabel)

**Methods:**
- `_update_pnl_for_current_tf()` - **SHARED**: Calls stats service
- `set_pnl_for_timeframe()` - **HUB**: Coordinates color/display updates
- `_compose_pnl_header_text()`
- `_apply_pnl_to_header()`
- `_apply_pnl_to_pills()` - **SHARED**: Updates pill colors
- `_update_header_for_hover()` - **SHARED**: Needs `_equity_points`, timeframe info
- `_get_baseline_for_tf()` - **SHARED**: Needs `_equity_points`, `_tf`
- PnL label styling (from `_build_ui` and `_on_theme_refresh`)

**Shared Dependencies:**
- Needs stats_service for PnL calculation
- Needs `_equity_points` for baseline calculation
- Needs `_tf` for timeframe-specific baseline logic
- Updates theme colors and pill colors
- Needs THEME for formatting and colors

---

### 6. equity_state_manager.py (250-300 lines)
**Responsibility**: Scoped equity curve storage, loading, and thread-safety

**State:**
- `_equity_curves` (dict[(mode, account), list[tuple]])
- `_equity_points` (list) - Active curve
- `_equity_mutex` (QMutex) - **CRITICAL** Thread-safety
- `_pending_loads` (set)
- `_active_scope` (tuple)
- `current_mode`, `current_account` (str)
- `_session_start_balances`, `_session_start_time`
- `_future_watchers` (list) - Prevent GC

**Methods:**
- `_get_equity_curve()` - **CRITICAL**: Async load orchestration
- `_load_equity_curve_from_database()` - **Async**: Calls stats_service
- `_on_equity_curve_loaded()` - **Callback**: Updates cache, triggers repaint
- `update_equity_series_from_balance()` - **CRITICAL FIX**: Thread-safe updates
- `update_equity_series()` - **Legacy**: Wrapper
- `set_equity_series()` - **Legacy**: Wrapper
- Mode switching (from `set_trading_mode()`)

**Shared Dependencies:**
- Needs stats_service for loading equity curves
- Calls `_replot_from_cache()` after load/update
- Calls PnL recalculation methods
- Thread-safe access patterns via QMutex
- QtConcurrent for async loading

---

### 7. signal_wiring.py (100-150 lines)
**Responsibility**: Qt signal connections and event handling

**Methods:**
- `_connect_signal_bus()` - **HUB**: All SignalBus connections
- `_wire_balance_signal()` - **HUB**: StateManager connections
- `_on_balance_changed()` - **Handler**: Updates display and equity
- `_on_mode_changed()` - **Handler**: Updates mode-specific display
- Panel reference setters: `set_stats_panel()`, `set_panel_references()`

**Signal Definitions:**
- `timeframeChanged` (str)

**Shared Dependencies:**
- Calls methods across all functional areas
- Connected to: StateManager, SignalBus
- Coordinates: balance updates, mode changes, theme changes, PnL updates

---

### 8. ui_builder.py (150-180 lines)
**Responsibility**: UI layout and widget creation

**Methods:**
- `_build_ui()` - **Primary**: Creates main layout
- `_build_header()` - **Primary**: Creates header row
- `MaskedFrame` class (utility for rounded containers)
- Widget creation: balance, PnL, badge, connection icon

**Shared Dependencies:**
- Creates: `graph_container`, `lbl_balance`, `lbl_pnl`, `mode_badge`, `lbl_title`, `conn_icon`
- Uses THEME for colors, fonts, sizing
- Sets up container layouts
- Coordinates with graph attachment

---

### Core Panel1 Class (150-200 lines)
**Responsibility**: Orchestration, initialization, and public API

**Initialization:**
- `__init__()` - Orchestrates all module initialization
- Module instantiation and wiring
- Signal connection
- Initial state setup

**Public API:**
- `set_stats_panel()`
- `set_panel_references()`
- `set_connection_status()`
- `refresh()` - **Query**: Force repaint

**Delegation:**
- Routes public API calls to appropriate modules
- Ensures proper initialization order
- Handles cross-module dependencies

---

## INITIALIZATION ORDER (CRITICAL)

1. **Create State Managers**
   - Equity state manager (create scoped dict, mutex)
   - PnL state manager (initialize to $0, neutral)

2. **Build UI**
   - Create widgets (labels, badges, icons)
   - Create graph container
   - Note: Graph NOT created yet (placeholder)

3. **Wire Signals**
   - Connect StateManager balance signal
   - Connect SignalBus signals
   - Connect timeframe change handlers

4. **Initialize Graph**
   - Create pyqtgraph plot
   - Attach to container (CRITICAL timing)
   - Initialize hover elements
   - Start pulse timer

5. **Set Initial Theme**
   - Call `switch_theme()` with default (usually "live")
   - Update all colors

6. **Final Setup**
   - Ensure LIVE pill dot visible
   - Initialize PnL display ($0.00, neutral)
   - Start equity update timer

---

## MIGRATION NOTES

### Breaking Changes When Decomposing
1. **Scoped equity curves** - New architecture (mode, account) tuple keys
   - Old code may expect single global curve
   - Need migration path for legacy callers

2. **Thread-safe mutex** - New requirement for equity curve access
   - All code accessing `_equity_curves` or `_equity_points` must respect mutex
   - Potential for deadlock if not careful

3. **SignalBus dependency** - New pattern for event delivery
   - Old direct method calls being phased out
   - New code uses Qt signals instead

### Backward Compatibility Layer
- Keep legacy methods: `switch_equity_curve_for_mode()`, `set_mode_live()`, `update_equity_series()`, `set_equity_series()`
- These methods delegate to new implementations
- Allows gradual migration of caller code

---

## SUMMARY TABLE

| Module | Lines | Inputs | Outputs | Critical? |
|--------|-------|--------|---------|-----------|
| equity_chart.py | 350 | `_equity_points`, `_tf`, `_pnl_up` | Visual chart, hover artifacts | YES |
| balance_display.py | 100 | `balance` from StateManager | `lbl_balance` text | No |
| timeframe_manager.py | 200 | `_tf`, `_tf_configs`, `_equity_points` | `_tf` state, PnL recalc | YES |
| theme_manager.py | 140 | `_pnl_up`, THEME | Badge, label colors, styles | Medium |
| pnl_calculator.py | 170 | `_equity_points`, `_tf`, stats_service | `_pnl_*` state, `lbl_pnl` | YES |
| equity_state_manager.py | 280 | Database, StateManager | `_equity_curves`, `_equity_points` | **CRITICAL** |
| signal_wiring.py | 120 | Qt signals | Calls to all other modules | **CRITICAL** |
| ui_builder.py | 170 | THEME, widget creation | Widget hierarchy | No |
| **Total** | **1530** | | | |

