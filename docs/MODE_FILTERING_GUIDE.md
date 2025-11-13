# Mode Filtering Guide

## Overview

Mode filtering ensures that trading panels only display data for the **active trading mode** (SIM, LIVE, or DEBUG). This prevents the "both modes show same data" bug where SIM and LIVE positions would appear simultaneously in the same panel.

## Architecture

### Message Flow

```
DTC Message
    ↓
dtc_parser.py (adds 'mode' field based on TradeAccount)
    ↓
MessageRouter (routes to panels)
    ↓
Panel Handler (checks payload['mode'] vs panel.current_mode)
    ↓
Accept (if mode matches) OR Skip (if mode doesn't match)
```

### Key Components

#### 1. DTC Parser (`core/dtc_parser.py`)
- **Function**: `_add_mode_if_available(payload, mode_map)`
- **Purpose**: Tags every message with `mode` field based on TradeAccount
- **Example**:
  ```python
  # Input: {"TradeAccount": "120005", "Symbol": "ESH25", "qty": 2}
  # mode_map: {"120005": "LIVE", "Sim1": "SIM"}
  # Output: {"TradeAccount": "120005", "Symbol": "ESH25", "qty": 2, "mode": "LIVE"}
  ```

#### 2. Panel Handlers (`panels/panel2/trade_handlers.py`)
- **Functions**: `on_position_update()`, `on_order_update()`
- **Filter Logic**:
  ```python
  payload_mode = payload.get("mode")
  if payload_mode and payload_mode != panel.current_mode:
      log.debug(f"Skipping {msg_type} for mode={payload_mode} (current={panel.current_mode})")
      return  # Skip processing
  ```

#### 3. Statistics Panel (`panels/panel3.py`)
- **Function**: `register_order_event()`
- **Database Queries**: Filtered by mode in `stats_service.py`
- **Filter Logic**: Same as Panel 2

## Usage

### Panel 2 (Trading Panel)

```python
# Panel 2 automatically filters position/order updates
# You don't need to do anything special - it just works!

# Example: Panel in SIM mode
panel.current_mode = "SIM"

# SIM position update (ACCEPTED)
panel.on_position_update({
    "mode": "SIM",
    "symbol": "ESH25",
    "qty": 2,
    "avg_entry": 5800.25
})
# → Position displayed in panel

# LIVE position update (REJECTED)
panel.on_position_update({
    "mode": "LIVE",
    "symbol": "NQM24",
    "qty": 1,
    "avg_entry": 18500.00
})
# → Skipped, not displayed
```

### Panel 3 (Statistics Panel)

```python
# Panel 3 filters both:
# 1. Real-time order updates (via register_order_event)
# 2. Historical statistics queries (via stats_service)

# When in SIM mode:
panel._load_metrics_for_timeframe("1D")
# → Only shows SIM trades from past 1 day

# When switching to LIVE mode:
panel.current_mode = "LIVE"
panel._load_metrics_for_timeframe("1D")
# → Only shows LIVE trades from past 1 day
```

### Mode Switching

```python
# When user switches modes via state manager:
state_manager.request_mode_change("LIVE")
# → state_manager.modeChanged signal emitted
# → Panel 3 refreshes stats for new mode
# → Panel 2 starts accepting only LIVE messages
```

## Configuration

### Mode Mapping

The `mode_map` is built automatically from TRADE_ACCOUNT responses:

```python
# In data_bridge.py
self._mode_map = {}  # e.g., {"120005": "LIVE", "Sim1": "SIM"}

# When TRADE_ACCOUNT response arrives:
account = payload.get("account")  # "120005"
mode = detect_mode_from_account(account)  # "LIVE"
self._mode_map[account] = mode
```

### Mode Detection Rules

From `utils/trade_mode.py`:

```python
def detect_mode_from_account(account: str) -> str:
    """
    Detect trading mode from account string.

    Rules:
    - Contains "sim" (case-insensitive) → SIM
    - All digits (e.g., "120005") → LIVE
    - Otherwise → DEBUG
    """
    if "sim" in account.lower():
        return "SIM"
    elif account.isdigit():
        return "LIVE"
    else:
        return "DEBUG"
```

## Testing

### Unit Tests

```bash
# Test symbol utils
python tests/manual_test_symbol_utils.py

# Test mode signals
python tests/manual_test_mode_signals.py
```

### Integration Tests

```bash
# Test complete mode filtering flow
python tests/integration/test_mode_filtering_simple.py
```

### Expected Results

```
✓ ALL INTEGRATION TESTS PASSED (8/8)

Summary:
  ✓ Panels accept messages matching their mode
  ✓ Panels reject messages not matching their mode
  ✓ SIM and LIVE modes are isolated from each other
  ✓ Mode switching prevents cross-contamination
  ✓ Multiple messages from same mode handled correctly
  ✓ Mixed mode streams filtered correctly
  ✓ Order updates also filtered by mode
  ✓ Edge cases (no mode, empty mode, None) handled gracefully
```

## Debugging

### Enable Debug Logging

```python
# In config/settings.py
DEBUG_DTC = True

# Logs will show:
# [panel2] Skipping PositionUpdate for mode=LIVE (current=SIM)
# [panel3] Skipping OrderUpdate for mode=SIM (current=LIVE)
```

### Check Mode Map

```python
# In data_bridge.py, after handshake:
print(f"Mode map: {self._mode_map}")
# Expected: {'120005': 'LIVE', 'Sim1': 'SIM'}
```

### Verify Payload Mode Field

```python
# In dtc_parser.py, after normalization:
log.info(f"[DTC] PositionUpdate NORMALIZED: {payload}")
# Should include: "mode": "LIVE" or "mode": "SIM"
```

## Common Issues

### Issue: Both modes still showing same data
**Cause**: Mode map not populated (no TRADE_ACCOUNT responses received)
**Fix**: Check DTC handshake sequence, ensure TRADE_ACCOUNT request succeeds

### Issue: All messages rejected
**Cause**: `panel.current_mode` doesn't match any `payload['mode']`
**Fix**: Check mode detection rules, verify account string format

### Issue: Case sensitivity
**Cause**: Mode strings must be exact ("SIM" not "sim")
**Fix**: Ensure uppercase mode strings throughout

## Performance

- **Filtering Cost**: O(1) string comparison per message
- **Memory Impact**: Minimal (one additional string field per message)
- **Signal Overhead**: Mode-specific signals use Blinker's efficient dispatch

## Backward Compatibility

- Messages without `mode` field are accepted (backward compatible)
- Global signals (`bus.position`) still work for unfiltered subscriptions
- Existing code continues to function without changes

## Future Enhancements

### Mode-Specific Signal Subscriptions

```python
# Subscribe only to SIM positions
bus.sim.position.connect(sim_handler)

# Subscribe only to LIVE orders
bus.live.order.connect(live_handler)

# Still works: subscribe to all modes
bus.position.connect(global_handler)
```

### Symbol Canonicalization

```python
from utils.symbol_utils import canonicalize_symbol, symbols_match

# Normalize symbol formats
canonical = canonicalize_symbol("F.US.ESH25")  # → "ESH25"

# Match across formats
if symbols_match("ESH25", "F.US.ESH25"):
    print("Same contract!")
```

## Related Documentation

- [DTC Parser Reference](./DTC_PARSER_REFERENCE.md)
- [Signal Bus Guide](./SIGNAL_BUS_GUIDE.md)
- [Symbol Utils API](./SYMBOL_UTILS_API.md)
- [State Manager Guide](./STATE_MANAGER_GUIDE.md)

## Changelog

### Phase 2 (Options A, B, C)
- ✅ Added mode filtering to Panel 2 (`panels/panel2/trade_handlers.py`)
- ✅ Added mode filtering to Panel 3 (`panels/panel3.py`)
- ✅ Created symbol canonicalization utility (`utils/symbol_utils.py`)
- ✅ Added mode-specific signal namespacing (`utils/signal_bus.py`)
- ✅ Created comprehensive integration tests

### Phase 1
- ✅ Extracted DTC parser (`core/dtc_parser.py`)
- ✅ Added mode mapping in data bridge (`core/data_bridge.py`)
- ✅ Implemented `_add_mode_if_available()` for automatic mode tagging
