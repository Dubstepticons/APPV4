# Panel1 Decomposition - Implementation Specification

**Status:** Phase 1 - Foundation Modules In Progress
**Date:** 2025-11-14
**Original File:** `panels/panel1.py` (1,820 LOC)

---

## Executive Summary

Panel1 manages the equity chart display with PyQtGraph rendering, thread-safe equity curve management, hover interactions, timeframe filtering, and PnL calculations. This specification outlines the decomposition into 8 focused modules.

**Complexity Highlights:**
- PyQtGraph chart rendering with 25 FPS animation
- Thread-safe equity curve management (QMutex protection)
- Async equity loading with QtConcurrent
- Binary search for hover/scrubbing interactions
- 6 timeframe modes (LIVE, 1D, 1W, 1M, 3M, YTD)
- Complex PnL calculations with baseline lookups

---

## Planned Architecture

### 8 Modules (Est. 1,800 LOC total)

```
panels/panel1/
├── __init__.py              (10 LOC)   - Public API exports
├── panel1_main.py           (200 LOC)  - Thin orchestrator
├── helpers.py               (50 LOC)   - Utility functions (_pnl_color, _fmt_money, _fmt_pct)
├── masked_frame.py          (50 LOC)   - Custom QFrame with rounded clipping
├── pnl_calculator.py        (200 LOC)  - PnL calculations, baseline lookup, formatting
├── timeframe_manager.py     (220 LOC)  - Timeframe filtering, pills integration, binary search
├── equity_state.py          (320 LOC)  - Thread-safe equity curve management (CRITICAL)
├── equity_chart.py          (400 LOC)  - PyQtGraph rendering, animation, trails, glow
└── hover_handler.py         (250 LOC)  - Mouse hover, scrubbing, nearest point search

TOTAL: ~1,700 LOC
```

---

## Module Specifications

### Phase 1: Foundation (300 LOC)

#### 1. helpers.py (50 LOC)
**Purpose:** Utility functions for formatting and colors

**Functions:**
- `pnl_color(up: Optional[bool]) -> str` - Return color from PnL direction
- `fmt_money(v: Optional[float]) -> str` - Format currency ($1,234.56)
- `fmt_pct(p: Optional[float]) -> str` - Format percentage (+2.34%)

**Complexity:** Low
**Dependencies:** config.theme

---

#### 2. masked_frame.py (50 LOC)
**Purpose:** Custom QFrame with rounded background and clipping

**Class:**
```python
class MaskedFrame(QtWidgets.QFrame):
    def __init__(self, parent=None)
    def set_background_color(self, color: str)
    def _shape_path(self) -> QtGui.QPainterPath
    def paintEvent(self, event: QtGui.QPaintEvent)
```

**Features:**
- Paints theme background
- Automatically masks to painted geometry
- Children (PlotWidget) clipped to shape

**Complexity:** Low
**Dependencies:** PyQt6, config.theme

---

#### 3. pnl_calculator.py (200 LOC)
**Purpose:** PnL calculations and formatting

**Key Methods:**
```python
class PnLCalculator:
    @staticmethod
    def calculate_pnl(
        current_balance: float,
        baseline_balance: float
    ) -> dict:
        # Returns: {amount, percentage, is_positive}

    @staticmethod
    def get_baseline_for_timeframe(
        points: list[tuple[int, float]],
        timeframe: str,
        current_time: int
    ) -> Optional[float]:
        # Binary search for opening balance

    @staticmethod
    def compose_pnl_text(
        pnl_amount: float,
        pnl_pct: float
    ) -> str:
        # Format as "ICON $amount (percentage%)"
```

**Features:**
- PnL calculation (amount and percentage)
- Baseline lookup with binary search
- Text formatting with icons
- Null-safe operations

**Complexity:** Medium
**Dependencies:** helpers.py

---

### Phase 2: Timeframe Management (220 LOC)

#### 4. timeframe_manager.py (220 LOC)
**Purpose:** Timeframe filtering and window calculations

**Key Methods:**
```python
class TimeframeManager:
    TIMEFRAMES = ["LIVE", "1D", "1W", "1M", "3M", "YTD"]

    def __init__(self, current_tf: str = "LIVE")

    def set_timeframe(self, tf: str) -> None
    def get_timeframe(self) -> str

    @staticmethod
    def calculate_window_start(tf: str, current_time: int) -> int:
        # Calculate Unix timestamp for TF window start

    @staticmethod
    def filter_points_for_timeframe(
        points: list[tuple[int, float]],
        tf: str,
        current_time: int
    ) -> list[tuple[int, float]]:
        # Binary search to slice points to TF window

    @staticmethod
    def find_nearest_index(
        x_data: list[float],
        x_target: float
    ) -> int:
        # Binary search for closest point
```

**Features:**
- 6 timeframe modes
- Window start calculation (seconds ago)
- Binary search filtering
- Efficient point slicing

**Complexity:** Medium
**Dependencies:** None (pure Python)

---

### Phase 3: State Management (320 LOC) - **CRITICAL**

#### 5. equity_state.py (320 LOC)
**Purpose:** Thread-safe equity curve management

**Key Methods:**
```python
class EquityStateManager(QtCore.QObject):
    equityCurveLoaded = QtCore.pyqtSignal(str, str, object)  # mode, account, points

    def __init__(self):
        self._equity_curves: dict[tuple[str, str], list[tuple[int, float]]] = {}
        self._equity_mutex = QtCore.QMutex()
        self._current_mode: str = "SIM"
        self._current_account: str = ""

    def get_equity_curve(
        self,
        mode: str,
        account: str
    ) -> Optional[list[tuple[int, float]]]:
        # Thread-safe curve retrieval (with mutex)
        # Initiates async load if not cached

    def add_balance_point(
        self,
        balance: float,
        timestamp: int
    ) -> None:
        # Thread-safe point addition (with mutex)

    def set_mode(self, mode: str, account: str) -> None:
        # Switch active scope

    def _load_equity_curve_from_database(
        self,
        mode: str,
        account: str
    ) -> list[tuple[int, float]]:
        # Background thread: Build curve from trade history

    def _on_equity_curve_loaded(
        self,
        mode: str,
        account: str,
        points: list[tuple[int, float]]
    ) -> None:
        # Callback: Store loaded curve (with mutex)
```

**Features:**
- Thread-safe with QMutex
- Scoped curves per (mode, account)
- Async loading with QtConcurrent
- In-memory caching
- Signal emission on load complete

**Complexity:** High (thread safety critical)
**Dependencies:** PyQt6, services.stats_service

---

### Phase 4: Chart Rendering (400 LOC)

#### 6. equity_chart.py (400 LOC)
**Purpose:** PyQtGraph rendering with animation

**Key Methods:**
```python
class EquityChart(QtCore.QObject):
    def __init__(self, container: QtWidgets.QWidget):
        self._plot: pg.PlotWidget
        self._line: pg.PlotDataItem
        self._endpoint: pg.ScatterPlotItem
        self._trails: list[pg.PlotDataItem]
        self._glow: pg.PlotDataItem
        self._ripples: list[pg.ScatterPlotItem]
        self._pulse_timer: QtCore.QTimer

    def init_graph(self) -> None:
        # Create PlotWidget, line, trails, glow, endpoint, ripples

    def replot(self, points: list[tuple[int, float]]) -> None:
        # Update line data, endpoint, trails, auto-range

    def start_animation(self) -> None:
        # Start 25 FPS pulse timer

    def _on_pulse_tick(self) -> None:
        # Animate endpoint breathing, sonar rings, glow

    def update_endpoint_color(self, color: str) -> None:
        # Recolor endpoint based on PnL

    def auto_range(self, points: list[tuple[int, float]]) -> None:
        # Set X/Y ranges based on data
```

**Features:**
- PyQtGraph PlotWidget
- Line rendering with trails
- Animated endpoint (breathing effect)
- Sonar ripples (expanding rings)
- Glow effect
- 25 FPS pulse animation
- Auto-ranging

**Complexity:** High (graphics rendering)
**Dependencies:** pyqtgraph, PyQt6

---

### Phase 5: Hover Interactions (250 LOC)

#### 7. hover_handler.py (250 LOC)
**Purpose:** Mouse hover and scrubbing

**Key Methods:**
```python
class HoverHandler(QtCore.QObject):
    hoverPointChanged = QtCore.pyqtSignal(int, float, float)  # index, timestamp, balance

    def __init__(self, plot_widget: pg.PlotWidget):
        self._hover_line: pg.InfiniteLine
        self._hover_text: pg.TextItem
        self._current_points: list[tuple[int, float]] = []

    def init_hover_elements(self) -> None:
        # Create hover line and text overlay

    def set_points(self, points: list[tuple[int, float]]) -> None:
        # Update points for hover calculations

    def on_mouse_move(self, evt) -> None:
        # Map coords, find nearest point, update display

    def hide_hover(self) -> None:
        # Hide hover elements

    def _find_nearest_index(self, x_target: float) -> int:
        # Binary search for closest point
```

**Features:**
- Vertical hover line
- Timestamp + balance text overlay
- Binary search for nearest point
- Mouse tracking
- Cursor leave detection

**Complexity:** Medium
**Dependencies:** pyqtgraph, PyQt6

---

### Phase 6: Orchestrator (200 LOC)

#### 8. panel1_main.py (200 LOC)
**Purpose:** Wire all modules together

**Structure:**
```python
class Panel1(QtWidgets.QWidget, ThemeAwareMixin):
    timeframeChanged = QtCore.pyqtSignal(str)

    def __init__(self):
        # Create UI widgets
        self._build_ui()

        # Create submodules
        self.equity_state = EquityStateManager()
        self.timeframe_mgr = TimeframeManager()
        self.pnl_calc = PnLCalculator()
        self.equity_chart = EquityChart(container)
        self.hover_handler = HoverHandler(plot_widget)

        # Wire signals
        self._connect_signals()

        # Load initial equity
        self._load_equity_for_mode()

    def _connect_signals(self):
        # Wire module signals
        self.equity_state.equityCurveLoaded.connect(self._on_equity_loaded)
        self.hover_handler.hoverPointChanged.connect(self._on_hover_point)
        # ... etc

    # Backwards-compatible API
    def set_trading_mode(self, mode: str, account: str):
        # Delegate to equity_state

    def set_timeframe(self, tf: str):
        # Delegate to timeframe_mgr, replot

    def set_account_balance(self, balance: float):
        # Update balance label

    def set_connection_status(self, connected: bool):
        # Update connection icon
```

**Features:**
- Thin orchestration layer
- Signal routing
- Backwards-compatible API
- Module coordination

**Complexity:** Low (wiring only)
**Dependencies:** All submodules

---

## Implementation Phases

### Phase 1: Foundation (Est. 2-3 hours)
- ✅ Create directory structure
- helpers.py
- masked_frame.py
- pnl_calculator.py

### Phase 2: Timeframe Management (Est. 2 hours)
- timeframe_manager.py

### Phase 3: State Management (Est. 3-4 hours) - **CRITICAL**
- equity_state.py
- **Risk:** High (thread safety, async loading)

### Phase 4: Chart Rendering (Est. 4-5 hours)
- equity_chart.py
- **Risk:** Medium (PyQtGraph complexity)

### Phase 5: Hover Interactions (Est. 2-3 hours)
- hover_handler.py

### Phase 6: Orchestrator (Est. 2-3 hours)
- panel1_main.py
- __init__.py
- Integration testing

---

## Critical Considerations

### Thread Safety (CRITICAL)
**Challenge:** Equity curves accessed from multiple threads
- Main thread: UI updates
- Background thread: Database loading (QtConcurrent)

**Solution:** QMutex protection in EquityStateManager
```python
self._equity_mutex.lock()
try:
    # Access _equity_curves
finally:
    self._equity_mutex.unlock()
```

### Binary Search Efficiency
**Challenge:** Hover/scrubbing needs fast point lookups
**Solution:** Binary search in O(log n) time
- timeframe_manager.py: filter_points_for_timeframe()
- hover_handler.py: _find_nearest_index()

### PyQtGraph Integration
**Challenge:** PlotWidget must be added to layout correctly
**Solution:** Proper parent/layout attachment
```python
self._plot = pg.PlotWidget(parent=container)
container.layout().addWidget(self._plot)
```

### Animation Performance
**Challenge:** 25 FPS pulse must not block UI
**Solution:** Lightweight pulse_tick handler
- Update only endpoint brush
- Minimal calculations per frame

---

## Testing Strategy

Each module independently testable:

```python
# helpers.py
def test_fmt_money():
    assert fmt_money(1234.56) == "$1,234.56"
    assert fmt_money(None) == "--"

# pnl_calculator.py
def test_calculate_pnl():
    result = PnLCalculator.calculate_pnl(11000.0, 10000.0)
    assert result["amount"] == 1000.0
    assert result["percentage"] == 10.0
    assert result["is_positive"] is True

# timeframe_manager.py
def test_filter_points():
    points = [(1000, 100.0), (2000, 110.0), (3000, 120.0)]
    filtered = TimeframeManager.filter_points_for_timeframe(points, "1D", 3600)
    assert len(filtered) > 0

# equity_state.py (with mocking)
def test_add_balance_point():
    manager = EquityStateManager()
    manager.set_mode("SIM", "Test1")
    manager.add_balance_point(1000.0, 1234567890)
    curve = manager.get_equity_curve("SIM", "Test1")
    assert len(curve) == 1
```

---

## Migration Plan

1. **Feature Flag** (Optional)
   - Add `USE_NEW_PANEL1` in settings
   - Test both versions in parallel

2. **Gradual Rollout**
   - Test with SIM mode first
   - Monitor for regressions
   - Migrate LIVE mode

3. **Cleanup**
   - Remove old `panels/panel1.py`
   - Update imports
   - Update documentation

---

## Summary

| Module | LOC | Complexity | Phase |
|--------|-----|------------|-------|
| helpers.py | 50 | Low | 1 |
| masked_frame.py | 50 | Low | 1 |
| pnl_calculator.py | 200 | Medium | 1 |
| timeframe_manager.py | 220 | Medium | 2 |
| equity_state.py | 320 | High | 3 |
| equity_chart.py | 400 | High | 4 |
| hover_handler.py | 250 | Medium | 5 |
| panel1_main.py | 200 | Low | 6 |
| **TOTAL** | **1,690** | - | - |

**Original:** 1,820 LOC monolith
**New Architecture:** 1,690 LOC across 8 focused modules
**Reduction:** 7% (due to elimination of redundancy and clearer separation)

---

**Last Updated:** 2025-11-14
**Status:** Specification Complete - Ready for Implementation
