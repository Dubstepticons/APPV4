# Option 2: Full Refactor - Implementation Plan

**Date**: 2025-11-13
**Status**: In Progress
**Estimated Time**: 36-54 hours total

---

## Overview

Full architecture refactor to address monolithic files and inconsistent patterns:
1. **Priority #4**: Unify message passing on Qt signals (16-24h)
2. **Cleanup**: Fix redundancy hotspots (8-12h)
3. **Panel2 Refactor**: Use Position domain model (8-12h)
4. **Modularization**: Break Panel2 into modules (4-6h)

---

## Phase 1: Message Passing Audit ✅ COMPLETE

### Current State Analysis

**3 Message Passing Patterns Identified**:

#### 1. **Blinker Signals** (Legacy, Being Phased Out)
- Used by `data_bridge.DTCClientJSON`
- MessageRouter subscribes to Blinker signals
- **Location**: `core/message_router.py:86` - `_subscribe_to_signals()`
-**Events**:
  - `TRADE_ACCOUNT`
  - `BALANCE_UPDATE`
  - `POSITION_UPDATE`
  - `ORDER_UPDATE`
  - `MARKET_TRADE`
  - `MARKET_BIDASK`

#### 2. **Qt Signals** (Modern, Partially Adopted)
- **StateManager** (`core/state_manager.py`):
  - `modeChanged = QtCore.pyqtSignal(str)`
  - `balanceChanged = QtCore.pyqtSignal(float)`
  - `accountChanged = QtCore.pyqtSignal(str)`
- **DTCClientJSON** (`core/data_bridge.py`):
  - `session_ready = QtCore.pyqtSignal()`
  - `connected = QtCore.pyqtSignal()`
  - `disconnected = QtCore.pyqtSignal()`

#### 3. **Direct Method Calls** (Tight Coupling)
- **MessageRouter -> Panels**:
  - `panel_balance.update_balance()`
  - `panel_live.set_position()`
  - `panel_stats.update_stats()`
- **App Manager -> Panels**:
  - Direct panel method invocations
  - No decoupling

### Message Flow Map

```
DTC Thread → Blinker Signal → MessageRouter → Direct Call → Panel (Qt Thread)
                                    ↓
                              Trade Mode Detection
                                    ↓
                              StateManager.set_mode() → Qt Signal → Panels
```

### Migration Target

```
DTC Thread → SignalBus (Qt Signal) → Panel (Qt Thread)
                   ↓
         StateManager.mode_changed → Panel
```

**Benefits**: Single pattern, thread-safe, testable, decoupled

---

## Phase 2: Create SignalBus ⚠️ IN PROGRESS

### SignalBus Design

**File**: `core/signal_bus.py`

**Events to Support**:

1. **Account Events**
   - `tradeAccountReceived(dict)` - TradeAccount response
   - `balanceUpdated(float, str)` - Balance + account
   - `accountChanged(str)` - Account switched

2. **Position Events**
   - `positionOpened(object)` - Position domain object
   - `positionUpdated(dict)` - Position update from DTC
   - `positionClosed(dict)` - Trade record

3. **Order Events**
   - `orderFillReceived(dict)` - Order fill
   - `orderUpdateReceived(dict)` - Order status update
   - `orderRejected(str)` - Rejection reason

4. **Market Data Events**
   - `marketTradeReceived(dict)` - Trade tick
   - `marketBidAskReceived(dict)` - BBO update
   - `priceUpdated(str, float)` - Symbol, price (derived)

5. **Session Events**
   - `dtcConnected()` - DTC session established
   - `dtcDisconnected()` - DTC session lost
   - `sessionReady()` - Ready for requests

6. **Mode Events** (migrate from StateManager)
   - `modeChanged(str)` - SIM/LIVE/DEBUG
   - `modeSwitchRequested(str)` - User clicked mode button

### Implementation Plan

1. Create `core/signal_bus.py` with SignalBus class
2. Add singleton accessor: `get_signal_bus()`
3. Emit signals from DTCClientJSON instead of Blinker
4. Connect panels to SignalBus in app_manager.py
5. Keep Blinker temporarily for backward compat
6. Remove MessageRouter after migration complete

---

## Phase 3: Migrate MessageRouter ⏳ PENDING

### Step-by-Step Migration

#### 3.1 DTCClientJSON Emit Qt Signals
**File**: `core/data_bridge.py`

**Changes**:
- Import `get_signal_bus()`
- Replace Blinker emits with Qt signals:
  ```python
  # Before
  trade_account_received.send(sender=self, data=msg)

  # After
  signal_bus = get_signal_bus()
  signal_bus.tradeAccountReceived.emit(msg)
  ```

#### 3.2 Panels Subscribe to SignalBus
**Files**: `panels/panel1.py`, `panels/panel2.py`, `panels/panel3.py`

**Changes**:
- Remove direct method calls from MessageRouter
- Connect to SignalBus in `__init__`:
  ```python
  signal_bus = get_signal_bus()
  signal_bus.balanceUpdated.connect(self._on_balance_updated)
  signal_bus.positionUpdated.connect(self._on_position_updated)
  ```

#### 3.3 Remove MessageRouter
**File**: `core/app_manager.py`

**Changes**:
- Remove MessageRouter instantiation (line 709)
- Remove router parameter from DTCClientJSON
- Update _connect_dtc_signals() to use SignalBus

---

## Phase 4: Replace Direct Calls ⏳ PENDING

### Panel Communication Patterns to Replace

#### Pattern 1: app_manager → panel (direct call)
**Before**:
```python
self.panel_live.set_position(qty=1, entry_price=5800)
```

**After**:
```python
signal_bus.positionOpened.emit(Position.open(...))
```

#### Pattern 2: panel → panel (direct call)
**Before**:
```python
self.parent().panel_balance.refresh()
```

**After**:
```python
signal_bus.balanceRefreshRequested.emit()
```

### Files to Update

1. `core/app_manager.py` - Remove direct panel calls
2. `panels/panel1.py` - Use signals for cross-panel communication
3. `panels/panel2.py` - Emit signals instead of calling parent
4. `panels/panel3.py` - Subscribe to signals

---

## Phase 5: Code Cleanup ⏳ PENDING

### Top Priority Files (From REDUNDANCY_CLEANUP_PLAN.md)

#### 1. `services/dtc_json_client.py` - Score: 20
- Replace 5 try-except-pass with `contextlib.suppress()`
- Flatten 4 nested if statements
- Wrap file operation with context manager

#### 2. `panels/panel1.py` - Score: 18
- Replace 8 try-except-pass with `contextlib.suppress()`
- Add logging before suppressing exceptions
- Flatten nested conditionals

#### 3. `panels/panel2.py` - Score: 11
- Replace 3 nested if statements
- Remove unused variable
- Use ternary operator where applicable

#### 4. `core/message_router.py` - Score: 10
- Will be DELETED after migration complete

#### 5. `core/app_manager.py` - Score: 10
- Replace 3 try-except-pass
- Flatten 2 nested if statements

---

## Phase 6: Panel2 Refactor ⏳ PENDING

### Goal: Use Position Domain Model

**Current State** (1800+ lines, mixed concerns):
```python
class Panel2:
    def __init__(self):
        self.entry_qty = 0
        self.entry_price = None
        self.is_long = None
        self.entry_vwap = None
        # ... 20+ position fields scattered

    def calculate_unrealized_pnl(self):
        if self.entry_qty and self.last_price:
            diff = self.last_price - self.entry_price
            pnl = diff * self.entry_qty * DOLLARS_PER_POINT
            if not self.is_long:
                pnl = -pnl
            return pnl
        return 0.0
```

**Target State** (simplified, separated concerns):
```python
class Panel2:
    def __init__(self):
        from domain.position import Position
        self._position = Position.flat(mode="SIM", account="")

    @property
    def unrealized_pnl(self) -> float:
        return self._position.unrealized_pnl(self.last_price)
```

### Refactor Steps

1. **Replace position fields with Position object**
   - Create `_position: Position` attribute
   - Remove scattered position fields
   - Update all references

2. **Replace P&L calculations with Position methods**
   - `unrealized_pnl` → `_position.unrealized_pnl(price)`
   - `realized_pnl` → `_position.realized_pnl(exit_price)`
   - MAE/MFE → `_position.mae()` / `_position.mfe()`

3. **Update cell display methods**
   - Pull values from `_position` instead of `self.*`
   - Simplify display logic

4. **Update signal handlers**
   - `_on_position_opened(position: Position)`
   - `_on_position_updated(dict)`
   - `_on_position_closed(dict)`

---

## Phase 7: Modularize Panel2 ⏳ PENDING

### Target Structure

```
panels/
  panel2/
    __init__.py           # Main Panel2 class
    position_display.py   # Position info cells (entry, target, stop)
    pnl_display.py        # P&L calculation cells (unrealized, MAE, MFE)
    vwap_display.py       # VWAP/POC/CumDelta cells
    chart_integration.py  # Chart interaction logic
    bracket_orders.py     # Bracket order handling
```

### Module Breakdown (Estimated Lines)

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `__init__.py` | 400 | Main panel, layout, signal routing |
| `position_display.py` | 200 | Entry qty/price/time, duration |
| `pnl_display.py` | 250 | P&L, MAE, MFE, efficiency, R-multiple |
| `vwap_display.py` | 150 | VWAP, POC, CumDelta entry snapshots |
| `chart_integration.py` | 300 | Chart clicks, VWAP updates |
| `bracket_orders.py` | 250 | Target/stop management |

**Total**: ~1550 lines (down from 1800+)

### Benefits

✅ **Readability**: Each module has single responsibility
✅ **Testability**: Modules testable in isolation
✅ **Maintainability**: Changes localized to one file
✅ **Reusability**: Modules can be reused in other panels
✅ **Navigation**: Easier to find relevant code

---

## Success Criteria

### Phase 1-2: SignalBus Creation
- [ ] SignalBus class created with all required signals
- [ ] Singleton accessor works
- [ ] No regressions in existing functionality

### Phase 3: MessageRouter Migration
- [ ] All Blinker signals replaced with Qt signals
- [ ] All panels connected to SignalBus
- [ ] MessageRouter can be deleted
- [ ] No runtime errors or missing messages

### Phase 4: Direct Call Elimination
- [ ] All panel-to-panel calls use signals
- [ ] App manager uses signals
- [ ] Tests pass

### Phase 5: Cleanup
- [ ] Top 5 redundancy hotspots fixed
- [ ] Ruff SIM violations reduced by 50%+
- [ ] Code complexity improved

### Phase 6: Panel2 Position Model
- [ ] Panel2 uses Position domain object
- [ ] All P&L calculations use Position methods
- [ ] Position fields consolidated
- [ ] No functionality regression

### Phase 7: Panel2 Modularization
- [ ] Panel2 split into 6 modules
- [ ] Each module < 400 lines
- [ ] All tests passing
- [ ] Application works end-to-end

---

## Timeline Estimate

| Phase | Task | Estimate |
|-------|------|----------|
| 1 | Audit (DONE) | ✅ 2h |
| 2 | Create SignalBus | 2h |
| 3 | Migrate MessageRouter | 6h |
| 4 | Replace Direct Calls | 10h |
| 5 | Code Cleanup | 10h |
| 6 | Panel2 Refactor | 10h |
| 7 | Panel2 Modularization | 6h |
| **Total** | | **46 hours** |

**Realistic Schedule**: 5-6 working days (8h/day)

---

## Risk Mitigation

1. **Regressions**: Create integration tests before refactoring
2. **Thread Safety**: Qt signals are thread-safe by design
3. **Testing**: Manual testing after each phase
4. **Rollback**: Git commits after each phase completes
5. **Incremental**: Can stop after any phase if time constrained

---

## Current Status

- ✅ Phase 1 Complete: Audit finished
- 🔄 Phase 2 In Progress: Creating SignalBus
- ⏳ Phases 3-7: Pending

**Next Action**: Create `core/signal_bus.py`
