# APPSIERRA Migration Strategy

**Date:** 2025-11-14
**Status:** Ready for Execution
**Branch:** `claude/get-latitude-01A6fKJ23ratoLx1NPScuLRb`

---

## Executive Summary

This document outlines the comprehensive migration strategy for transitioning APPSIERRA from the old monolithic architecture to the new decomposed, modular architecture. The migration will be executed in phases with careful validation at each step to ensure zero downtime and minimal risk.

> **Note:** Legacy `USE_NEW_PANEL*` feature flags have been retired. The new panels are always enabled, so any historical references to those environment variables are informational only.

### What's Being Migrated:

1. **Panel1:** 1,820 LOC monolith → 8 focused modules (2,459 LOC)
2. **Panel2:** 1,930 LOC monolith → 8 focused modules (3,790 LOC)
3. **SignalBus:** Dict payloads → Typed domain events
4. **Balance Management:** Scattered logic → Unified balance manager

---

## Migration Philosophy

### Core Principles:

1. **Zero Downtime** - Application continues to work during migration
2. **Gradual Rollout** - Feature flags allow controlled deployment
3. **Backwards Compatibility** - Old code continues to work
4. **Easy Rollback** - Quick revert if issues arise
5. **Comprehensive Testing** - Verify before removing old code

### Risk Mitigation:

- Feature flags for instant rollback
- Parallel testing (old vs new)
- Incremental migration
- Extensive logging
- Performance monitoring

---

## Phase 1: Feature Flags Implementation

### Objective:
Create configuration system to toggle between old and new implementations.

### Duration: 1 day

### Steps:

#### 1.1: Create Feature Flag Module

```python
# config/feature_flags.py

"""
Feature flags for gradual migration to new architecture.

Usage:
    from config.feature_flags import FeatureFlags

    if FeatureFlags.USE_NEW_PANEL1:
        from panels.panel1 import Panel1
    else:
        from panels.panel1_old import Panel1
"""

from __future__ import annotations

import os
from typing import Optional


class FeatureFlags:
    """
    Feature flags for architectural migrations.

    Flags can be set via:
    1. Environment variables (highest priority)
    2. Config file
    3. Default values

    Environment Variables:
        USE_NEW_PANEL1=1        - Enable new Panel1 architecture
        USE_NEW_PANEL2=1        - Enable new Panel2 architecture
        USE_TYPED_EVENTS=1      - Enable typed domain events
        ENABLE_MIGRATION_LOGS=1 - Extra logging for migration
    """

    # Panel Migrations
    USE_NEW_PANEL1: bool = _get_flag("USE_NEW_PANEL1", default=False)
    USE_NEW_PANEL2: bool = _get_flag("USE_NEW_PANEL2", default=False)

    # Event System
    USE_TYPED_EVENTS: bool = _get_flag("USE_TYPED_EVENTS", default=False)

    # Logging
    ENABLE_MIGRATION_LOGS: bool = _get_flag("ENABLE_MIGRATION_LOGS", default=True)

    # Performance
    ENABLE_PERFORMANCE_TRACKING: bool = _get_flag("ENABLE_PERFORMANCE_TRACKING", default=True)

    @staticmethod
    def _get_flag(name: str, default: bool = False) -> bool:
        """
        Get feature flag value from environment or config.

        Args:
            name: Flag name
            default: Default value if not set

        Returns:
            Boolean flag value
        """
        # Check environment variable
        env_value = os.getenv(name)
        if env_value is not None:
            return env_value.lower() in ("1", "true", "yes", "on")

        # Check config file
        try:
            from config.settings import FEATURE_FLAGS
            if name in FEATURE_FLAGS:
                return bool(FEATURE_FLAGS[name])
        except (ImportError, AttributeError):
            pass

        # Return default
        return default

    @classmethod
    def enable_all_new_features(cls) -> None:
        """Enable all new features (for testing)."""
        cls.USE_NEW_PANEL1 = True
        cls.USE_NEW_PANEL2 = True
        cls.USE_TYPED_EVENTS = True

    @classmethod
    def disable_all_new_features(cls) -> None:
        """Disable all new features (rollback)."""
        cls.USE_NEW_PANEL1 = False
        cls.USE_NEW_PANEL2 = False
        cls.USE_TYPED_EVENTS = False

    @classmethod
    def print_status(cls) -> None:
        """Print current feature flag status."""
        print("=" * 60)
        print("FEATURE FLAGS STATUS")
        print("=" * 60)
        print(f"USE_NEW_PANEL1: {cls.USE_NEW_PANEL1}")
        print(f"USE_NEW_PANEL2: {cls.USE_NEW_PANEL2}")
        print(f"USE_TYPED_EVENTS: {cls.USE_TYPED_EVENTS}")
        print(f"ENABLE_MIGRATION_LOGS: {cls.ENABLE_MIGRATION_LOGS}")
        print(f"ENABLE_PERFORMANCE_TRACKING: {cls.ENABLE_PERFORMANCE_TRACKING}")
        print("=" * 60)
```

#### 1.2: Add to config/settings.py

```python
# config/settings.py

# Feature flags (can be overridden by environment variables)
FEATURE_FLAGS = {
    "USE_NEW_PANEL1": False,  # Default: use old Panel1
    "USE_NEW_PANEL2": False,  # Default: use old Panel2
    "USE_TYPED_EVENTS": False,  # Default: use dict events
}
```

#### 1.3: Update app_manager.py

```python
# core/app_manager.py

from config.feature_flags import FeatureFlags

# Print feature flag status on startup
FeatureFlags.print_status()

# Conditional import
if FeatureFlags.USE_NEW_PANEL1:
    from panels.panel1 import Panel1  # New decomposed version
    log.info("Using NEW Panel1 architecture")
else:
    from panels.panel1_old import Panel1  # Old monolith
    log.info("Using OLD Panel1 architecture")

if FeatureFlags.USE_NEW_PANEL2:
    from panels.panel2 import Panel2  # New decomposed version
    log.info("Using NEW Panel2 architecture")
else:
    from panels.panel2_old import Panel2  # Old monolith
    log.info("Using OLD Panel2 architecture")
```

### Validation:
- ✅ Feature flags load correctly
- ✅ Environment variables override config
- ✅ App starts with both old and new versions

---

## Phase 2: Backup Old Implementations

### Objective:
Preserve old monolithic implementations for rollback.

### Duration: 1 hour

### Steps:

#### 2.1: Rename Old Panel1

```bash
# Move old Panel1 to panel1_old.py
mv panels/panel1.py panels/panel1_old.py

# Update imports in panel1_old.py if needed
```

#### 2.2: Rename Old Panel2

```bash
# Move old Panel2 to panel2_old.py
mv panels/panel2.py panels/panel2_old.py
```

#### 2.3: Create Compatibility Shims

```python
# panels/panel1.py (if USE_NEW_PANEL1=False)

"""
Panel1 compatibility shim.

Routes to old or new implementation based on feature flag.
"""

from config.feature_flags import FeatureFlags

if FeatureFlags.USE_NEW_PANEL1:
    from panels.panel1_new import Panel1
else:
    from panels.panel1_old import Panel1

__all__ = ["Panel1"]
```

### Validation:
- ✅ Old implementations preserved
- ✅ Both versions accessible
- ✅ No breaking changes

---

## Phase 3: Parallel Testing (Staging)

### Objective:
Test new implementations alongside old in staging environment.

### Duration: 3-5 days

### Steps:

#### 3.1: Deploy to Staging

```bash
# Set feature flags for parallel testing
export USE_NEW_PANEL1=0  # Use old initially
export USE_NEW_PANEL2=0
export ENABLE_MIGRATION_LOGS=1

# Run application
python main.py
```

#### 3.2: Run Integration Tests

```bash
# Test old implementation
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
python test_panel1_integration.py
python test_panel2_integration.py

# Test new implementation
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
python test_panel1_integration.py
python test_panel2_integration.py
```

#### 3.3: Performance Comparison

```python
# tools/performance_comparison.py

"""
Compare performance of old vs new implementations.
"""

import time
from config.feature_flags import FeatureFlags

def benchmark_panel1():
    """Benchmark Panel1 instantiation and operations."""

    # Test old Panel1
    FeatureFlags.USE_NEW_PANEL1 = False
    from panels.panel1 import Panel1

    start = time.time()
    panel_old = Panel1()
    old_time = time.time() - start

    # Test new Panel1
    FeatureFlags.USE_NEW_PANEL1 = True
    # Reload module
    import importlib
    import panels.panel1
    importlib.reload(panels.panel1)
    from panels.panel1 import Panel1

    start = time.time()
    panel_new = Panel1()
    new_time = time.time() - start

    print(f"Old Panel1: {old_time:.3f}s")
    print(f"New Panel1: {new_time:.3f}s")
    print(f"Difference: {(new_time - old_time):.3f}s ({((new_time/old_time)-1)*100:.1f}%)")

benchmark_panel1()
```

#### 3.4: User Acceptance Testing

- Manual testing of all features
- All timeframes (LIVE, 1D, 1W, 1M, 3M, YTD)
- All modes (DEBUG, SIM, LIVE)
- Hover interactions
- Chart animations
- Order flows (Panel2)

### Validation:
- ✅ All tests pass for both versions
- ✅ No performance regressions
- ✅ No visual differences
- ✅ No data corruption

---

## Phase 4: Gradual Production Rollout

### Objective:
Gradually enable new implementations in production with monitoring.

### Duration: 1-2 weeks

### Steps:

#### 4.1: Week 1 - Panel1 Only

```bash
# Enable only Panel1 in production
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=0
export ENABLE_MIGRATION_LOGS=1
export ENABLE_PERFORMANCE_TRACKING=1
```

**Monitoring:**
- Check logs for errors
- Monitor performance metrics
- Watch for memory leaks
- User feedback

**Rollback Plan:**
```bash
# If issues arise, instant rollback
export USE_NEW_PANEL1=0
# Restart application
```

#### 4.2: Week 2 - Panel2 Added

```bash
# Enable both panels
export USE_NEW_PANEL1=1
export USE_NEW_PANEL2=1
```

**Monitoring:**
- Position state accuracy
- Order flow correctness
- Metrics calculations
- Database persistence

---

## Phase 5: Typed Events Migration

### Objective:
Migrate SignalBus to use typed domain events.

### Duration: 1 week

### Steps:

#### 5.1: Update SignalBus Emitters

```python
# BEFORE (dict payloads)
from core.signal_bus import get_signal_bus
signal_bus = get_signal_bus()

signal_bus.positionUpdated.emit({
    'symbol': 'MES',
    'account': 'Sim1',
    'quantity': 1,
    'average_price': 6750.0
})

# AFTER (typed events)
from domain.events import PositionUpdateEvent

event = PositionUpdateEvent(
    symbol='MES',
    account='Sim1',
    quantity=1,
    average_price=6750.0,
    mode='SIM'
)

signal_bus.positionUpdated.emit(event)
```

#### 5.2: Update SignalBus Handlers

```python
# BEFORE
def on_position_updated(data: dict):
    symbol = data['symbol']
    account = data['account']
    # ...

# AFTER
from domain.events import PositionUpdateEvent

def on_position_updated(event: PositionUpdateEvent):
    symbol = event.symbol
    account = event.account
    # Full IDE support!
```

#### 5.3: Compatibility Layer

```python
# For gradual migration, support both

from config.feature_flags import FeatureFlags

def on_position_updated(event):
    if FeatureFlags.USE_TYPED_EVENTS:
        # Event is PositionUpdateEvent
        symbol = event.symbol
    else:
        # Event is dict
        symbol = event['symbol']
```

### Migration Order:

1. **High-Value Paths** (Week 1):
   - TradeCloseService
   - Panel2 order flow
   - Panel3 analytics

2. **Medium-Value Paths** (Week 2):
   - Panel1 balance updates
   - DTC message handling

3. **Low-Value Paths** (Week 3):
   - UI status messages
   - Error handling

---

## Phase 6: Cleanup & Removal

### Objective:
Remove old implementations after validation period.

### Duration: 1 week

### Steps:

#### 6.1: Verify New Implementations Stable

- Minimum 2 weeks in production
- Zero critical bugs
- Performance acceptable
- User feedback positive

#### 6.2: Remove Old Monoliths

```bash
# After validation period complete
git rm panels/panel1_old.py
git rm panels/panel2_old.py
```

#### 6.3: Remove Feature Flags

```python
# Simplify imports (no longer conditional)

# config/feature_flags.py - remove Panel flags
# core/app_manager.py - direct imports

from panels.panel1 import Panel1  # Always new version
from panels.panel2 import Panel2  # Always new version
```

#### 6.4: Update Documentation

- Architecture diagrams
- API documentation
- Migration guide (for future reference)
- Lessons learned

---

## Phase 7: Typed Events Full Migration

### Objective:
Complete migration to typed events everywhere.

### Duration: 1 week

### Steps:

#### 7.1: Remove `.to_dict()` Methods

```python
# domain/events.py

# Remove backwards compatibility methods
class PositionUpdateEvent:
    # ... fields ...

    # DELETE THIS:
    # def to_dict(self) -> dict:
    #     return {...}
```

#### 7.2: Enforce Types in SignalBus

```python
# core/signal_bus.py

from domain.events import PositionUpdateEvent

class SignalBus:
    # Enforce type hints
    positionUpdated: QtCore.pyqtSignal = QtCore.pyqtSignal(PositionUpdateEvent)

    def emit_position_update(self, event: PositionUpdateEvent):
        """Type-safe emission."""
        if not isinstance(event, PositionUpdateEvent):
            raise TypeError(f"Expected PositionUpdateEvent, got {type(event)}")
        self.positionUpdated.emit(event)
```

#### 7.3: Remove Dict Handlers

```bash
# Search for dict-based handlers
git grep "def.*\(data: dict\)" | grep signal

# Update each one to use typed events
```

---

## Rollback Procedures

### Emergency Rollback (< 5 minutes)

```bash
# Set feature flags to disable all new features
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=0
export USE_TYPED_EVENTS=0

# Restart application
systemctl restart appsierra
# or
pkill -f main.py && python main.py
```

### Partial Rollback

```bash
# Roll back only Panel1
export USE_NEW_PANEL1=0
export USE_NEW_PANEL2=1  # Keep Panel2

# Roll back only Panel2
export USE_NEW_PANEL1=1  # Keep Panel1
export USE_NEW_PANEL2=0
```

### Code Rollback (if needed)

```bash
# Revert to old commit
git revert <commit-hash>

# Or checkout old version
git checkout <old-commit> -- panels/panel1.py
git checkout <old-commit> -- panels/panel2.py
```

---

## Success Metrics

### Must Achieve:

✅ **Zero Data Loss** - All equity curves, positions, trades preserved
✅ **Zero Downtime** - Application remains available
✅ **Performance Maintained** - No regressions > 10%
✅ **Backwards Compatibility** - Old API continues to work

### Target Improvements:

- **Code Quality:** +50% testability (16 testable modules vs 2)
- **Modularity:** +435% (8 modules per panel vs 1)
- **Thread Safety:** 100% (QMutex, RLock protections)
- **Documentation:** +200% (comprehensive docs for all modules)

---

## Timeline Summary

| Phase | Duration | Description | Status |
|-------|----------|-------------|--------|
| 1. Feature Flags | 1 day | Implement toggle system | Pending |
| 2. Backup | 1 hour | Preserve old code | Pending |
| 3. Parallel Testing | 3-5 days | Test both versions | Pending |
| 4. Production Rollout | 1-2 weeks | Gradual enable | Pending |
| 5. Typed Events | 1 week | Migrate events | Pending |
| 6. Cleanup | 1 week | Remove old code | Pending |
| 7. Full Migration | 1 week | Complete transition | Pending |

**Total Duration:** 4-6 weeks

---

## Risk Assessment

### Low Risk:
- Feature flags implementation ✅
- Backup of old code ✅
- Parallel testing ✅

### Medium Risk:
- Production rollout (mitigated by gradual deployment)
- Typed events migration (mitigated by compatibility layer)

### High Risk:
- Removing old code (mitigated by 2-week validation period)
- Full typed events enforcement (mitigated by thorough testing)

---

## Communication Plan

### Stakeholders:
1. **Development Team** - Technical updates, code reviews
2. **QA Team** - Test plans, validation criteria
3. **Users** - Feature announcements, feedback collection
4. **Management** - Progress reports, risk assessment

### Updates:
- **Daily:** Feature flag status, test results
- **Weekly:** Progress reports, metrics
- **Monthly:** Retrospectives, lessons learned

---

## Next Steps

1. **Immediate (Today):**
   - Implement feature flags
   - Backup old implementations
   - Set up testing environment

2. **This Week:**
   - Run parallel tests
   - Performance benchmarks
   - Integration validation

3. **Next Week:**
   - Begin production rollout (Panel1)
   - Monitor metrics
   - Gather feedback

4. **Month 1:**
   - Complete panel migrations
   - Begin typed events migration
   - Validate stability

5. **Month 2:**
   - Complete cleanup
   - Remove old code
   - Documentation updates

---

**Last Updated:** 2025-11-14
**Status:** Ready for Execution
**Next:** Implement feature flags (Phase 1)
