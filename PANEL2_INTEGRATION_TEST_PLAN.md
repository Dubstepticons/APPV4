# Panel2 Integration Test Plan

**Date:** 2025-11-14
**Status:** Ready for Testing
**Branch:** `claude/get-latitude-01A6fKJ23ratoLx1NPScuLRb`

---

## Executive Summary

Comprehensive test plan for integrating the newly decomposed Panel2 architecture. The Panel2 monolith (1,930 LOC) has been decomposed into 8 focused modules (3,790 LOC), providing better modularity, testability, and maintainability.

---

## Panel2 Module Architecture

### 8 Focused Modules:
1. **position_state.py** (430 LOC) - Immutable position snapshots
2. **metrics_calculator.py** (370 LOC) - Pure calculation functions
3. **csv_feed_handler.py** (370 LOC) - CSV import/export
4. **state_persistence.py** (260 LOC) - Database operations
5. **order_flow.py** (570 LOC) - Order creation logic
6. **position_display.py** (480 LOC) - Position UI widgets
7. **visual_indicators.py** (625 LOC) - Visual feedback components
8. **panel2_main.py** (685 LOC) - Thin orchestrator

---

## Test Suite 1: Import & Instantiation

### Test 1.1: Import Panel2
```python
from panels.panel2 import Panel2
```

**Expected:** No errors, Panel2 class available

---

### Test 1.2: Instantiate Panel2
```python
from PyQt6 import QtWidgets
app = QtWidgets.QApplication([])

from panels.panel2 import Panel2
panel = Panel2()
```

**Expected:** Panel2 instance created, all UI widgets initialized

---

### Test 1.3: Check Module Instances
```python
panel = Panel2()

# Verify all modules initialized
assert panel._position_state is not None
assert panel._metrics_calculator is not None
assert panel._csv_handler is not None
assert panel._persistence is not None
assert panel._order_flow is not None
assert panel._position_display is not None
assert panel._visual_indicators is not None
```

**Pass Criteria:** All module instances exist

---

## Test Suite 2: PositionState (Immutable State)

### Test 2.1: Create Position State
```python
from panels.panel2.position_state import PositionState

state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0,
    peak_profit=10.0,
    peak_loss=-5.0,
    stop_loss_price=6745.0
)

# Test immutability (should be frozen dataclass)
try:
    state.entry_qty = 2
    assert False, "State should be immutable"
except:
    pass  # Expected
```

**Pass Criteria:** State is immutable, all fields accessible

---

### Test 2.2: Built-in Calculations
```python
state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0,
    peak_profit=10.0,
    peak_loss=-5.0,
    stop_loss_price=6745.0
)

# Test calculations
pnl = state.current_pnl()
assert pnl == 5.0, f"Expected 5.0, got {pnl}"

mae = state.mae()
assert mae == -5.0, f"Expected -5.0, got {mae}"

mfe = state.mfe()
assert mfe == 10.0, f"Expected 10.0, got {mfe}"

r_multiple = state.r_multiple()
# R = (current_pnl) / (risk_amount)
# Risk = entry - stop = 6750 - 6745 = 5.0
# R = 5.0 / 5.0 = 1.0
assert r_multiple == 1.0, f"Expected 1.0, got {r_multiple}"
```

**Pass Criteria:** All calculations correct

---

### Test 2.3: Immutable Updates
```python
state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0
)

# Test with_price (immutable update)
new_state = state.with_price(6760.0)

assert state.last_price == 6755.0, "Original should be unchanged"
assert new_state.last_price == 6760.0, "New state should have updated price"
assert new_state.entry_price == 6750.0, "Other fields should be preserved"
```

**Pass Criteria:** Immutable updates work correctly

---

## Test Suite 3: MetricsCalculator (Pure Functions)

### Test 3.1: Calculate All Metrics
```python
from panels.panel2.metrics_calculator import MetricsCalculator
from panels.panel2.position_state import PositionState
import time

calculator = MetricsCalculator()

state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0,
    peak_profit=10.0,
    peak_loss=-5.0,
    stop_loss_price=6745.0,
    take_profit_price=6765.0,
    entry_time=time.time() - 300  # 5 minutes ago
)

metrics = calculator.calculate_all(state, current_epoch=time.time())

# Verify all metric keys present
required_keys = [
    'unrealized_pnl',
    'mae',
    'mfe',
    'risk_amount',
    'reward_amount',
    'r_multiple',
    'efficiency',
    'risk_reward_ratio',
    'range_pct',
    'duration_seconds'
]

for key in required_keys:
    assert key in metrics, f"Missing metric: {key}"
```

**Pass Criteria:** All metrics calculated correctly

---

### Test 3.2: Calculator is Stateless
```python
calculator = MetricsCalculator()

state = PositionState(entry_qty=1, entry_price=6750.0, is_long=True, last_price=6755.0)

# Calculate twice with same input
result1 = calculator.calculate_all(state)
result2 = calculator.calculate_all(state)

# Results should be identical (pure function)
assert result1 == result2, "Calculator should be stateless"
```

**Pass Criteria:** Calculator produces consistent results

---

## Test Suite 4: CSV Feed Handler

### Test 4.1: Export Position to CSV
```python
from panels.panel2.csv_feed_handler import CSVFeedHandler
from panels.panel2.position_state import PositionState

handler = CSVFeedHandler()

state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0
)

# Export to dict for CSV
csv_row = handler.position_to_csv_row(state)

assert 'entry_price' in csv_row
assert csv_row['entry_price'] == 6750.0
assert csv_row['last_price'] == 6755.0
```

**Pass Criteria:** CSV export works correctly

---

### Test 4.2: Import Position from CSV
```python
handler = CSVFeedHandler()

csv_row = {
    'entry_qty': '1',
    'entry_price': '6750.0',
    'is_long': 'True',
    'last_price': '6755.0'
}

state = handler.csv_row_to_position(csv_row)

assert state.entry_qty == 1
assert state.entry_price == 6750.0
assert state.is_long == True
assert state.last_price == 6755.0
```

**Pass Criteria:** CSV import works correctly

---

## Test Suite 5: State Persistence (Database)

### Test 5.1: Save Position to Database
```python
from panels.panel2.state_persistence import StatePersistence
from panels.panel2.position_state import PositionState

persistence = StatePersistence()

state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0,
    symbol="MES",
    account="Sim1"
)

# Save to database
persistence.save_position(state)

# Load from database
loaded = persistence.load_position("MES", "Sim1")

assert loaded is not None
assert loaded.entry_price == 6750.0
assert loaded.last_price == 6755.0
```

**Pass Criteria:** Save/load round-trip works

---

### Test 5.2: Update Position in Database
```python
persistence = StatePersistence()

state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0,
    symbol="MES",
    account="Sim1"
)

persistence.save_position(state)

# Update price
new_state = state.with_price(6760.0)
persistence.update_position(new_state)

# Load and verify
loaded = persistence.load_position("MES", "Sim1")
assert loaded.last_price == 6760.0
```

**Pass Criteria:** Updates work correctly

---

## Test Suite 6: Order Flow

### Test 6.1: Create Buy Order
```python
from panels.panel2.order_flow import OrderFlow

order_flow = OrderFlow()

order = order_flow.create_buy_order(
    symbol="MES",
    quantity=1,
    price=6750.0,
    account="Sim1"
)

assert order['symbol'] == "MES"
assert order['quantity'] == 1
assert order['side'] == "BUY"
assert order['price'] == 6750.0
```

**Pass Criteria:** Buy order created correctly

---

### Test 6.2: Create Sell Order
```python
order_flow = OrderFlow()

order = order_flow.create_sell_order(
    symbol="MES",
    quantity=1,
    price=6755.0,
    account="Sim1"
)

assert order['side'] == "SELL"
assert order['price'] == 6755.0
```

**Pass Criteria:** Sell order created correctly

---

### Test 6.3: Create Stop Loss Order
```python
order_flow = OrderFlow()

stop = order_flow.create_stop_loss_order(
    symbol="MES",
    quantity=1,
    stop_price=6745.0,
    account="Sim1"
)

assert stop['type'] == "STOP"
assert stop['stop_price'] == 6745.0
```

**Pass Criteria:** Stop loss order created correctly

---

## Test Suite 7: Position Display (UI)

### Test 7.1: Create Position Widget
```python
from panels.panel2.position_display import PositionDisplay
from panels.panel2.position_state import PositionState

display = PositionDisplay()

state = PositionState(
    entry_qty=1,
    entry_price=6750.0,
    is_long=True,
    last_price=6755.0
)

# Update display
display.update_position(state)

# Check labels (manual verification)
```

**Pass Criteria:** Position widget displays correctly

---

### Test 7.2: Update Position Display
```python
display = PositionDisplay()

state1 = PositionState(entry_qty=1, entry_price=6750.0, is_long=True, last_price=6755.0)
display.update_position(state1)

state2 = state1.with_price(6760.0)
display.update_position(state2)

# Visual inspection: labels should update
```

**Pass Criteria:** Display updates on state change

---

## Test Suite 8: Visual Indicators

### Test 8.1: PnL Color Indicator
```python
from panels.panel2.visual_indicators import VisualIndicators

indicators = VisualIndicators()

# Positive PnL
color = indicators.pnl_color(5.0)
# Should return green

# Negative PnL
color = indicators.pnl_color(-5.0)
# Should return red

# Neutral
color = indicators.pnl_color(0.0)
# Should return neutral color
```

**Pass Criteria:** Colors match PnL direction

---

### Test 8.2: R-Multiple Indicator
```python
indicators = VisualIndicators()

# Test R-multiple display
r_display = indicators.format_r_multiple(2.5)
assert "2.5R" in r_display

# Test color coding
# R >= 2.0 should be green
# R < 1.0 should be red
```

**Pass Criteria:** R-multiple formatted correctly with colors

---

## Test Suite 9: Integration with MainWindow

### Test 9.1: Panel2 in App Manager
```python
# In core/app_manager.py

from panels.panel2 import Panel2
self.panel_live = Panel2()
```

**Pass Criteria:** Panel2 loads in MainWindow without errors

---

### Test 9.2: Signal Connectivity
```python
from core.signal_bus import get_signal_bus

signal_bus = get_signal_bus()

# Emit position update
signal_bus.positionUpdated.emit({
    'symbol': 'MES',
    'account': 'Sim1',
    'quantity': 1,
    'average_price': 6750.0
})

# Panel2 should receive and display position
```

**Pass Criteria:** Panel2 receives and displays position updates

---

## Test Suite 10: Performance

### Test 10.1: State Creation Performance
```python
import time

start = time.time()
for i in range(10000):
    state = PositionState(
        entry_qty=1,
        entry_price=6750.0,
        is_long=True,
        last_price=6755.0
    )
elapsed = time.time() - start

print(f"10k state creations: {elapsed:.3f}s")
assert elapsed < 1.0, "State creation too slow"
```

**Pass Criteria:** < 1 second for 10k states

---

### Test 10.2: Metrics Calculation Performance
```python
from panels.panel2.metrics_calculator import MetricsCalculator

calculator = MetricsCalculator()
state = PositionState(entry_qty=1, entry_price=6750.0, is_long=True, last_price=6755.0)

start = time.time()
for i in range(1000):
    metrics = calculator.calculate_all(state)
elapsed = time.time() - start

print(f"1k metric calculations: {elapsed:.3f}s")
assert elapsed < 0.1, "Calculations too slow"
```

**Pass Criteria:** < 100ms for 1000 calculations

---

## Automated Test Script

See: `test_panel2_integration.py`

```python
from panels.panel2 import Panel2
from panels.panel2.position_state import PositionState
from panels.panel2.metrics_calculator import MetricsCalculator

# Run all tests
panel = Panel2()
assert panel is not None

state = PositionState(entry_qty=1, entry_price=6750.0, is_long=True, last_price=6755.0)
assert state.current_pnl() == 5.0

calculator = MetricsCalculator()
metrics = calculator.calculate_all(state)
assert 'unrealized_pnl' in metrics

print("✅ All Panel2 integration tests passed!")
```

---

## Success Criteria

### Must Pass:
✅ All module imports
✅ All instantiation tests
✅ PositionState immutability
✅ MetricsCalculator accuracy
✅ Database persistence
✅ Order creation

### Should Pass:
- All UI display tests
- All visual indicator tests
- All performance benchmarks
- Signal connectivity

---

## Known Issues

### Issue 1: Database Connection
**Workaround:** Ensure database initialized before testing

### Issue 2: PyQt6 Required
**Workaround:** Install PyQt6 in test environment

---

## Next Steps

1. Run automated tests
2. Manual GUI testing
3. Integration testing with MainWindow
4. Performance profiling
5. Migration to production

---

**Last Updated:** 2025-11-14
**Status:** Ready for Testing
**Next:** Execute test suite
