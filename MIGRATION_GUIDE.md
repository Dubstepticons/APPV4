# Migration Guide - Zero-Downtime Panel Deployment

**Status:** Panel1 Phase 3 (manual validation) + Panel2 Phase 4 cleanup
**Last Updated:** 2025-11-15

> **Note:** Legacy `USE_NEW_PANEL1` / `USE_NEW_PANEL2` feature flags have been removed.
> The decomposed panels are always active now; any commands in this guide that
> reference those environment variables are kept for historical context only.
**Branch:** `claude/get-latitude-01A6fKJ23ratoLx1NPScuLRb`

---

## Executive Summary

The Priority 1 refactoring is **100% complete**, with all decomposed panels implemented and a zero-downtime migration system ready for production deployment. This guide provides step-by-step instructions for safely migrating from the old monolithic panels to the new decomposed architecture.

### What's Been Completed

✅ **Panel1 Decomposition** - 8 focused modules (2,459 LOC)
✅ **Panel2 Decomposition** - 8 focused modules (3,790 LOC)
✅ **Feature Flags System** - Environment-based switching
✅ **Migration Infrastructure** - Factory methods in MainWindow
✅ **Backup System** - Old panels preserved as `_old.py`
✅ **Test Suite** - Integration tests and validation
✅ **Documentation** - Complete architecture reference

---

## Quick Start

### Default Mode (Safe - Uses Old Panels)

```bash
# Start with old monolithic panels (default)
python main.py
```

### Enable New Panel1

```bash
# Enable decomposed Panel1
export USE_NEW_PANEL1=1
python main.py
```

### Enable Both New Panels

```bash
# Enable both decomposed panels
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
python main.py
```

### Instant Rollback

```bash
# Revert to old panels immediately
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
python main.py
```

---

## Migration Phases (7-Phase Plan)

### ✅ Phase 1: Feature Flags Implementation (COMPLETE)

**Goal:** Build infrastructure for zero-downtime switching

**Completed:**
- [x] Created `config/feature_flags.py` (437 LOC)
- [x] Integrated feature flags into MainWindow
- [x] Implemented panel factory methods
- [x] Created validation test suite
- [x] Verified environment variable override

**Validation:**
```bash
cd /home/user/APPV4
python test_feature_flags.py
```

**Expected Output:**
```
✓ FeatureFlags imported successfully
✓ Environment variable override working correctly
✓ Rollback to old panels working correctly
```

---

### ✅ Phase 2: Backup Old Implementations (COMPLETE)

**Goal:** Preserve original panels for rollback

**Completed:**
- [x] Renamed `panels/panel1.py` → `panels/panel1_old.py`
- [x] Renamed `panels/panel2.py` → `panels/panel2_old.py`
- [x] Both versions available simultaneously
- [x] Import paths updated in MainWindow

**File Structure:**
```
panels/
├── panel1/                  # New decomposed Panel1
│   ├── __init__.py
│   ├── panel1_main.py       # Orchestrator
│   ├── equity_state.py      # Thread-safe state
│   ├── equity_chart.py      # PyQtGraph rendering
│   ├── hover_handler.py     # Mouse interactions
│   ├── pnl_calculator.py    # Pure calculations
│   ├── timeframe_manager.py # Filtering logic
│   ├── masked_frame.py      # Custom widget
│   └── helpers.py           # Utilities
├── panel1_old.py            # Original monolithic (backup)
├── panel2/                  # New decomposed Panel2
│   ├── __init__.py
│   ├── panel2_main.py       # Orchestrator
│   ├── position_state.py    # Immutable state
│   ├── metrics_calculator.py # Pure calculations
│   ├── order_flow.py        # DTC handling
│   ├── position_display.py  # UI rendering
│   ├── visual_indicators.py # Heat/alerts
│   ├── csv_feed_handler.py  # Market data
│   └── state_persistence.py # DB/JSON
└── panel2_old.py            # Original monolithic (backup)
```

---

### 🔄 Phase 3: Parallel Testing (CURRENT - READY TO START)

**Goal:** Validate new panels in staging environment

**Prerequisites:**
- Development environment with PyQt6 installed
- Access to staging DTC server
- Test accounts for SIM and LIVE modes

**Testing Checklist:**

#### 3.1 Panel1 Integration Tests

```bash
# Run automated test suite (requires PyQt6)
cd /home/user/APPV4
pytest tests/test_panel1_integration.py -v
```

**Manual Tests:**
1. **Timeframe Switching**
   - Switch between LIVE, 1D, 1W, 1M, 3M, YTD
   - Verify chart updates correctly
   - Check PnL calculations for each timeframe

2. **Mode Switching**
   - Switch SIM → LIVE → DEBUG
   - Verify balance displays correctly
   - Check equity curve persistence

3. **Hover Interactions**
   - Mouse over equity chart
   - Verify hover line appears
   - Check PnL updates in real-time

4. **Thread Safety**
   - Rapidly switch modes while data loading
   - Check for race conditions
   - Monitor for Qt thread warnings

#### 3.2 Panel2 Integration Tests

**Manual Tests:**
1. **Position Opening**
   - Open position in SIM mode
   - Verify all 15 cells populate
   - Check heat timer starts

2. **Market Data Updates**
   - Verify CSV feed polling (500ms)
   - Check price updates in real-time
   - Validate VWAP, Delta, POC updates

3. **Visual Indicators**
   - Test heat timer thresholds (3:00, 4:30, 5:00)
   - Verify stop proximity alerts
   - Check flashing behavior

4. **State Persistence**
   - Open position
   - Restart application
   - Verify position restored from database

#### 3.3 Backwards Compatibility Tests

Run both versions side-by-side:

```bash
# Terminal 1: Old panels
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
python main.py

# Terminal 2: New panels
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
python main.py
```

**Validation:**
- Compare display outputs
- Verify identical PnL calculations
- Check signal emissions
- Monitor performance metrics

#### 3.4 Performance Benchmarks

```bash
# Enable performance tracking
export ENABLE_PERF_TRACKING=1
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
python main.py
```

**Metrics to Track:**
- Panel1 equity chart render time (<16ms for 60 FPS)
- Panel2 cell update frequency (500ms refresh)
- Memory usage (expect 10-15% reduction)
- CPU usage during updates (expect 20-30% reduction)

---

### 📋 Phase 4: Gradual Production Rollout (NEXT)

**Goal:** Safely deploy to production with monitoring

**Week 1: Panel1 Only**

```bash
# Production environment
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=0
export ENABLE_MIGRATION_LOGS=1
python main.py
```

**Monitor:**
- No errors in logs
- Equity chart rendering correctly
- Balance updates working
- No thread safety issues

**Rollback Plan:**
If any issues detected:
```bash
export USE_NEW_PANEL1=0
# Restart application immediately
```

**Week 2: Both Panels**

```bash
# Production environment
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
export ENABLE_MIGRATION_LOGS=1
python main.py
```

**Monitor:**
- Position display correct
- Heat timers functioning
- CSV feed updates working
- State persistence reliable

**Rollback Plan:**
```bash
export USE_NEW_PANEL2=0  # Rollback Panel2 only
# Or rollback both:
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
```

---

### 🔍 Phase 5: Validation and Monitoring (NEXT)

**Goal:** Confirm production stability

**Duration:** 2 weeks minimum

**Metrics to Track:**

| Metric | Old Panels | New Panels | Target |
|--------|-----------|-----------|--------|
| Memory Usage | Baseline | -10-15% | Reduction |
| CPU Usage | Baseline | -20-30% | Reduction |
| Render Time (Panel1) | ~20ms | <16ms | <16ms |
| Error Rate | Baseline | 0 new errors | 0 new errors |
| Crash Rate | Baseline | 0 new crashes | 0 new crashes |

**Log Monitoring:**

```bash
# Check migration logs
grep "Migration" logs/app.log | tail -20

# Expected output:
# [Migration] Using NEW Panel1 (decomposed architecture)
# [Migration] Using NEW Panel2 (decomposed architecture)
```

**User Feedback:**
- Gather feedback on responsiveness
- Check for UI glitches
- Verify all features working

---

### 🧹 Phase 6: Cleanup Old Code (FUTURE)

**Goal:** Remove technical debt and legacy code

**Only proceed after 2+ weeks of stable production**

**Steps:**

1. **Remove Old Panel Files**
```bash
git rm panels/panel1_old.py
git rm panels/panel2_old.py
git commit -m "chore: Remove old monolithic panels after successful migration"
```

2. **Remove Feature Flag Checks**

Update `core/app_manager.py`:
```python
# Before:
self.panel_balance = self._create_panel1()

# After:
from panels.panel1 import Panel1
self.panel_balance = Panel1()
```

3. **Update Configuration**

Remove from `config/feature_flags.py`:
```python
# Remove USE_NEW_PANEL1 and USE_NEW_PANEL2 flags
```

4. **Update Documentation**
- Remove migration-specific docs
- Update README with final architecture
- Archive migration logs

---

### 🎯 Phase 7: Full Typed Events Migration (FUTURE)

**Goal:** Complete migration to typed event system

**Services to Migrate:**

1. **TradeCloseService**
```python
# Before: Dict events
signal_bus.tradeClosedForAnalytics.emit({
    "trade_id": 123,
    "pnl": 125.50
})

# After: Typed events
event = TradeClosedForAnalyticsEvent(
    trade_id=123,
    realized_pnl=125.50
)
signal_bus.tradeClosedForAnalytics.emit(event)
```

2. **OrderFlowHandler**
3. **Panel3 Analytics**
4. **UnifiedBalanceManager**

**Remove Compatibility Layer:**
```python
# Remove .to_dict() methods from domain/events.py
```

---

## Troubleshooting

### Issue: Application Won't Start

**Symptom:** Import errors or crashes on startup

**Solution:**
1. Check feature flag syntax:
```bash
# Valid values: 0, 1, true, false, True, False
export USE_NEW_PANEL1=1  # ✓ Correct
export USE_NEW_PANEL1=yes # ✗ Invalid
```

2. Verify old panels exist:
```bash
ls -la panels/panel1_old.py
ls -la panels/panel2_old.py
```

3. Rollback to safe mode:
```bash
unset USE_NEW_PANEL1
unset USE_NEW_PANEL2
python main.py
```

---

### Issue: Panel Rendering Incorrectly

**Symptom:** Missing data, blank charts, or visual glitches

**Solution:**
1. Enable migration logs:
```bash
export ENABLE_MIGRATION_LOGS=1
python main.py
```

2. Check which panel is active:
```python
# In app_manager.py logs:
# Look for "[Migration] Using NEW Panel1" or "Using OLD Panel1"
```

3. Test old panel:
```bash
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
python main.py
```

If old panel works but new panel doesn't, file a bug report with logs.

---

### Issue: Performance Regression

**Symptom:** Slow rendering, high CPU usage

**Solution:**
1. Enable performance tracking:
```bash
export ENABLE_PERF_TRACKING=1
python main.py
```

2. Compare metrics:
```bash
# Old panels
export USE_NEW_PANEL1=0
python main.py
# Note CPU/memory usage

# New panels
export USE_NEW_PANEL1=1
python main.py
# Compare metrics
```

3. If regression confirmed, rollback and investigate:
```bash
export USE_NEW_PANEL1=0
# File performance report with profiling data
```

---

### Issue: Data Loss or State Corruption

**Symptom:** Missing positions, incorrect balances

**Solution:**
1. **IMMEDIATELY** rollback:
```bash
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
python main.py
```

2. Check database integrity:
```bash
# Verify positions table
sqlite3 data/appsierra.db "SELECT * FROM open_positions;"

# Verify trades table
sqlite3 data/appsierra.db "SELECT * FROM trades ORDER BY id DESC LIMIT 10;"
```

3. Restore from JSON state files if needed:
```bash
# State files location:
ls -la runtime_state_*.json
```

---

## Configuration Reference

### Feature Flags

All flags are boolean (True/False) and follow this priority:

1. **Environment Variables** (highest priority)
2. **Config File** (`config/settings.py`)
3. **Defaults** (lowest priority)

**Available Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `USE_NEW_PANEL1` | False | Enable decomposed Panel1 |
| `USE_NEW_PANEL2` | False | Enable decomposed Panel2 |
| `USE_TYPED_EVENTS` | False | Enable typed event system |
| `ENABLE_MIGRATION_LOGS` | True | Log migration decisions |
| `ENABLE_PERF_TRACKING` | True | Track performance metrics |

**Setting via Environment:**
```bash
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
```

**Setting via Config File:**
```python
# config/settings.py
FEATURE_FLAGS = {
    "USE_NEW_PANEL1": True,
    "USE_NEW_PANEL2": True,
}
```

---

## Success Criteria

Before proceeding to next phase, verify:

### Phase 3 → Phase 4
- [ ] All integration tests pass
- [ ] Manual testing complete
- [ ] Performance benchmarks meet targets
- [ ] No regressions detected
- [ ] Team sign-off

### Phase 4 → Phase 5
- [ ] Production rollout successful
- [ ] No critical errors in logs
- [ ] User feedback positive
- [ ] Rollback plan validated

### Phase 5 → Phase 6
- [ ] 2+ weeks stable production
- [ ] All metrics meeting targets
- [ ] Zero regressions
- [ ] Team consensus to cleanup

### Phase 6 → Phase 7
- [ ] Old code removed
- [ ] Documentation updated
- [ ] Codebase simplified
- [ ] Ready for typed events migration

---

## Next Steps

**Immediate (Panel1 Phase 3):**
1. Execute manual checklist (timeframes, hover, thread safety, UX)
2. Capture screenshots/perf benchmarks + log review results
3. Compile QA/dev/product sign-off package for Panel1 rollout

**Short Term (Phase 4):**
1. Deploy Panel1-only build to production and monitor for 1 week
2. Keep Panel1 enabled after soak once metrics are green
3. Finalize Panel2 enablement (flip default flag + remove `panel2_old.py`)
4. Publish combined rollout findings + config changes

**Long Term (Phases 5-7):**
1. Validate production stability
2. Cleanup old code
3. Migrate to typed events
4. Complete Priority 2 refactoring

---

## Support

**Documentation:**
- [Architecture Documentation](ARCHITECTURE_DOCUMENTATION.md)
- [Migration Strategy](MIGRATION_STRATEGY.md)
- [Priority 1 Implementation](PRIORITY1_REFACTORING_IMPLEMENTATION.md)
- [Panel1 Integration Tests](PANEL1_INTEGRATION_TEST_PLAN.md)
- [Panel2 Integration Tests](PANEL2_INTEGRATION_TEST_PLAN.md)

**Testing:**
- `test_feature_flags.py` - Feature flag validation
- `test_panel1_integration.py` - Panel1 automated tests
- See test plan documents for manual tests

**Logs:**
```bash
# Check migration logs
grep "Migration" logs/app.log

# Check errors
grep "ERROR" logs/app.log

# Check warnings
grep "WARN" logs/app.log
```

---

**End of Migration Guide**
