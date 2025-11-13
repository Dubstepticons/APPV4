# Phase 4: Direct Method Call Audit

**Goal**: Replace direct panel method calls with SignalBus signals for full decoupling

---

## Current Direct Calls Identified

### 1. App Manager → Panel1 (Balance)

**File**: `core/app_manager.py`

| Line | Call | Purpose | Priority |
|------|------|---------|----------|
| 264 | `panel_balance._get_equity_curve()` | Load equity history | LOW (internal, startup only) |
| 273 | `panel_balance.update_equity_series_from_balance()` | Add equity point | **HIGH** (balance updates) |
| 289 | `panel_balance._replot_from_cache()` | Redraw graph | LOW (internal UI) |
| 489-490 | `panel_balance.set_account_balance()` | Update balance display | **HIGH** (balance updates) |
| 553 | `panel_balance._refresh_theme_colors()` | Theme change | MEDIUM |
| 602 | `panel_balance.set_timeframe()` | TF change | MEDIUM |
| 642 | `panel_balance.set_timeframe()` | TF change (duplicate) | MEDIUM |

**Recommended Signals to Add:**
```python
# SignalBus additions for Panel1
balanceDisplayRequested = QtCore.pyqtSignal(float, str)  # balance, mode
equityPointRequested = QtCore.pyqtSignal(float, str)     # balance, mode
timeframeChangeRequested = QtCore.pyqtSignal(str)        # timeframe
```

---

### 2. App Manager → Panel2 (Live Trading)

**File**: `core/app_manager.py`

| Line | Call | Purpose | Priority |
|------|------|---------|----------|
| 557 | `panel_live.refresh_theme()` | Theme change | MEDIUM |
| 607 | `panel_live.set_timeframe()` | TF change | LOW (optional sync) |
| 612 | `panel_live.set_live_dot_visible()` | Show LIVE indicator | LOW (visual only) |
| 614 | `panel_live.set_live_dot_pulsing()` | Pulse LIVE indicator | LOW (visual only) |
| 825-829 | `panel_live.save_state()` | Save state on exit | LOW (shutdown only) |

**Recommended Signals to Add:**
```python
# SignalBus additions for Panel2
themeChangeRequested = QtCore.pyqtSignal()
liveDotVisibilityRequested = QtCore.pyqtSignal(bool)  # visible
liveDotPulsingRequested = QtCore.pyqtSignal(bool)     # pulsing
```

**Note**: `set_timeframe()` and `save_state()` are low priority (infrequent, not critical path)

---

### 3. App Manager → Panel3 (Stats)

**File**: `core/app_manager.py`

| Line | Call | Purpose | Priority |
|------|------|---------|----------|
| 358 | `panel_stats.on_trade_closed()` | Process closed trade | **HIGH** (trade lifecycle) |
| 365 | `panel_stats._load_metrics_for_timeframe()` | Reload metrics | MEDIUM |
| 372 | `panel_stats.analyze_and_store_trade_snapshot()` | Store snapshot | MEDIUM |
| 561 | `panel_stats.refresh_theme()` | Theme change | MEDIUM |

**Recommended Signals:**
```python
# SignalBus already has:
# tradeClosed = QtCore.pyqtSignal(dict)  # Can use this!

# New signals for Panel3:
metricsReloadRequested = QtCore.pyqtSignal(str)  # timeframe
snapshotAnalysisRequested = QtCore.pyqtSignal()
```

**Note**: `on_trade_closed()` can use existing `tradeClosed` signal from Panel2

---

### 4. Panel3 → Panel2 (Stats reading Live data)

**File**: `panels/panel3.py`

| Line | Call | Purpose | Priority |
|------|------|---------|----------|
| 208 | `_panel_live.has_active_position()` | Check if in trade | **HIGH** |
| 213 | `_panel_live.get_current_trade_data()` | Get position data | **HIGH** |
| 214 | `_panel_live.get_live_feed_data()` | Get market data | **HIGH** |
| 215 | `_panel_live.get_trade_state()` | Get state data | **HIGH** |

**Current Pattern**: Panel3 pulls data directly from Panel2

**Recommended Approach**:
- Option A: **Push model** - Panel2 emits data changes, Panel3 caches
- Option B: **Query signal** - Panel3 emits request signal, Panel2 responds
- Option C: **Keep as-is** - These are data queries, not commands (acceptable coupling)

**Recommendation**: **Option C (Keep as-is)** - These are read-only data queries for analysis. This is acceptable coupling since Panel3 is specifically designed to analyze Panel2's live trading state. The methods are getter methods returning data, not mutating state.

---

### 5. Panel Wiring (Initialization)

**File**: `core/app_manager.py`

| Line | Call | Purpose | Priority |
|------|------|---------|----------|
| 312 | `panel_balance.set_stats_panel()` | Wire Panel1 → Panel3 | **REMOVE** |
| 317 | `panel_stats.set_live_panel()` | Wire Panel3 → Panel2 | **KEEP** (data access) |

**Recommendation**:
- **Remove** `set_stats_panel()` - Replace with signals
- **Keep** `set_live_panel()` - Panel3 needs direct data access for analysis

---

## Phase 4 Implementation Plan

### Priority 1: Critical Path (Balance & Trade Events)

**1.1 Balance Updates (App Manager → Panel1)**
- Add signals: `balanceDisplayRequested`, `equityPointRequested`
- Replace: `set_account_balance()`, `update_equity_series_from_balance()`
- Impact: Balance display, equity graph updates

**1.2 Trade Lifecycle (Panel2 → Panel3)**
- Use existing: `tradeClosed` signal (already in Panel2.tradesChanged)
- Replace: `panel_stats.on_trade_closed()` direct call
- Impact: Trade statistics, metrics recalculation

### Priority 2: UI Synchronization (Theme, Timeframe)

**2.1 Theme Changes**
- Add signal: `themeChangeRequested`
- Replace: All `refresh_theme()` calls
- Impact: Visual consistency across panels

**2.2 Timeframe Changes**
- Use existing: Can add to existing signals or create `timeframeChangeRequested`
- Replace: `set_timeframe()` calls
- Impact: Graph windowing, LIVE mode sync

### Priority 3: Low-Impact (Visual, Shutdown)

**3.1 LIVE Dot Indicators**
- Add signals: `liveDotVisibilityRequested`, `liveDotPulsingRequested`
- Replace: `set_live_dot_visible()`, `set_live_dot_pulsing()`
- Impact: Visual indicator only

**3.2 State Persistence**
- Keep as-is: `save_state()` on shutdown (called once, not critical path)

---

## Signals to Add to SignalBus

### Balance & Equity
```python
# Panel1 commands
balanceDisplayRequested = QtCore.pyqtSignal(float, str)      # balance, mode
equityPointRequested = QtCore.pyqtSignal(float, str)         # balance, mode
```

### UI Synchronization
```python
# Cross-panel UI updates
themeChangeRequested = QtCore.pyqtSignal()
timeframeChangeRequested = QtCore.pyqtSignal(str)            # timeframe
```

### Panel2 Visual Indicators
```python
# Panel2 LIVE mode indicators
liveDotVisibilityRequested = QtCore.pyqtSignal(bool)         # visible
liveDotPulsingRequested = QtCore.pyqtSignal(bool)            # pulsing
```

### Panel3 Analytics (Optional)
```python
# Panel3 commands (low priority)
metricsReloadRequested = QtCore.pyqtSignal(str)              # timeframe
snapshotAnalysisRequested = QtCore.pyqtSignal()
```

---

## Exclusions (Keep Direct Calls)

### Data Queries (Acceptable Coupling)
- `panel_live.has_active_position()` - Read-only query
- `panel_live.get_current_trade_data()` - Data getter
- `panel_live.get_live_feed_data()` - Data getter
- `panel_live.get_trade_state()` - Data getter

**Rationale**: These are read-only data access methods. Panel3 is specifically designed to analyze Panel2's state. This is acceptable coupling for analytics.

### Startup/Shutdown (Low Frequency)
- `panel_balance._get_equity_curve()` - One-time startup load
- `panel_balance._replot_from_cache()` - Internal UI method
- `panel_live.save_state()` - One-time shutdown save

**Rationale**: Called once per session, not worth signal overhead.

---

## Implementation Steps

### Step 1: Add Signals to SignalBus
- Update `core/signal_bus.py` with new signals
- Group by purpose (balance, UI sync, indicators)
- Add documentation

### Step 2: Priority 1 - Balance & Trade Events
- Panel1 subscribes to balance signals
- App Manager emits balance signals instead of direct calls
- Panel3 subscribes to `tradeClosed` signal
- Test balance updates and trade closure

### Step 3: Priority 2 - Theme & Timeframe
- All panels subscribe to theme/timeframe signals
- App Manager emits instead of direct calls
- Test UI synchronization

### Step 4: Priority 3 - Visual Indicators (Optional)
- Panel2 subscribes to LIVE dot signals
- App Manager emits instead of direct calls
- Test visual indicators

### Step 5: Cleanup
- Remove `set_stats_panel()` wiring
- Update documentation
- Verify no regressions

---

## Estimated Time

- **Step 1**: 1 hour (add signals)
- **Step 2**: 3 hours (balance & trade events)
- **Step 3**: 2 hours (theme & timeframe)
- **Step 4**: 1 hour (visual indicators - optional)
- **Step 5**: 1 hour (cleanup & testing)

**Total**: ~8 hours (6 hours for priorities 1-2 only)

---

## Success Criteria

✅ No direct method calls for balance updates
✅ No direct method calls for trade events
✅ Theme changes propagate via signals
✅ Timeframe changes propagate via signals
✅ All existing functionality preserved
✅ No regressions in UI behavior

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Signal not received | Low | Medium | Logging, fallback handling |
| Event ordering issues | Low | Low | QueuedConnection ensures order |
| Performance overhead | Very Low | Very Low | Qt signals very efficient |
| Breaking existing code | Low | Medium | Incremental replacement, testing |

---

## Notes

- Keep Panel3 → Panel2 data queries (acceptable coupling for analytics)
- Focus on command/event patterns, not data queries
- Use QueuedConnection for cross-thread safety
- Test thoroughly after each step
