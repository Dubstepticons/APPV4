# Panel1.py Structural Analysis - Complete Documentation

Generated: November 14, 2025  
Source File: `/home/user/APPV4/panels/panel1.py` (1820 lines)

---

## 4-Document Analysis Set

This comprehensive analysis breaks down the complex panel1.py file into:
1. Functional areas
2. Proposed modules
3. Data dependencies and flow
4. Thread safety mechanisms
5. Quick reference lookup

### Document 1: PANEL1_STRUCTURE_ANALYSIS.md (839 lines)
**Purpose**: Detailed structural breakdown  
**Contains**:
- Overview of Panel1 architecture
- 9 Functional Areas with detailed analysis:
  1. Equity Chart Rendering & Animation
  2. Balance Display
  3. Timeframe Management
  4. Theme Switching & Color Updates
  5. PnL Display & Calculation
  6. Equity Curve State Management
  7. Hover/Scrubbing (Interactive Timeline)
  8. Signal Wiring & Connections
  9. Mode Switching
- Critical dependencies and shared state
- Proposed module decomposition (8-9 modules)
- Initialization order
- Migration notes
- Summary table

**When to Use**:
- Understanding full architecture
- Planning refactoring
- Learning about specific functional area
- Understanding module boundaries

### Document 2: PANEL1_DEPENDENCIES_FLOWCHART.md (493 lines)
**Purpose**: Visual data flow and dependencies  
**Contains**:
- Module dependency graph (ASCII diagram)
- 4 Critical data flows:
  1. Balance Update flow
  2. Timeframe Change flow
  3. Mode Switch flow
  4. Hover/Scrubbing flow
- State update synchronization
- Thread safety boundaries (Main thread vs Background)
- Module integration points (1-8)
- API contracts and public methods
- Signal connections overview

**When to Use**:
- Tracing data flow for debugging
- Understanding thread safety
- Planning modifications
- Checking impact of changes
- Reviewing module interfaces

### Document 3: PANEL1_QUICK_REFERENCE.md (423 lines)
**Purpose**: Quick lookup and implementation guide  
**Contains**:
- File structure overview (line ranges)
- Method organization by functional area (45+ methods)
- Critical state variables with types
- Signal connections table
- Data dependencies map
- 4 Critical paths (must not break)
- Thread safety checklist
- Performance considerations
- Common patterns (4)
- Common gotchas (5)
- Testing checklist

**When to Use**:
- Finding a method quickly
- Checking state variable purpose
- Verifying thread safety before modification
- Looking up signal connections
- Planning tests

### Document 4: PANEL1_ANALYSIS_SUMMARY.md (370 lines)
**Purpose**: Executive summary and recommendations  
**Contains**:
- High-level overview
- Key findings summary
- Architecture complexity assessment
- Critical state structures
- Proposed module table
- Critical findings (4 issues)
- Module ownership guidelines
- Thread safety summary
- Migration path (4 phases, 7-9 days)
- Impact analysis
- Code quality observations
- Next steps (4 time horizons)
- Summary statistics
- Conclusion

**When to Use**:
- Getting oriented quickly
- Presenting to team
- Planning refactoring effort
- Decision-making on architecture

---

## Quick Navigation

### By Use Case

**"I want to understand Panel1 quickly"**
1. Read PANEL1_ANALYSIS_SUMMARY.md (10 min)
2. Skim PANEL1_QUICK_REFERENCE.md tables (5 min)
3. Review relevant sections of PANEL1_STRUCTURE_ANALYSIS.md (10 min)

**"I need to modify a method"**
1. Find method in PANEL1_QUICK_REFERENCE.md (2 min)
2. Check dependencies in PANEL1_DEPENDENCIES_FLOWCHART.md (5 min)
3. Review critical paths in PANEL1_QUICK_REFERENCE.md (3 min)
4. Check thread safety checklist (1 min)
5. Implement and test per testing checklist (variable)

**"I want to refactor into modules"**
1. Read PANEL1_ANALYSIS_SUMMARY.md "Migration Path" (5 min)
2. Study module ownership in PANEL1_ANALYSIS_SUMMARY.md (10 min)
3. Review proposed modules in PANEL1_STRUCTURE_ANALYSIS.md (15 min)
4. Check all interfaces in PANEL1_DEPENDENCIES_FLOWCHART.md (10 min)
5. Create Phase 1 stubs using guidance (2-3 hours)

**"I found a bug in threading"**
1. Find affected method in PANEL1_QUICK_REFERENCE.md (2 min)
2. Check thread safety checklist (2 min)
3. Review Thread Safety Boundaries in PANEL1_DEPENDENCIES_FLOWCHART.md (5 min)
4. Check Critical Paths for related areas (5 min)
5. Fix and verify per testing checklist (variable)

**"I need to add a new feature"**
1. Review PANEL1_ANALYSIS_SUMMARY.md "Critical Findings" (5 min)
2. Check module impact in PANEL1_STRUCTURE_ANALYSIS.md (10 min)
3. Trace data flow in PANEL1_DEPENDENCIES_FLOWCHART.md (10 min)
4. Update affected methods in PANEL1_QUICK_REFERENCE.md (2 min)
5. Implement with proper signal routing (variable)

---

## Key Concepts Explained

### Scoped Equity Curves
```python
self._equity_curves: dict[(mode, account), list[(timestamp, balance)]]
```
- Each (mode, account) pair has its own equity curve
- Allows SIM and LIVE mode data to coexist without collision
- Protected by `_equity_mutex` for thread safety

### Timeframe Filtering
- 6 timeframes: LIVE (1hr), 1D, 1W, 1M, 3M, YTD
- Uses `_tf_configs` dict with window sizes
- `_filtered_points_for_current_tf()` slices data to window
- Affects both graph display and PnL baseline calculation

### PnL Direction Propagation
```
_pnl_up (up/down/neutral)
  ↓
Updates 4+ UI elements:
  - Label color (_apply_pnl_to_header)
  - Pill color (_apply_pnl_to_pills)
  - Endpoint color (_recolor_endpoint)
  - Animation color (_on_pulse_tick)
```

### Thread-Safe Pattern
```python
_equity_mutex.lock()
try:
    # Access _equity_curves or _pending_loads here
    ...
finally:
    _equity_mutex.unlock()
# UI updates AFTER unlock (no deadlock!)
```

### Signal-Driven Architecture
- SignalBus is event hub
- All connections use QueuedConnection (thread-safe)
- Replaces direct method calls
- Allows cross-module communication

---

## Critical State Flow

### Equity Points Flow
```
DTC → SignalBus.balanceUpdated
  ↓
Panel1._on_balance_updated
  ↓
StateManager.set_balance_for_mode
  ↓
Panel1.set_account_balance (display)
  ↓
Panel1.update_equity_series_from_balance (store)
  ↓
MUTEX LOCK → Add to _equity_curves[scope] → MUTEX UNLOCK
  ↓
Panel1._replot_from_cache
  ↓
Graph updates on screen
```

### Mode Switch Flow
```
User clicks SIM/LIVE badge
  ↓
SignalBus.modeChanged
  ↓
Panel1.set_trading_mode
  ↓
1. switch_theme(mode) - update all colors
2. _update_badge_style(mode) - neon pill
3. _get_equity_curve(mode) - load from DB (async)
4. _replot_from_cache - show new mode's data
```

### Timeframe Change Flow
```
User clicks timeframe pill
  ↓
Panel1.set_timeframe(tf)
  ↓
Update _tf
  ↓
_filtered_points_for_current_tf() - slice to window
  ↓
_replot_from_cache - redraw with filtered data
  ↓
_update_pnl_for_current_tf - recalculate for new baseline
  ↓
Display updated graph and PnL
```

---

## Performance Notes

### Memory
- Equity curve limited to 2 hours (prevents bloat)
- Async loading prevents UI freeze
- QFutureWatcher stored to prevent GC issues

### CPU/GPU
- 25 FPS pulse animation (smooth but not excessive)
- 1 sec equity update timer (avoids excessive repaints)
- Performance mode available (`_perf_safe`) for slower systems
- Binary search for hover (efficient O(log n) nearest point)

### Threading
- QtConcurrent for background loading
- QMutex for dict access (minimal lock duration)
- QueuedConnection for signal routing (thread-safe)

---

## Testing Strategy

### Unit Tests (by module)
- equity_state_manager: Async load, scoping, mutex
- equity_chart: Rendering, animation, hover
- timeframe_manager: Filtering, baseline lookup
- pnl_calculator: Calculation, formatting, colors
- theme_manager: Badge styling, color updates

### Integration Tests
- Balance update → Display → Equity curve → Graph
- Mode switch → Theme change → Curve reload → Repaint
- Timeframe change → Filtering → PnL recalc → Display
- Hover → Baseline lookup → PnL display → Teardown

### Stress Tests
- Rapid balance updates (100/sec)
- Fast timeframe switching
- Frequent theme changes
- Simultaneous mode + TF changes
- Memory growth over time

### Thread Safety Tests
- Concurrent balance updates
- Mode switch during load
- Equity access during GC
- Signal delivery under load

---

## Modification Checklist

Before modifying any method:

- [ ] Identify functional area (9 areas in summary)
- [ ] Check method's dependencies (quick reference)
- [ ] Verify data flow impact (dependencies flowchart)
- [ ] Check thread safety if accessing _equity_curves (quick ref)
- [ ] Verify repaint strategy (_replot_from_cache?)
- [ ] Test on all 6 timeframes
- [ ] Verify PnL calculation correct
- [ ] Run testing checklist
- [ ] Check for deadlock (mutex unlock before UI)

---

## Common Fixes

### Graph Doesn't Update
**Cause**: Forgot to call `_replot_from_cache()`  
**Fix**: Add call after updating `_equity_points` or `_tf`  
**See**: PANEL1_QUICK_REFERENCE.md "Common Gotchas" #1

### Race Condition in Async Load
**Cause**: Accessing `_equity_curves` without mutex  
**Fix**: Wrap with `_equity_mutex.lock()/unlock()`  
**See**: PANEL1_QUICK_REFERENCE.md "Common Gotchas" #2

### Deadlock in Background Thread
**Cause**: UI call while mutex locked  
**Fix**: Unlock before any UI updates  
**See**: PANEL1_DEPENDENCIES_FLOWCHART.md "Thread Safety Boundaries"

### PnL Color Doesn't Update
**Cause**: Forgot to call `_apply_pnl_to_pills()` or others  
**Fix**: Use `set_pnl_for_timeframe()` which calls all  
**See**: PANEL1_QUICK_REFERENCE.md "Common Patterns" #3

### Callback Never Fires
**Cause**: QFutureWatcher not stored (GC'd)  
**Fix**: Store in `_future_watchers` list  
**See**: PANEL1_QUICK_REFERENCE.md "Common Gotchas" #4

---

## Statistics

| Metric | Value |
|--------|-------|
| Original File | 1,820 lines |
| Total Analysis | 2,125 lines |
| Functional Areas | 9 |
| Methods | ~50 |
| State Variables | ~25 |
| Signals | 1 emit, 6 subscribe |
| Proposed Modules | 8-9 |
| Critical Paths | 4 |
| Common Patterns | 4 |
| Common Gotchas | 5 |
| Thread Safety Concerns | 0 critical |

---

## File Locations

All documents in: `/home/user/APPV4/`

```
PANEL1_ANALYSIS_SUMMARY.md           <- Start here
PANEL1_STRUCTURE_ANALYSIS.md         <- Detailed breakdown
PANEL1_DEPENDENCIES_FLOWCHART.md     <- Data flow & threads
PANEL1_QUICK_REFERENCE.md            <- Method lookup
PANEL1_MODULE_PLAN.md                <- Original plan
PANEL1_FIXES.md                      <- Known fixes
panels/panel1.py                     <- Original file
```

---

## Document Cross-References

If you see a reference like:

- **"See PANEL1_STRUCTURE_ANALYSIS.md Functional Area 3"**
  → Open that doc, find "## FUNCTIONAL AREA 3: TIMEFRAME MANAGEMENT"

- **"See PANEL1_QUICK_REFERENCE.md method table"**
  → Open that doc, find "## Method Organization by Functional Area"

- **"See PANEL1_DEPENDENCIES_FLOWCHART.md Thread Safety Boundaries"**
  → Open that doc, find "## Thread Safety Boundaries" section

- **"See PANEL1_ANALYSIS_SUMMARY.md Module Ownership"**
  → Open that doc, find "## What Each Module Should Own"

---

## Version History

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2025-11-14 | 1.0 | Initial analysis | Analysis Tool |

---

## Feedback & Corrections

If you find:
- Incorrect line numbers → Check original file and report
- Missing methods → Check Method Organization table
- Unclear explanations → Refer to original source code
- Better architecture ideas → Document in separate file

---

## Conclusion

This analysis provides everything needed to:
- Understand Panel1 architecture
- Modify individual methods safely
- Plan and execute refactoring
- Maintain code quality
- Train new developers

Start with the document that matches your use case from the "Quick Navigation" section above.

