# Panel1 Integration Test Plan

**Date:** 2025-11-14
**Status:** Ready for Testing
**Branch:** `claude/get-latitude-01A6fKJ23ratoLx1NPScuLRb`

---

## Executive Summary

This document outlines the comprehensive test plan for integrating the newly decomposed Panel1 architecture into APPSIERRA. The Panel1 monolith (1,820 LOC) has been successfully decomposed into 8 focused modules (2,459 LOC). Now we must verify that the new architecture works correctly in the production environment.

---

## Test Objectives

### Primary Goals:
1. ✅ **Verify Backwards Compatibility** - Ensure old Panel1 API still works
2. ✅ **Validate Module Integration** - Confirm all 8 modules work together
3. ✅ **Test Data Flow** - Verify equity data flows through all layers
4. ✅ **Check Thread Safety** - Validate QMutex protections work correctly
5. ✅ **Performance Validation** - Ensure no performance regressions

### Secondary Goals:
6. Test all timeframes (LIVE, 1D, 1W, 1M, 3M, YTD)
7. Test all modes (DEBUG, SIM, LIVE)
8. Test hover interactions
9. Test chart animations
10. Test error handling

---

## Pre-Test Checklist

### Environment Setup:
- [ ] Python 3.11+ installed
- [ ] PyQt6 installed (`pip install PyQt6`)
- [ ] pyqtgraph installed (`pip install pyqtgraph`)
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Database initialized
- [ ] Test data available

### Code Verification:
- [x] All 8 Panel1 modules committed
- [x] `panels/panel1/__init__.py` exports `Panel1`
- [x] No syntax errors
- [x] Type hints valid
- [x] Documentation complete

---

## Test Suite 1: Import & Instantiation

### Test 1.1: Import Panel1
**Objective:** Verify Panel1 can be imported from new location

```python
from panels.panel1 import Panel1
```

**Expected:**
- No import errors
- Panel1 class is available
- All submodules load correctly

**Pass Criteria:** Import succeeds without errors

---

### Test 1.2: Instantiate Panel1
**Objective:** Verify Panel1 can be instantiated

```python
from PyQt6 import QtWidgets
app = QtWidgets.QApplication([])

from panels.panel1 import Panel1
panel = Panel1()
```

**Expected:**
- Panel1 instance created
- All submodules initialized
- UI widgets created
- No exceptions

**Pass Criteria:** Instantiation succeeds, panel is valid QWidget

---

### Test 1.3: Check Module Integration
**Objective:** Verify all 8 submodules are properly integrated

```python
panel = Panel1()

# Check module instances
assert panel._equity_state is not None, "EquityStateManager missing"
assert panel._equity_chart is not None, "EquityChart missing"
assert panel._hover_handler is not None, "HoverHandler missing"
assert panel._equity_chart.has_plot(), "Chart plot missing"
```

**Expected:**
- `_equity_state`: EquityStateManager instance
- `_equity_chart`: EquityChart instance
- `_hover_handler`: HoverHandler instance
- Chart has PlotWidget

**Pass Criteria:** All module instances exist and are properly initialized

---

## Test Suite 2: Public API Compatibility

### Test 2.1: set_trading_mode()
**Objective:** Test mode switching

```python
panel = Panel1()

# Test SIM mode
panel.set_trading_mode("SIM", "Sim1")
assert panel._current_mode == "SIM"
assert panel.mode_badge.text() == "SIM"

# Test LIVE mode
panel.set_trading_mode("LIVE", "Live1")
assert panel._current_mode == "LIVE"
assert panel.mode_badge.text() == "LIVE"

# Test DEBUG mode
panel.set_trading_mode("DEBUG")
assert panel._current_mode == "DEBUG"
assert panel.mode_badge.text() == "DEBUG"
```

**Pass Criteria:** Mode badge updates, internal state correct

---

### Test 2.2: set_timeframe()
**Objective:** Test all 6 timeframes

```python
panel = Panel1()

timeframes = ["LIVE", "1D", "1W", "1M", "3M", "YTD"]

for tf in timeframes:
    panel.set_timeframe(tf)
    assert panel._current_timeframe == tf
    # Signal should be emitted
```

**Pass Criteria:**
- All timeframes accepted
- `timeframeChanged` signal emitted
- Chart updates correctly

---

### Test 2.3: set_account_balance()
**Objective:** Test balance display

```python
panel = Panel1()

panel.set_account_balance(10000.0)
assert panel.lbl_balance.text() == "$10,000.00"

panel.set_account_balance(12345.67)
assert panel.lbl_balance.text() == "$12,345.67"

panel.set_account_balance(None)
assert panel.lbl_balance.text() == "--"
```

**Pass Criteria:** Balance label displays formatted values correctly

---

### Test 2.4: update_equity_series_from_balance()
**Objective:** Test equity curve updates

```python
import time

panel = Panel1()
panel.set_trading_mode("SIM", "Test1")

# Add 10 balance points
for i in range(10):
    balance = 10000.0 + (i * 10.0)
    panel.update_equity_series_from_balance(balance, mode="SIM")
    time.sleep(0.1)

# Check that points were added
curve = panel._equity_state.get_active_curve()
assert len(curve) > 0, "No equity points added"

# Check that chart updated
# (visual inspection required)
```

**Pass Criteria:**
- Points added to equity state
- Chart displays line
- No errors

---

### Test 2.5: set_pnl_for_timeframe()
**Objective:** Test PnL display

```python
panel = Panel1()

# Test positive PnL
panel.set_pnl_for_timeframe(50.0, 0.5, up=True)
assert "+ $50.00" in panel.lbl_pnl.text()
assert "0.50%" in panel.lbl_pnl.text()

# Test negative PnL
panel.set_pnl_for_timeframe(-30.0, -0.3, up=False)
assert "- $30.00" in panel.lbl_pnl.text()
assert "0.30%" in panel.lbl_pnl.text()

# Test neutral PnL
panel.set_pnl_for_timeframe(0.0, 0.0, up=None)
assert "$0.00" in panel.lbl_pnl.text()
```

**Pass Criteria:** PnL label displays correct values with correct colors

---

## Test Suite 3: Data Flow & State Management

### Test 3.1: Equity State Thread Safety
**Objective:** Verify QMutex protection works

```python
import threading
import time

panel = Panel1()
panel.set_trading_mode("SIM", "Test1")

# Concurrent writes
def writer(thread_id):
    for i in range(100):
        balance = 10000.0 + (thread_id * 100) + i
        panel.update_equity_series_from_balance(balance, mode="SIM")
        time.sleep(0.001)

threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]

for t in threads:
    t.start()

for t in threads:
    t.join()

# Check that all points were added (no data loss)
curve = panel._equity_state.get_active_curve()
# Should have ~1000 points (10 threads * 100 points)
# (Some may be deduplicated by time cutoff)
```

**Pass Criteria:** No crashes, no data corruption, all points accessible

---

### Test 3.2: Timeframe Filtering
**Objective:** Verify binary search filtering works correctly

```python
import time

panel = Panel1()
panel.set_trading_mode("SIM", "Test1")

# Add 100 points over 2 hours
now = time.time()
for i in range(100):
    timestamp = now - (2 * 3600) + (i * 72)  # Every 72 seconds
    balance = 10000.0 + i
    panel._equity_state.add_balance_point(balance, timestamp, "SIM", "Test1")

# Test LIVE (1 hour window)
panel.set_timeframe("LIVE")
curve = panel._equity_state.get_active_curve()

from panels.panel1.timeframe_manager import TimeframeManager
filtered = TimeframeManager.filter_points_for_timeframe(curve, "LIVE")

# Should have ~50 points (last hour out of 2 hours)
assert 40 <= len(filtered) <= 60, f"Expected ~50 points, got {len(filtered)}"

# Test 1D (24 hour window - all points)
panel.set_timeframe("1D")
filtered = TimeframeManager.filter_points_for_timeframe(curve, "1D")
assert len(filtered) == 100, f"Expected 100 points, got {len(filtered)}"
```

**Pass Criteria:** Correct number of points for each timeframe

---

### Test 3.3: PnL Calculations
**Objective:** Verify PnL calculator works correctly

```python
import time

panel = Panel1()
panel.set_trading_mode("SIM", "Test1")

# Add baseline point (1 hour ago)
now = time.time()
baseline_time = now - 3600
panel._equity_state.add_balance_point(10000.0, baseline_time, "SIM", "Test1")

# Add current point
panel._equity_state.add_balance_point(10500.0, now, "SIM", "Test1")

# Set timeframe to LIVE (1 hour window)
panel.set_timeframe("LIVE")

# Trigger PnL calculation
curve = panel._equity_state.get_active_curve()
panel._update_pnl_for_timeframe(curve)

# Check PnL values
assert panel._pnl_val == 500.0, f"Expected 500.0, got {panel._pnl_val}"
assert panel._pnl_pct == 5.0, f"Expected 5.0%, got {panel._pnl_pct}%"
assert panel._pnl_up == True, "Expected positive PnL"
```

**Pass Criteria:** PnL calculations are accurate

---

## Test Suite 4: Chart Rendering

### Test 4.1: Chart Initialization
**Objective:** Verify PyQtGraph chart renders

```python
panel = Panel1()

# Check that chart exists
assert panel._equity_chart.has_plot(), "Chart has no plot"

# Check that plot widget is in layout
assert panel._equity_chart.get_plot_widget() is not None
```

**Pass Criteria:** Chart widget exists and is visible

---

### Test 4.2: Chart Animation
**Objective:** Verify pulse animation works

```python
panel = Panel1()

# Start animation
panel._equity_chart.start_animation()

# Check that timer is running
# (Visual inspection required)

# Stop animation
panel._equity_chart.stop_animation()
```

**Pass Criteria:**
- Animation starts without errors
- Endpoint pulses (visual)
- Sonar rings expand (visual)
- Glow effect pulses (visual)

---

### Test 4.3: Chart Data Rendering
**Objective:** Verify chart displays data

```python
import time

panel = Panel1()
panel.set_trading_mode("SIM", "Test1")

# Add test data
now = time.time()
points = [(now - (i * 60), 10000.0 + (i * 10)) for i in range(60)]

for timestamp, balance in points:
    panel._equity_state.add_balance_point(balance, timestamp, "SIM", "Test1")

# Set timeframe and replot
panel.set_timeframe("LIVE")

# Visual inspection: Should see upward sloping line
```

**Pass Criteria:**
- Line visible on chart
- Line matches data points
- Trails and glow visible
- Endpoint at correct position

---

## Test Suite 5: Hover Interactions

### Test 5.1: Hover Line
**Objective:** Verify hover line appears

```python
panel = Panel1()
panel.set_trading_mode("SIM", "Test1")

# Add test data
# ... (add points)

# Simulate mouse move
# (Requires GUI interaction - manual test)
```

**Pass Criteria:**
- Hover line appears on mouse move
- Timestamp text displays
- Line follows mouse
- Disappears on mouse leave

---

### Test 5.2: Hover PnL Calculation
**Objective:** Verify hover updates balance/PnL

```python
panel = Panel1()

# Setup test data
# ... (add points)

# Hover over point
# (Manual test - check that balance/PnL labels update)
```

**Pass Criteria:**
- Balance label updates to hovered point
- PnL label shows PnL vs baseline
- Colors change based on PnL direction

---

## Test Suite 6: Integration with MainWindow

### Test 6.1: Panel1 in App Manager
**Objective:** Verify Panel1 works in main application

```python
# In core/app_manager.py

# This should already work:
from panels.panel1 import Panel1
self.panel_balance = Panel1()
```

**Pass Criteria:**
- Panel1 loads in MainWindow
- No crashes
- Displays correctly in layout

---

### Test 6.2: Signal Connectivity
**Objective:** Verify SignalBus integration

```python
# Test that Panel1 receives balance updates from SignalBus

from core.signal_bus import get_signal_bus
signal_bus = get_signal_bus()

# Emit balance update
signal_bus.balanceUpdated.emit(10500.0, "Sim1")

# Check that Panel1 received update
# (Check balance label, equity curve)
```

**Pass Criteria:**
- Panel1 receives SignalBus events
- Updates correctly
- No errors

---

## Test Suite 7: Performance

### Test 7.1: Startup Time
**Objective:** Verify no regression in startup time

```python
import time

start = time.time()
panel = Panel1()
elapsed = time.time() - start

print(f"Panel1 startup time: {elapsed:.3f}s")

# Should be < 1 second
assert elapsed < 1.0, f"Startup too slow: {elapsed:.3f}s"
```

**Pass Criteria:** Startup time < 1 second

---

### Test 7.2: Chart Rendering Performance
**Objective:** Verify chart renders smoothly

```python
import time

panel = Panel1()

# Add 1000 points
now = time.time()
for i in range(1000):
    panel._equity_state.add_balance_point(
        10000.0 + i, now - (1000 - i), "SIM", "Test1"
    )

# Measure replot time
curve = panel._equity_state.get_active_curve()

start = time.time()
panel._equity_chart.replot(curve, "1D")
elapsed = time.time() - start

print(f"Chart replot time: {elapsed:.3f}s")

# Should be < 100ms
assert elapsed < 0.1, f"Replot too slow: {elapsed:.3f}s"
```

**Pass Criteria:** Replot time < 100ms for 1000 points

---

### Test 7.3: Binary Search Performance
**Objective:** Verify O(log n) performance

```python
from panels.panel1.timeframe_manager import TimeframeManager
import time

# Create large dataset
points = [(i, 10000.0 + i) for i in range(100000)]

# Measure filtering time
start = time.time()
filtered = TimeframeManager.filter_points_for_timeframe(points, "LIVE")
elapsed = time.time() - start

print(f"Filter time (100k points): {elapsed:.3f}s")

# Should be very fast (< 10ms) due to binary search
assert elapsed < 0.01, f"Filter too slow: {elapsed:.3f}s"
```

**Pass Criteria:** Filter time < 10ms for 100k points

---

## Test Suite 8: Error Handling

### Test 8.1: Invalid Timeframe
**Objective:** Verify graceful handling of invalid input

```python
panel = Panel1()

# Try invalid timeframe
panel.set_timeframe("INVALID")

# Should log warning, not crash
# Current timeframe should remain unchanged
```

**Pass Criteria:** No crash, warning logged

---

### Test 8.2: Missing PyQtGraph
**Objective:** Verify graceful degradation

```python
# Mock missing pyqtgraph
import sys
sys.modules['pyqtgraph'] = None

from panels.panel1 import Panel1
panel = Panel1()

# Should create panel without chart
assert not panel._equity_chart.has_plot()
```

**Pass Criteria:** Panel loads without chart, no crash

---

### Test 8.3: Database Error
**Objective:** Verify error handling for DB failures

```python
panel = Panel1()
panel.set_trading_mode("SIM", "NonExistent")

# Try to load equity curve for non-existent account
# Should handle gracefully
```

**Pass Criteria:** No crash, empty curve returned

---

## Test Execution Plan

### Phase 1: Automated Tests (Day 1)
1. Run `test_panel1_integration.py`
2. Fix any failing tests
3. Document issues

### Phase 2: Manual GUI Tests (Day 2)
1. Test all timeframes visually
2. Test hover interactions
3. Test chart animations
4. Test mode switching

### Phase 3: Integration Tests (Day 3)
1. Test in MainWindow
2. Test with live data
3. Test signal connectivity
4. Performance profiling

### Phase 4: Regression Tests (Day 4)
1. Compare with old Panel1
2. Verify no regressions
3. Document differences

---

## Success Criteria

### Must Pass:
✅ All import tests
✅ All instantiation tests
✅ All public API tests
✅ Thread safety tests
✅ Data flow tests
✅ Performance benchmarks

### Should Pass:
- All chart rendering tests
- All hover interaction tests
- All error handling tests
- All regression tests

### Nice to Have:
- 100% test coverage
- Performance improvements over old Panel1
- No visual regressions

---

## Known Issues & Workarounds

### Issue 1: PyQt6 Not Available in Test Environment
**Workaround:** Run tests in development environment with PyQt6 installed

### Issue 2: Database Not Initialized
**Workaround:** Run `python -m core.database` to initialize

---

## Test Automation Script

See: `test_panel1_integration.py`

Run with:
```bash
python test_panel1_integration.py
```

---

## Next Steps After Testing

1. **If tests pass:**
   - Update documentation
   - Create migration plan
   - Add feature flag
   - Deploy to staging

2. **If tests fail:**
   - Document failures
   - Create bug tickets
   - Fix issues
   - Re-test

3. **After deployment:**
   - Monitor performance
   - Gather user feedback
   - Remove old Panel1 monolith
   - Update imports

---

**Last Updated:** 2025-11-14
**Status:** Ready for Testing
**Next:** Execute test suite in development environment
