# Panel2 Final Modules - Specification

**Status:** Phase 3 - PositionDisplay Complete, OrderFlow & Panel2Main Remaining
**Date:** 2025-11-14

---

## Completed (Phase 3a)

### ✅ PositionDisplay (`panels/panel2/position_display.py` - 580 LOC)

Pure rendering layer for the 3x5 metrics grid.

**Features:**
- Renders all 15 metric cells
- Updates from PositionState + metrics dict
- Handles color logic (green/red by direction/sign)
- Handles flashing (heat cell, stop cell)
- Updates symbol and live price banners
- Pure UI - no business logic

**Usage:**
```python
display = PositionDisplay(
    c_price, c_heat, c_time, c_target, c_stop,
    c_risk, c_rmult, c_range, c_mae, c_mfe,
    c_vwap, c_delta, c_poc, c_eff, c_pts,
    symbol_banner, live_banner
)

# Update from state
display.update(state, metrics, current_epoch=time.time())
```

**Benefits:**
✅ Pure rendering (no state)
✅ Easy to test in isolation
✅ Clear color rules
✅ Theme-aware
✅ No DTC dependencies

---

## Remaining Work

### 📋 OrderFlow (250 LOC) - Complex DTC Handling

**Purpose:** Process DTC order and position updates, manage position lifecycle

**Key Methods:**
1. `on_order_update(payload: dict)` - Handle OrderUpdate from DTC
   - Auto-detect stop/target from sell orders
   - Seed position in SIM mode (Sierra Chart quirk)
   - Detect trade closure (quantity decrease)
   - Build trade dict with P&L calculations
   - Emit tradeCloseRequested signal

2. `on_position_update(payload: dict)` - Handle PositionUpdate from DTC
   - Update position state from DTC
   - Extract symbol from position (not quote feed)
   - Detect trade closure (qty → 0)
   - Emit positionOpened/positionClosed signals

**DTC Protocol Quirks to Handle:**
- SIM mode: Never sends non-zero PositionUpdate (must seed from fills)
- Order detection: Infer stop/target from sell order prices
- Closure detection: Two paths (OrderUpdate qty decrease, PositionUpdate qty → 0)
- Missing data: Fallback to last_price if exit price missing

**Signals to Emit:**
```python
positionOpened = QtCore.pyqtSignal(object)   # PositionState
positionClosed = QtCore.pyqtSignal(dict)     # Trade dict
tradeCloseRequested = QtCore.pyqtSignal(dict)  # To TradeCloseService
```

**Complexity:** High
- ~140 LOC for on_order_update
- ~120 LOC for on_position_update
- Intricate DTC message handling
- Multiple closure paths
- Error handling for missing data

---

### 📋 Panel2Main (150 LOC) - Thin Orchestrator

**Purpose:** Wire all modules together, provide backwards-compatible API

**Structure:**
```python
class Panel2(QtWidgets.QWidget):
    """
    Main Panel2 orchestrator.

    Coordinates all submodules and provides backwards-compatible API.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create submodules
        self.csv_feed = CSVFeedHandler(SNAPSHOT_CSV_PATH)
        self.persistence = StatePersistence(mode="SIM", account="")
        self.indicators = VisualIndicators()
        self.display = PositionDisplay(...)
        self.order_flow = OrderFlow()

        # Current state
        self._state = PositionState.flat()

        # Wire signals
        self._connect_signals()

        # Load persisted state
        self._state = self.persistence.load_state()

        # Start CSV feed
        self.csv_feed.start()

    def _connect_signals(self):
        """Wire all module signals together."""
        # CSV feed → Update state → Update display
        self.csv_feed.feedUpdated.connect(self._on_feed_updated)

        # Order flow → Update state → Save → Update display
        self.order_flow.positionOpened.connect(self._on_position_opened)
        self.order_flow.positionClosed.connect(self._on_position_closed)

        # Indicators → Log/emit alerts
        self.indicators.heatWarning.connect(self._on_heat_warning)
        self.indicators.stopProximity.connect(self._on_stop_proximity)

    def _on_feed_updated(self, market_data: dict):
        """Handle CSV feed update."""
        # Update state with market data
        self._state = self._state.with_market_data(**market_data)

        # Calculate metrics
        metrics = MetricsCalculator.calculate_all(
            self._state,
            current_epoch=int(time.time())
        )

        # Update indicators
        self.indicators.update(self._state, current_epoch=int(time.time()))

        # Update display
        self.display.update(self._state, metrics, current_epoch=int(time.time()))

        # Persist state
        self.persistence.save_state(self._state)

    def _on_position_opened(self, state: PositionState):
        """Handle position opened."""
        self._state = state
        self.persistence.save_position_to_database(state)

    def _on_position_closed(self, trade: dict):
        """Handle position closed."""
        self._state = PositionState.flat(
            mode=self._state.current_mode,
            account=self._state.current_account
        )
        self.persistence.close_position_in_database()

    # Backwards-compatible API
    def on_order_update(self, payload: dict):
        """Delegate to order flow handler."""
        self.order_flow.on_order_update(payload)

    def on_position_update(self, payload: dict):
        """Delegate to order flow handler."""
        self.order_flow.on_position_update(payload)

    def set_trading_mode(self, mode: str, account: str):
        """Switch trading mode."""
        self._state = PositionState.flat(mode=mode, account=account)
        self.persistence = StatePersistence(mode=mode, account=account)
        loaded_state = self.persistence.load_state()
        if loaded_state:
            self._state = loaded_state

    def refresh(self):
        """Public refresh method (for tests)."""
        metrics = MetricsCalculator.calculate_all(self._state)
        self.display.update(self._state, metrics)
```

**Benefits:**
✅ Thin layer (just wiring)
✅ Clear signal routing
✅ Backwards-compatible API
✅ Easy to test
✅ Minimal logic

---

## Summary

| Module | LOC | Status | Complexity |
|--------|-----|--------|------------|
| PositionState | 430 | ✅ Complete | Low (data) |
| MetricsCalculator | 370 | ✅ Complete | Low (pure functions) |
| CSVFeedHandler | 340 | ✅ Complete | Low (file I/O) |
| StatePersistence | 340 | ✅ Complete | Medium (DB + JSON) |
| VisualIndicators | 320 | ✅ Complete | Low (state detection) |
| **PositionDisplay** | **580** | **✅ Complete** | **Low (rendering)** |
| **OrderFlow** | **250** | **📋 Pending** | **High (DTC quirks)** |
| **Panel2Main** | **150** | **📋 Pending** | **Low (wiring)** |
| **TOTAL** | **2,780** | **75%** | - |

---

## Implementation Notes

### OrderFlow Challenges

1. **SIM Mode Quirk:** Sierra Chart never sends PositionUpdate with non-zero qty in SIM mode
   - Solution: Seed position from OrderUpdate fills
   - Requires detecting first fill vs subsequent fills

2. **Closure Detection:** Two different paths
   - Path 1: OrderUpdate with decreasing quantity
   - Path 2: PositionUpdate with qty → 0
   - Must handle both without double-closing

3. **Stop/Target Detection:** Not sent explicitly by DTC
   - Solution: Infer from sell order prices relative to entry
   - Lower than entry = stop, higher = target

4. **Missing Data:** Exit price may not be in OrderUpdate
   - Fallback chain: LastFillPrice → AverageFillPrice → Price1 → last_price

5. **Mode Detection:** Must derive from account string
   - "Sim103" → SIM
   - "120005" → LIVE
   - "" → DEBUG

### Panel2Main Challenges

1. **Signal Wiring:** Complex signal graph
   - CSV → State → Display
   - OrderFlow → State → Persistence → Display
   - Indicators → Alerts → Display

2. **State Management:** Current state is shared
   - Must coordinate updates across modules
   - Immutable PositionState helps prevent mutations

3. **Backwards Compatibility:** Old Panel2 API must work
   - on_order_update(), on_position_update()
   - set_trading_mode(), refresh()
   - get_current_trade_data()

---

## Next Steps

### 1. Extract OrderFlow (High Priority, High Complexity)

**Estimated Effort:** 2-3 hours
**Risk:** Medium (complex DTC protocol handling)

**Approach:**
- Extract on_order_update() method (~140 LOC)
- Extract on_position_update() method (~120 LOC)
- Create OrderFlow class with signal emissions
- Handle all DTC quirks and edge cases
- Add comprehensive error handling

### 2. Create Panel2Main (Medium Priority, Low Complexity)

**Estimated Effort:** 1-2 hours
**Risk:** Low (mostly wiring)

**Approach:**
- Create thin orchestrator class
- Wire all module signals
- Implement backwards-compatible API
- Add mode switching logic
- Integration testing

### 3. Integration Testing (High Priority)

**Estimated Effort:** 2-3 hours
**Risk:** Medium (coordination bugs)

**Approach:**
- Test full signal flow (CSV → Display)
- Test order flow (DTC → Closure → Persistence)
- Test mode switching
- Test error cases
- Performance testing

### 4. Migration (Low Priority Initially)

**Estimated Effort:** 1-2 hours
**Risk:** Low (gradual rollout)

**Approach:**
- Add feature flag `USE_NEW_PANEL2`
- Test both versions in parallel
- Gradual migration
- Remove old Panel2 when confident

---

## Architecture Benefits (Already Achieved)

From the 6 completed modules:

✅ **Modularity:** 6 focused modules vs 1 monolith (1,930 LOC)
✅ **Testability:** Each module independently testable
✅ **Thread Safety:** Immutable PositionState + Qt signals
✅ **Clarity:** 300-400 LOC files with single responsibilities
✅ **Reusability:** MetricsCalculator, VisualIndicators reusable
✅ **Type Safety:** Full type hints throughout
✅ **Error Handling:** Graceful degradation at all layers
✅ **Documentation:** Comprehensive docstrings

---

## Conclusion

**Phase 3a Complete:** PositionDisplay extracted (580 LOC)
**Remaining:** OrderFlow (250 LOC) + Panel2Main (150 LOC) = 400 LOC
**Progress:** 75% complete (2,380 / 2,780 LOC)

The foundation is solid - all data, I/O, and UI rendering layers are complete.
The remaining work (OrderFlow + Panel2Main) involves intricate DTC protocol
handling and module wiring, but the patterns are established and clear.

**Recommendation:** Complete OrderFlow and Panel2Main in next session when
sufficient time is available for careful DTC protocol handling and testing.

---

**Last Updated:** 2025-11-14
**Next Milestone:** OrderFlow extraction + Panel2Main creation
