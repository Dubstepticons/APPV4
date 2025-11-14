# Phase 7: Integration Testing Plan

**Date**: 2025-11-13
**Status**: Ready for Implementation
**Prerequisites**: Phases 1-6 Complete ✅

---

## Overview

Phase 7 completes the position state architecture by validating that all components work together correctly under real-world conditions.

**Objectives**:
1. Verify crash recovery restores position state accurately
2. Validate mode switching preserves position isolation
3. Confirm thread safety under concurrent load
4. Test database transaction integrity

---

## Test Suite 1: Crash Recovery Flow

### Test 1.1: Basic Crash Recovery (SIM Mode)

**Scenario**: Application crashes with open SIM position, restart and verify recovery.

**Steps**:
1. Start application in SIM mode
2. Open position: LONG 1 MES @ 5800
3. Wait 10 seconds (let trade extremes update)
4. Verify database has OpenPosition record:
   ```sql
   SELECT * FROM openposition WHERE mode='SIM';
   ```
5. **Kill application** (simulate crash): `kill -9 <pid>`
6. Restart application
7. Verify recovery dialog appears with position details
8. Check Panel2 displays: LONG 1 MES @ 5800
9. Verify entry snapshots restored (VWAP, delta, POC)
10. Verify trade extremes restored (min/max prices)

**Expected Results**:
- ✅ Recovery dialog shows correct position
- ✅ Panel2 displays all position fields
- ✅ Entry time shows duration from original entry
- ✅ MAE/MFE calculations use full price history

**Validation**:
```python
# Database query
assert db.query(OpenPosition).filter_by(mode='SIM').count() == 1

# Position state
assert panel2.entry_qty == 1
assert panel2.entry_price == 5800.0
assert panel2.is_long == True

# Extremes
assert panel2._trade_min_price is not None
assert panel2._trade_max_price is not None
```

### Test 1.2: Crash Recovery with LIVE Position

**Scenario**: Crash with LIVE position, verify recovery shows warning.

**Steps**:
1. Start in LIVE mode (account="120005")
2. Open position: SHORT 2 MNQ @ 21000
3. Kill application
4. Restart
5. Verify recovery dialog shows:
   - Position details
   - **WARNING**: LIVE position detected, verify with broker

**Expected Results**:
- ✅ Recovery dialog includes broker verification warning
- ✅ LIVE position restored to Panel2
- ✅ User can manually close if stale

### Test 1.3: Stale Position Detection (>24h)

**Scenario**: Position older than 24 hours, verify stale warning.

**Steps**:
1. Manually insert old position in database:
   ```python
   old_time = datetime.now(UTC) - timedelta(hours=25)
   position = OpenPosition(
       mode='SIM', account='', symbol='MES',
       qty=1, entry_price=5800,
       entry_time=old_time, updated_at=old_time
   )
   db.add(position)
   ```
2. Start application
3. Verify recovery dialog shows:
   - **STALE** warning (>24h old)
   - Option to manually close

**Expected Results**:
- ✅ Stale positions flagged in recovery dialog
- ✅ User can delete without creating trade record
- ✅ No automatic position restoration

---

## Test Suite 2: Mode Switching

### Test 2.1: SIM → LIVE → SIM with Open Position

**Scenario**: Mode switching preserves separate position state.

**Steps**:
1. Start in SIM mode
2. Open SIM position: LONG 1 MES @ 5800
3. Verify Panel2 shows position
4. Switch to LIVE mode (Sierra Chart sends Type 401 LIVE account)
5. Verify Panel2 clears (no LIVE position)
6. Verify SIM position still in database:
   ```sql
   SELECT * FROM openposition WHERE mode='SIM';
   ```
7. Switch back to SIM mode
8. Verify Panel2 restores original position: LONG 1 MES @ 5800

**Expected Results**:
- ✅ SIM position preserved in database during LIVE mode
- ✅ Panel2 shows correct position for each mode
- ✅ No state leakage between modes

**Validation**:
```python
# In SIM mode
assert panel2.entry_qty == 1
assert panel2.current_mode == 'SIM'

# Switch to LIVE
state_manager.set_mode('120005')  # LIVE account
assert panel2.entry_qty == 0  # Cleared
assert panel2.current_mode == 'LIVE'

# Database still has SIM position
assert db.query(OpenPosition).filter_by(mode='SIM').count() == 1

# Switch back to SIM
state_manager.set_mode('')  # SIM account
assert panel2.entry_qty == 1  # Restored
assert panel2.entry_price == 5800.0
```

### Test 2.2: LIVE Position Blocks SIM Mode Switch

**Scenario**: Cannot switch to SIM while LIVE position open.

**Steps**:
1. Start in LIVE mode
2. Open LIVE position: LONG 1 MES @ 5800
3. Attempt to switch to SIM mode
4. Verify switch blocked (mode remains LIVE)
5. Close LIVE position
6. Retry SIM switch - should succeed

**Expected Results**:
- ✅ SIM mode blocked while LIVE position open
- ✅ Mode switch allowed after position closed

### Test 2.3: Concurrent Positions (SIM + LIVE different accounts)

**Scenario**: Can have SIM and LIVE positions open simultaneously (different accounts).

**Steps**:
1. Manually create two positions:
   ```python
   sim_pos = OpenPosition(mode='SIM', account='', symbol='MES', qty=1, ...)
   live_pos = OpenPosition(mode='LIVE', account='120005', symbol='MNQ', qty=2, ...)
   ```
2. Start application
3. Switch between modes
4. Verify correct position shown for each mode

**Expected Results**:
- ✅ Both positions exist in database
- ✅ Panel2 shows correct position for current mode
- ✅ Unique constraint (mode, account) enforced

---

## Test Suite 3: Thread Safety

### Test 3.1: Concurrent Position Updates

**Scenario**: DTC thread updates position while GUI thread reads.

**Steps**:
1. Open position
2. Simulate rapid DTC updates (100 updates in 1 second):
   ```python
   def dtc_thread():
       for price in range(5800, 5900):
           position_repo.update_trade_extremes('SIM', '', price)
           time.sleep(0.01)
   ```
3. Simultaneously query position from GUI thread
4. Verify no race conditions, data corruption, or deadlocks

**Expected Results**:
- ✅ No exceptions or crashes
- ✅ trade_min_price and trade_max_price correctly updated
- ✅ GUI reads consistent state

**Validation**: Use threading stress test
```python
import threading

def stress_test():
    errors = []
    def dtc_worker():
        try:
            for i in range(1000):
                repo.update_trade_extremes('SIM', '', 5800 + i % 100)
        except Exception as e:
            errors.append(e)

    def gui_worker():
        try:
            for i in range(1000):
                pos = repo.get_open_position('SIM', '')
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=dtc_worker),
        threading.Thread(target=gui_worker),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors: {errors}"
```

### Test 3.2: Concurrent Close Operations

**Scenario**: Prevent race condition where position closed twice.

**Steps**:
1. Open position
2. Trigger close from two threads simultaneously:
   ```python
   def close_worker():
       repo.close_position('SIM', '', exit_price=5850)

   t1 = threading.Thread(target=close_worker)
   t2 = threading.Thread(target=close_worker)
   t1.start()
   t2.start()
   ```
3. Verify exactly 1 TradeRecord created
4. Verify no database errors

**Expected Results**:
- ✅ Only one TradeRecord created
- ✅ Second close returns None (position not found)
- ✅ No IntegrityError or deadlock

---

## Test Suite 4: Database Transaction Integrity

### Test 4.1: Atomic Position Close

**Scenario**: Verify close operation is atomic (read + write + delete).

**Steps**:
1. Open position
2. During close operation, kill database connection mid-transaction
3. Restart and verify either:
   - Position still in OpenPosition (transaction rolled back)
   - OR Position moved to TradeRecord (transaction committed)
4. Never: Half-closed state (deleted from OpenPosition but not in TradeRecord)

**Expected Results**:
- ✅ No orphaned data
- ✅ Atomicity guaranteed by SQLAlchemy transaction

### Test 4.2: Database Lock Timeout

**Scenario**: Handle database lock timeout gracefully.

**Steps**:
1. Hold long-running transaction in one connection
2. Attempt update_trade_extremes in another connection
3. Verify timeout handled gracefully (no crash)

**Expected Results**:
- ✅ Operation returns False on timeout
- ✅ Error logged
- ✅ Trading continues

---

## Test Suite 5: End-to-End Scenarios

### Test 5.1: Full Trading Session

**Scenario**: Complete trading session from start to position close.

**Steps**:
1. Start application
2. Open position via DTC order fill
3. Position written to database
4. Trade extremes update every 500ms (10 updates)
5. Close position via DTC fill
6. Verify TradeRecord created with:
   - Correct entry/exit prices
   - MAE/MFE from extremes
   - Efficiency and R-multiple calculated
7. Verify OpenPosition deleted
8. Verify stats panel updates

**Expected Results**:
- ✅ Complete position lifecycle tracked
- ✅ All metrics accurate
- ✅ Database consistent

### Test 5.2: Multiple Trades in Session

**Scenario**: Multiple trades without restart.

**Steps**:
1. Trade 1: Open → Close
2. Trade 2: Open → Crash → Restart → Close
3. Trade 3: Open → Mode switch → Switch back → Close

**Expected Results**:
- ✅ All 3 trades in TradeRecord table
- ✅ P&L accumulated correctly
- ✅ No position leakage

---

## Test Infrastructure

### Manual Testing Checklist

```
[PHASE 7 INTEGRATION TESTS]

□ Test 1.1: Basic crash recovery (SIM)
□ Test 1.2: Crash recovery (LIVE with warning)
□ Test 1.3: Stale position detection
□ Test 2.1: Mode switching preserves positions
□ Test 2.2: LIVE blocks SIM switch
□ Test 2.3: Concurrent SIM + LIVE positions
□ Test 3.1: Concurrent position updates
□ Test 3.2: Concurrent close operations
□ Test 4.1: Atomic close transaction
□ Test 4.2: Database lock timeout
□ Test 5.1: Full trading session
□ Test 5.2: Multiple trades in session

[CRITICAL SCENARIOS]

□ Crash during position entry (mid-write)
□ Crash during position close (mid-transaction)
□ Network loss during trade
□ Database unavailable during update
□ Extremely rapid price updates (stress test)
```

### Automated Test Script

Location: `tests/integration/test_phase7_position_lifecycle.py`

**To implement**:
```python
import pytest
import threading
import time
from datetime import datetime, timezone, timedelta

from data.position_repository import get_position_repository
from data.schema import OpenPosition, TradeRecord
from services.position_recovery import get_recovery_service

class TestPhase7Integration:
    """Integration tests for position state architecture (Phase 7)."""

    def test_crash_recovery_sim_position(self, db_session):
        """Test 1.1: Basic crash recovery"""
        # ... implementation

    def test_mode_switching_preserves_positions(self, db_session, panel2):
        """Test 2.1: Mode switching"""
        # ... implementation

    def test_concurrent_updates_thread_safe(self, db_session):
        """Test 3.1: Thread safety"""
        # ... implementation

    # ... more tests
```

**Run with**:
```bash
pytest tests/integration/test_phase7_position_lifecycle.py -v
```

---

## Success Criteria

Phase 7 is complete when:

1. ✅ All 12 integration tests pass
2. ✅ No race conditions detected under load
3. ✅ Database integrity maintained under crash scenarios
4. ✅ Mode switching works correctly with positions
5. ✅ Recovery dialog tested with real user
6. ✅ Performance acceptable (updates don't lag UI)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Database corruption under crash | Atomic transactions, extensive testing |
| Position state inconsistency | Database is single source of truth |
| UI lag from DB writes | Async updates, optimized queries |
| Race conditions | Thread-safe repository, tested under load |
| Stale positions accumulate | Stale detection + manual cleanup UI |

---

## Timeline Estimate

- **Suite 1-2** (Crash + Mode): 4-6 hours
- **Suite 3** (Thread Safety): 3-4 hours
- **Suite 4** (Transactions): 2-3 hours
- **Suite 5** (End-to-End): 2-3 hours
- **Automation**: 4-6 hours

**Total**: 15-22 hours

---

**Status**: Documentation complete, ready for implementation
**Next Step**: Create `tests/integration/test_phase7_position_lifecycle.py`
