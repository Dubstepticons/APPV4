# Panel Contract - StateManager Integration Guide

## Overview

This document defines the **contract** between GUI Panels and StateManager. Following these rules ensures correct, race-free integration with the trading state machine.

**Target Audience**: Developers implementing or maintaining GUI panels (Panel 2, Panel 3, etc.)

---

## Core Principles

### 1. **Signal-Driven Updates Only**
- **DO**: React to StateManager signals (`modeChanged`, `balanceChanged`, `positionChanged`)
- **DON'T**: Poll StateManager state in timers or event loops
- **WHY**: StateManager uses atomic updates - reading state between signals may see inconsistent data

### 2. **Read State After Signals**
- **DO**: Read StateManager properties inside signal handlers
- **DON'T**: Cache state values across multiple signal emissions
- **WHY**: State can change between signals - always read fresh data

### 3. **Respect Mode Filtering**
- **DO**: Check `payload["mode"]` matches `panel.current_mode` before processing
- **DON'T**: Mix SIM and LIVE data in the same panel
- **WHY**: Prevents "ghost positions" and cross-contamination

---

## StateManager Public API

### Read-Only Properties (Safe to Access)

```python
from core.state_manager import StateManager

state = StateManager()

# ===== TRADING MODE =====
state.current_mode: str              # Current active mode ("SIM", "LIVE", "DEBUG")

# ===== BALANCE =====
state.sim_balance: float             # SIM account balance
state.live_balance: float            # LIVE account balance
state.active_balance: float          # Balance for currently open trade (position_mode)

# ===== POSITION =====
state.position_symbol: Optional[str]       # Symbol of open position (None if flat)
state.position_qty: int                    # Position quantity (0 if flat)
state.position_entry_price: float          # Average entry price
state.position_entry_time: Optional[datetime]  # Entry timestamp (None if recovered from DTC)
state.position_side: Optional[str]         # "LONG" or "SHORT" (None if flat)
state.position_mode: Optional[str]         # Mode of open position (None if flat)
state.position_recovered_from_dtc: bool    # True if position was recovered without entry_time

# ===== POSITION HELPERS =====
state.has_active_position() -> bool        # True if position is open (qty != 0)
state.get_open_trade_mode() -> Optional[str]  # Mode of open position (None if flat)
```

### Methods Panels Should **NEVER** Call

```python
# ❌ DEPRECATED - DO NOT USE
state.update_position(...)           # Raises RuntimeError - use open_position()/close_position()
state.set_positions(...)             # Raises RuntimeError - positions are managed internally
state.set(key, value)                # Direct _state writes - use dedicated methods only
state.update(dict)                   # Batch _state writes - use dedicated methods only

# ⚠️ INTERNAL USE ONLY
state.open_position(...)             # Reserved for MessageRouter and DTC recovery
state.close_position()               # Reserved for MessageRouter and DTC recovery
state.begin_state_update()           # Reserved for StateManager internal atomicity
state.end_state_update()             # Reserved for StateManager internal atomicity
```

### Safe Methods for Panels

```python
# Mode switching (request only - StateManager decides if allowed)
state.request_mode_change(mode: str, account: str = "") -> bool

# Balance queries
state.get_balance_for_mode(mode: str) -> float

# Mode validation
state.is_mode_blocked(mode: str) -> bool
```

---

## Signal Emission Order (CRITICAL)

StateManager emits signals in **STRICT ORDER** during atomic updates:

```
1. modeChanged(new_mode: str)      # Mode switch
2. balanceChanged(balance: float)  # Balance update
3. positionChanged(data: dict)     # Position update
```

**Why This Matters**:
- Panels that receive `positionChanged` can trust that `current_mode` is already updated
- Prevents displaying LIVE position with SIM mode label
- Ensures balance matches the mode before position is shown

**Example Flow**:
```python
# StateManager executes:
state.begin_state_update()
state._emit_signal("mode", "LIVE")      # Buffered
state._emit_signal("balance", 50000)    # Buffered
state._emit_signal("position", {...})   # Buffered
state.end_state_update()                # Emits ALL in order: mode → balance → position

# Panel receives (in order):
1. on_mode_changed("LIVE")           # Updates panel.current_mode
2. on_balance_changed(50000)         # Updates balance display
3. on_position_changed({...})        # Position sees correct mode + balance
```

---

## Mode Filtering Implementation

### Panel-Side Filtering (Panel 2 & Panel 3)

Every panel should filter messages by mode **before processing**:

```python
class TradingPanel:
    def __init__(self):
        self.current_mode = "SIM"  # Track active mode

        # Connect to StateManager signals
        state.modeChanged.connect(self.on_mode_changed)
        state.positionChanged.connect(self.on_position_changed)

    def on_mode_changed(self, new_mode: str):
        """Mode switch signal - update panel mode"""
        self.current_mode = new_mode
        self.refresh_ui()  # Clear stale data from old mode

    def on_position_changed(self, data: dict):
        """Position update signal - ALWAYS filter by mode"""
        # CRITICAL: Mode filtering guard
        payload_mode = data.get("mode")
        if payload_mode and payload_mode != self.current_mode:
            log.debug(f"Skipping position update for mode={payload_mode} (current={self.current_mode})")
            return  # Skip - wrong mode

        # Process position update (mode matches)
        action = data.get("action")  # "open" or "close"
        if action == "open":
            self._display_position(data)
        elif action == "close":
            self._close_position(data)
```

### Why Mode Filtering Is Required

Without mode filtering, you'll see:
- ❌ SIM positions showing in LIVE panel
- ❌ LIVE positions showing in SIM panel
- ❌ Positions persisting after mode switch
- ❌ Balance from wrong mode contaminating display

With mode filtering:
- ✅ SIM panel only shows SIM data
- ✅ LIVE panel only shows LIVE data
- ✅ Mode switches clear old data
- ✅ No cross-contamination

---

## Signal Payloads Reference

### `modeChanged` Signal

```python
def on_mode_changed(self, new_mode: str):
    """
    Emitted when trading mode changes.

    Args:
        new_mode: New mode string ("SIM", "LIVE", "DEBUG")

    Actions:
        - Update panel.current_mode
        - Clear UI for old mode
        - Refresh data for new mode
    """
```

### `balanceChanged` Signal

```python
def on_balance_changed(self, balance: float):
    """
    Emitted when balance updates for current_mode.

    Args:
        balance: New balance for the mode that changed

    Notes:
        - For SIM mode changes: balance = state.sim_balance
        - For LIVE mode changes: balance = state.live_balance
        - Check state.current_mode to know which mode changed

    Actions:
        - Update balance display
        - Recalculate risk metrics
    """
```

### `positionChanged` Signal

```python
def on_position_changed(self, data: dict):
    """
    Emitted when position opens or closes.

    Args:
        data: Position change dict with structure:

        OPEN ACTION:
        {
            "action": "open",
            "symbol": "ESH25",
            "qty": 2,
            "entry_price": 5800.25,
            "side": "LONG",
            "mode": "SIM"
        }

        CLOSE ACTION:
        {
            "action": "close",
            "trade_record": {
                "symbol": "ESH25",
                "side": "LONG",
                "qty": 2,
                "entry_time": datetime(...),
                "entry_price": 5800.25,
                "entry_vwap": 5801.0,
                "entry_cum_delta": 1500,
                "mode": "SIM"
            }
        }

    Actions:
        - ALWAYS check data["mode"] vs panel.current_mode first
        - If action="open": Display position in UI
        - If action="close": Remove position, record trade to DB
    """
```

---

## Common Patterns

### Pattern 1: Panel Initialization

```python
class TradingPanel(QWidget):
    def __init__(self, state: StateManager):
        super().__init__()
        self.state = state
        self.current_mode = state.current_mode  # Sync initial mode

        # Connect signals
        state.modeChanged.connect(self.on_mode_changed)
        state.balanceChanged.connect(self.on_balance_changed)
        state.positionChanged.connect(self.on_position_changed)

        # Initial UI sync
        self.refresh_balance()
        self.refresh_position()

    def refresh_balance(self):
        """Read balance from StateManager (safe to call anytime)"""
        balance = self.state.get_balance_for_mode(self.current_mode)
        self.balance_label.setText(f"${balance:,.2f}")

    def refresh_position(self):
        """Read position from StateManager (safe to call anytime)"""
        if self.state.has_active_position():
            # Check mode matches before displaying
            if self.state.position_mode == self.current_mode:
                self._display_position(
                    symbol=self.state.position_symbol,
                    qty=self.state.position_qty,
                    price=self.state.position_entry_price
                )
        else:
            self._clear_position_display()
```

### Pattern 2: Mode Switch Handling

```python
def on_mode_changed(self, new_mode: str):
    """Handle mode switch - clear old mode data"""
    old_mode = self.current_mode
    self.current_mode = new_mode

    log.info(f"Panel mode switched: {old_mode} → {new_mode}")

    # Clear UI for old mode
    self._clear_position_display()
    self._clear_orders_display()

    # Refresh data for new mode
    self.refresh_balance()
    self.refresh_position()

    # Update mode indicator in UI
    self.mode_label.setText(new_mode)
    self.mode_label.setStyleSheet(
        "color: red;" if new_mode == "LIVE" else "color: green;"
    )
```

### Pattern 3: Position Update with Mode Guard

```python
def on_position_changed(self, data: dict):
    """Handle position update with proper mode filtering"""
    # STEP 1: Mode filtering guard
    payload_mode = data.get("mode")
    if payload_mode and payload_mode != self.current_mode:
        log.debug(f"Ignoring position for mode={payload_mode} (current={self.current_mode})")
        return

    # STEP 2: Handle action
    action = data.get("action")

    if action == "open":
        # New position opened
        symbol = data.get("symbol")
        qty = data.get("qty")
        price = data.get("entry_price")
        side = data.get("side")

        log.info(f"Position opened: {symbol} {side} {qty} @ {price}")
        self._display_position(symbol, qty, price, side)

    elif action == "close":
        # Position closed
        trade = data.get("trade_record", {})
        symbol = trade.get("symbol")

        log.info(f"Position closed: {symbol}")
        self._clear_position_display()

        # Record trade to database
        self._record_closed_trade(trade)
```

---

## Testing Your Panel Integration

### Unit Test Template

```python
import pytest
from unittest.mock import Mock
from core.state_manager import StateManager

def test_panel_filters_wrong_mode():
    """Test that panel rejects updates from non-matching mode"""
    state = StateManager()
    panel = TradingPanel(state)

    # Set panel to SIM mode
    panel.current_mode = "SIM"

    # Send LIVE position update (should be ignored)
    panel.on_position_changed({
        "action": "open",
        "mode": "LIVE",
        "symbol": "ESH25",
        "qty": 1
    })

    # Verify no position displayed
    assert panel.position_label.text() == ""

def test_panel_accepts_matching_mode():
    """Test that panel accepts updates from matching mode"""
    state = StateManager()
    panel = TradingPanel(state)

    # Set panel to SIM mode
    panel.current_mode = "SIM"

    # Send SIM position update (should be accepted)
    panel.on_position_changed({
        "action": "open",
        "mode": "SIM",
        "symbol": "ESH25",
        "qty": 2,
        "entry_price": 5800.25
    })

    # Verify position displayed
    assert "ESH25" in panel.position_label.text()
    assert "2" in panel.position_label.text()
```

### Integration Test Checklist

- [ ] Panel initializes with correct mode from StateManager
- [ ] Panel responds to `modeChanged` signal
- [ ] Panel filters position updates by mode
- [ ] Panel filters order updates by mode (if applicable)
- [ ] Panel clears old data when mode switches
- [ ] Panel displays balance for correct mode
- [ ] Panel handles position closures (qty=0)
- [ ] Panel handles DTC reconnection gracefully

---

## Troubleshooting

### Issue: Panel shows SIM and LIVE positions simultaneously

**Cause**: Missing mode filtering guard in `on_position_changed()`

**Fix**:
```python
def on_position_changed(self, data: dict):
    # ADD THIS:
    payload_mode = data.get("mode")
    if payload_mode and payload_mode != self.current_mode:
        return  # Skip wrong mode
    # ... rest of handler
```

### Issue: Position display doesn't update after mode switch

**Cause**: Panel not refreshing data in `on_mode_changed()` handler

**Fix**:
```python
def on_mode_changed(self, new_mode: str):
    self.current_mode = new_mode
    self._clear_position_display()  # Clear old mode data
    self.refresh_position()         # ADD THIS: Load new mode data
```

### Issue: Panel reads stale state values

**Cause**: Caching state values instead of reading fresh in signal handlers

**Fix**:
```python
# ❌ WRONG: Caching state
def __init__(self, state):
    self.cached_balance = state.sim_balance  # Stale!

# ✅ RIGHT: Read fresh in handler
def on_balance_changed(self, balance: float):
    self.balance_label.setText(f"${balance:,.2f}")  # Fresh!
```

### Issue: RuntimeError when calling `state.update_position()`

**Cause**: Calling deprecated method

**Fix**: Don't call `update_position()` from panels. StateManager manages positions internally via MessageRouter.

---

## Migration Guide (Legacy Code)

If your panel currently uses deprecated patterns, migrate as follows:

### Old Pattern → New Pattern

```python
# ❌ OLD: Direct state writes
state.update_position(symbol, qty, price)

# ✅ NEW: Let MessageRouter handle it (panels should NOT call this)
# Positions are updated automatically from DTC messages

# ❌ OLD: Reading _state dictionary
positions = state._state.get("positions", {})

# ✅ NEW: Use public properties
if state.has_active_position():
    symbol = state.position_symbol
    qty = state.position_qty

# ❌ OLD: Polling state in timer
def on_timer(self):
    self.update_position_display()

# ✅ NEW: React to signals
def on_position_changed(self, data: dict):
    self.update_position_display()

# ❌ OLD: Accessing private fields
mode = state._current_mode

# ✅ NEW: Use public property
mode = state.current_mode
```

---

## Related Documentation

- [StateManager v2.0 Architecture](./STATE_MANAGER_GUIDE.md)
- [Mode Filtering Guide](./MODE_FILTERING_GUIDE.md)
- [Signal Bus Reference](./SIGNAL_BUS_GUIDE.md)
- [DTC Parser Reference](./DTC_PARSER_REFERENCE.md)

---

## Changelog

### 2025-01-XX - StateManager v2.0 Panel Contract
- ✅ Defined signal emission order (mode → balance → position)
- ✅ Documented mode filtering requirements
- ✅ Listed public API vs internal methods
- ✅ Added testing patterns and troubleshooting guide
- ✅ Deprecated `update_position()` and `_state` direct access
