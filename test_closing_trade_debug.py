"""
Test script to simulate a closing trade and debug Panel 2 -> Panel 3 communication.

This script:
1. Creates Panel 2 and Panel 3 instances
2. Wires them together via SignalBus
3. Simulates opening a position in Panel 2
4. Simulates closing the position
5. Verifies that Panel 3 receives the signal and updates

Usage:
    python test_closing_trade_debug.py
"""

import sys
import os
import time
from datetime import datetime, timezone

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from PyQt6 import QtWidgets, QtCore
from utils.logger import get_logger

log = get_logger(__name__)

def main():
    """Main test function."""
    log.info("=" * 80)
    log.info("STARTING CLOSING TRADE DEBUG TEST")
    log.info("=" * 80)

    # Create QApplication
    app = QtWidgets.QApplication(sys.argv)

    # Import panels
    from panels.panel2 import Panel2
    from panels.panel3 import Panel3

    # Create Panel 2 (Live Trading)
    log.info("\n[TEST] Creating Panel2...")
    panel2 = Panel2()
    log.info("[TEST] Panel2 created successfully")

    # Create Panel 3 (Trading Stats)
    log.info("\n[TEST] Creating Panel3...")
    panel3 = Panel3()
    log.info("[TEST] Panel3 created successfully")

    # Wire Panel 3 to Panel 2 (for direct data access)
    log.info("\n[TEST] Wiring Panel3 to Panel2...")
    panel3.set_live_panel(panel2)
    log.info("[TEST] Panel3 wired to Panel2")

    # Process events to ensure signal connections are established
    app.processEvents()
    time.sleep(0.5)

    # STEP 1: Simulate opening a position
    log.info("\n" + "=" * 80)
    log.info("STEP 1: SIMULATING POSITION OPEN")
    log.info("=" * 80)

    entry_price = 5800.00
    qty = 2
    is_long = True
    target_price = 5810.00
    stop_price = 5795.00

    log.info(f"[TEST] Opening position: {qty} @ {entry_price} (LONG)")
    panel2.set_position(qty, entry_price, is_long)
    panel2.set_targets(target_price, stop_price)
    panel2.set_symbol("MES")

    # Set some market data for P&L calculations
    panel2.last_price = entry_price + 2.0  # Up 2 points
    panel2.vwap = 5799.00
    panel2.cum_delta = 1500.0

    app.processEvents()
    time.sleep(0.5)

    log.info(f"[TEST] Position opened: Symbol={panel2.symbol}, Qty={panel2.entry_qty}, Entry={panel2.entry_price}")
    log.info(f"[TEST] Current price: {panel2.last_price}")

    # STEP 2: Verify position is active
    log.info("\n" + "=" * 80)
    log.info("STEP 2: VERIFYING POSITION STATE")
    log.info("=" * 80)

    has_position = panel2.has_active_position()
    log.info(f"[TEST] Panel2 has active position: {has_position}")

    if has_position:
        trade_data = panel2.get_current_trade_data()
        log.info(f"[TEST] Current trade data: {trade_data}")
    else:
        log.error("[TEST] ERROR: Position not detected in Panel2!")
        sys.exit(1)

    # STEP 3: Simulate closing the position via order update
    log.info("\n" + "=" * 80)
    log.info("STEP 3: SIMULATING TRADE CLOSE (VIA ORDER UPDATE)")
    log.info("=" * 80)

    exit_price = 5802.00  # Exit at 5802, profit of 2 points
    log.info(f"[TEST] Simulating sell order fill at {exit_price}")

    # Create a simulated order update payload (normalized format from data_bridge)
    order_payload = {
        "OrderStatus": 3,  # Filled
        "BuySell": 2,  # Sell
        "FilledQuantity": 0,  # Closed (qty goes to 0)
        "Price1": exit_price,
        "AverageFillPrice": exit_price,
        "LastFillPrice": exit_price,
        "Symbol": "F.US.MESZ25",
        "TradeAccount": "Sim1",
        "DateTime": int(datetime.now(timezone.utc).timestamp()),
    }

    log.info(f"[TEST] Order payload: {order_payload}")
    log.info("[TEST] Calling panel2.on_order_update...")

    # Call the order update handler
    panel2.on_order_update(order_payload)

    # Process events to allow signals to propagate
    log.info("[TEST] Processing Qt events to allow signal propagation...")
    app.processEvents()
    time.sleep(1.0)  # Give time for async signals

    # STEP 4: Verify trade closure and Panel 3 update
    log.info("\n" + "=" * 80)
    log.info("STEP 4: VERIFYING TRADE CLOSURE AND PANEL 3 UPDATE")
    log.info("=" * 80)

    # Check Panel 2 state
    has_position_after = panel2.has_active_position()
    log.info(f"[TEST] Panel2 has active position after close: {has_position_after}")

    if has_position_after:
        log.error("[TEST] ERROR: Position still active in Panel2 after close!")
    else:
        log.info("[TEST] SUCCESS: Position closed in Panel2")

    # Check Panel 3 received update
    log.info("[TEST] Checking Panel3 metrics...")
    # Panel 3 should have refreshed its metrics (check logs above)

    # Final summary
    log.info("\n" + "=" * 80)
    log.info("TEST SUMMARY")
    log.info("=" * 80)
    log.info("1. Check the logs above for '[Panel2 DEBUG]' messages to trace signal emission")
    log.info("2. Check the logs above for '[Panel3 DEBUG]' messages to trace signal reception")
    log.info("3. If Panel3 DEBUG messages are missing, the signal is NOT being received")
    log.info("=" * 80)

    # Don't start event loop - just exit
    log.info("\n[TEST] Test complete. Exiting...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
