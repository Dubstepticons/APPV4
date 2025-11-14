# Order Routing Test Guide

## Overview
This guide helps you test and debug order routing from DTC → Panel2 → Panel3.

## How Order Routing Works

### Flow Diagram
```
DTC (Sierra Chart)
    ↓
    | PositionUpdate (Type 306)
    ↓
DataBridge._route_dtc_message()
    ↓
    | _normalize_position()
    ↓
SignalBus.positionUpdated.emit(payload)
    ↓
Panel2.on_position_update()
    ↓
    | Updates UI cells via _refresh_all_cells()
    ↓
Panel3.on_trade_closed()
    ↓
    | Updates stats table when trade closes
```

## Debug Logging Points

Panel2 now emits detailed logs at these points:

```
[Panel2] Position update received: qty=X, avg_entry=Y, symbol=Z, account=A
[Panel2] Position update accepted: symbol=X, qty=Y, avg=Z, long=True/False
[Panel2] Calling _refresh_all_cells() to update UI metrics
[Panel2] UI refresh complete
```

## Test Procedure

### 1. Check if Position Updates Are Reaching Panel2

**Expected Logs:**
When you place a trade in Sierra Chart, you should see:
```
[Panel2] Position update received: qty=2, avg_entry=5200.5, symbol=F.US.MESZ25, account=Sim1
[Panel2] Position update accepted: symbol=MES, qty=2, avg=5200.5, long=True
[Panel2] Calling _refresh_all_cells() to update UI metrics
[Panel2] UI refresh complete
```

**If you DON'T see these logs:**
- Panel2 is NOT receiving position updates
- Check the DTC connection status
- Verify that Sierra Chart is connected and sending PositionUpdate messages

### 2. Check CSV Feed Updates

Panel2 also requires the CSV feed to be updating for live prices.

**Expected Logs:**
Every 500ms you should see:
```
[panel2] Feed updated -- VWAP changed: 5200.25
[panel2] Feed updated -- Delta changed: 120
```

**If you DON'T see these logs:**
- CSV feed might not be updating
- Check that `C:\Users\cgrah\Desktop\APPSIERRA\data\snapshot.csv` exists and is being updated
- Check file permissions

### 3. Manual Test: Trigger Position Update

To manually test Panel2 updates without Sierra Chart:

```bash
cd "C:\Users\cgrah\OneDrive\Desktop\APPV4"
python test_panel2_update.py
```

This will:
1. Start the app
2. Emit a test position update signal
3. Verify Panel2 updates its metrics
4. Close the position
5. Verify Panel2 clears the metrics

### 4. Check Trade Closure

When you close a trade:

**Expected Logs:**
```
[TRADE CLOSE] MES 2 @ 5200.5 -> 5210.5 | P&L: +$100.00 | Mode: SIM
[Panel3] Restored from trade: MES long 2 shares, P&L: $100.00
```

**If you DON'T see the Panel3 log:**
- Trade closure event might not be reaching Panel3
- Check SignalBus.tradeClosedForAnalytics connections

## Troubleshooting

### Panel2 shows "--" for all metrics

**Cause:** Panel2 is not receiving position updates

**Fix:**
1. Check app logs for `[Panel2] Position update received` logs
2. If not present, DTC connection might be down
3. Restart DTC connection in Sierra Chart

### Panel2 shows metrics but they don't update

**Cause:** CSV feed not updating

**Fix:**
1. Check app logs for `[panel2] Feed updated` logs
2. If not present, verify snapshot.csv path and permissions
3. Restart the app

### Panel3 stats not updating after trade closes

**Cause:** Trade closed event not reaching Panel3

**Fix:**
1. Check for `[TRADE CLOSE]` logs
2. Check app logs for trade persistence errors
3. Verify database connection is active

## Key Files

- **Panel2:** `panels/panel2.py` (lines 597-712)
- **Panel3:** `panels/panel3.py` (lines 433+)
- **Data Bridge:** `core/data_bridge.py` (lines 116-135 for normalization)
- **Signal Bus:** `core/signal_bus.py` (lines 30-80 for signals)

## Production Checklist

- [ ] Panel2 updates when new position is opened
- [ ] Panel2 shows correct entry price and quantity
- [ ] Panel2 updates live metrics as price moves
- [ ] Panel2 clears metrics when position closes
- [ ] Panel3 updates stats when trade closes
- [ ] Trade P&L is correctly calculated
- [ ] No error logs appear during trading

## Performance Notes

- Position updates are queued via `Qt.QueuedConnection` for thread safety
- CSV feed updates every 500ms (configurable via `CSV_REFRESH_MS`)
- Live metrics update in real-time based on CSV ticks
- Trade persistence happens atomically via PositionRepository
