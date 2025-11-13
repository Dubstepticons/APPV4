"""
Integration Test: End-to-End Mode Filtering Flow

Tests the complete flow from DTC message → Parser → Router → Panels
Validates that mode filtering works correctly across all layers.

Run with: python tests/integration/test_mode_filtering_flow.py
"""

import sys
import os

# Add APPV4 to path
sys.path.insert(0, "/home/user/APPV4")

# Import directly to avoid PyQt6 dependency
import importlib.util

spec = importlib.util.spec_from_file_location("dtc_parser", "/home/user/APPV4/core/dtc_parser.py")
dtc_parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dtc_parser)

parse_dtc_message = dtc_parser.parse_dtc_message
AppMessage = dtc_parser.AppMessage

from utils.signal_bus import SignalBus


class MockPanel:
    """Mock panel for testing mode filtering."""

    def __init__(self, mode: str = "SIM"):
        self.current_mode = mode
        self.current_account = ""
        self.position_updates = []
        self.order_updates = []

    def on_position_update(self, payload: dict):
        """Mock position update handler with mode filtering."""
        # MODE FILTERING (same as real panels)
        payload_mode = payload.get("mode")
        if payload_mode and payload_mode != self.current_mode:
            return  # Skip

        self.position_updates.append(payload)

    def on_order_update(self, payload: dict):
        """Mock order update handler with mode filtering."""
        # MODE FILTERING (same as real panels)
        payload_mode = payload.get("mode")
        if payload_mode and payload_mode != self.current_mode:
            return  # Skip

        self.order_updates.append(payload)


def test_dtc_parser_adds_mode():
    """Test that dtc_parser adds mode field to payloads."""
    print("Testing DTC parser mode tagging...")

    # Create mode map
    mode_map = {"120005": "LIVE", "Sim1": "SIM"}

    # Test LIVE position update
    dtc_msg = {
        "Type": 306,  # PositionUpdate
        "Symbol": "ESH25",
        "PositionQuantity": 2,
        "AveragePrice": 5800.25,
        "TradeAccount": "120005"
    }

    app_msg = parse_dtc_message(dtc_msg, mode_map=mode_map)
    assert app_msg is not None, "Parser returned None"
    assert app_msg.type == "POSITION_UPDATE", f"Wrong type: {app_msg.type}"
    assert app_msg.payload.get("mode") == "LIVE", f"Mode not added or wrong: {app_msg.payload.get('mode')}"

    # Test SIM order update
    dtc_msg = {
        "Type": 301,  # OrderUpdate
        "Symbol": "NQM24",
        "OrderStatus": 3,  # Filled
        "TradeAccount": "Sim1"
    }

    app_msg = parse_dtc_message(dtc_msg, mode_map=mode_map)
    assert app_msg is not None, "Parser returned None"
    assert app_msg.type == "ORDER_UPDATE", f"Wrong type: {app_msg.type}"
    assert app_msg.payload.get("mode") == "SIM", f"Mode not added or wrong: {app_msg.payload.get('mode')}"

    print("✓ DTC parser correctly tags messages with mode")


def test_panel_mode_filtering():
    """Test that panels filter messages based on mode."""
    print("Testing panel mode filtering...")

    # Create SIM panel
    sim_panel = MockPanel(mode="SIM")

    # Send SIM position update (should be accepted)
    sim_panel.on_position_update({
        "mode": "SIM",
        "symbol": "ESH25",
        "qty": 2,
        "avg_entry": 5800.25
    })

    # Send LIVE position update (should be rejected)
    sim_panel.on_position_update({
        "mode": "LIVE",
        "symbol": "NQM24",
        "qty": 1,
        "avg_entry": 18500.00
    })

    # Verify only SIM message was processed
    assert len(sim_panel.position_updates) == 1, f"Expected 1 update, got {len(sim_panel.position_updates)}"
    assert sim_panel.position_updates[0]["mode"] == "SIM", "Wrong mode processed"
    assert sim_panel.position_updates[0]["symbol"] == "ESH25", "Wrong symbol"

    print("✓ Panel correctly filters by mode")


def test_mode_switching_behavior():
    """Test panel behavior when switching modes."""
    print("Testing mode switching behavior...")

    panel = MockPanel(mode="SIM")

    # Send SIM update (accepted)
    panel.on_position_update({"mode": "SIM", "symbol": "ESH25", "qty": 1})
    assert len(panel.position_updates) == 1

    # Switch to LIVE mode
    panel.current_mode = "LIVE"

    # Send SIM update (rejected)
    panel.on_position_update({"mode": "SIM", "symbol": "ESH25", "qty": 2})
    assert len(panel.position_updates) == 1, "SIM update should be rejected after mode switch"

    # Send LIVE update (accepted)
    panel.on_position_update({"mode": "LIVE", "symbol": "NQM24", "qty": 1})
    assert len(panel.position_updates) == 2, "LIVE update should be accepted"
    assert panel.position_updates[1]["mode"] == "LIVE"

    print("✓ Mode switching works correctly")


def test_signal_bus_mode_routing():
    """Test mode-specific signal routing."""
    print("Testing mode-specific signal routing...")

    bus = SignalBus()

    sim_received = []
    live_received = []
    global_received = []

    # Connect handlers (using named functions, not lambdas)
    def sim_handler(sender, **kwargs):
        sim_received.append(kwargs)

    def live_handler(sender, **kwargs):
        live_received.append(kwargs)

    def global_handler(sender, **kwargs):
        global_received.append(kwargs)

    bus.sim.position.connect(sim_handler)
    bus.live.position.connect(live_handler)
    bus.position.connect(global_handler)

    # Emit SIM message
    bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 1})

    # Verify routing
    assert len(sim_received) == 1, f"SIM should receive 1, got {len(sim_received)}"
    assert len(live_received) == 0, f"LIVE should receive 0, got {len(live_received)}"
    assert len(global_received) == 1, f"Global should receive 1, got {len(global_received)}"

    # Emit LIVE message
    bus.emit_with_mode("position", {"mode": "LIVE", "symbol": "NQM24", "qty": 2})

    # Verify routing
    assert len(sim_received) == 1, "SIM count should not change"
    assert len(live_received) == 1, f"LIVE should receive 1, got {len(live_received)}"
    assert len(global_received) == 2, f"Global should receive 2, got {len(global_received)}"

    print("✓ Mode-specific signal routing works correctly")


def test_end_to_end_flow():
    """Test complete flow: DTC → Parser → Signal → Panel."""
    print("Testing end-to-end flow...")

    # Setup
    bus = SignalBus()
    mode_map = {"120005": "LIVE", "Sim1": "SIM"}
    sim_panel = MockPanel(mode="SIM")
    live_panel = MockPanel(mode="LIVE")

    # Connect panels to signals (using named functions)
    def sim_position_handler(sender, **kwargs):
        sim_panel.on_position_update(kwargs)

    def live_position_handler(sender, **kwargs):
        live_panel.on_position_update(kwargs)

    bus.sim.position.connect(sim_position_handler)
    bus.live.position.connect(live_position_handler)

    # Simulate DTC message flow

    # 1. LIVE position update comes in
    dtc_msg_live = {
        "Type": 306,
        "Symbol": "ESH25",
        "PositionQuantity": 2,
        "AveragePrice": 5800.25,
        "TradeAccount": "120005"
    }

    app_msg = parse_dtc_message(dtc_msg_live, mode_map=mode_map)
    assert app_msg is not None
    bus.emit_with_mode("position", app_msg.payload)

    # 2. SIM position update comes in
    dtc_msg_sim = {
        "Type": 306,
        "Symbol": "NQM24",
        "PositionQuantity": 1,
        "AveragePrice": 18500.00,
        "TradeAccount": "Sim1"
    }

    app_msg = parse_dtc_message(dtc_msg_sim, mode_map=mode_map)
    assert app_msg is not None
    bus.emit_with_mode("position", app_msg.payload)

    # Verify routing
    assert len(sim_panel.position_updates) == 1, f"SIM panel: expected 1, got {len(sim_panel.position_updates)}"
    assert len(live_panel.position_updates) == 1, f"LIVE panel: expected 1, got {len(live_panel.position_updates)}"

    assert sim_panel.position_updates[0]["symbol"] == "NQM24", "SIM panel got wrong symbol"
    assert live_panel.position_updates[0]["symbol"] == "ESH25", "LIVE panel got wrong symbol"

    print("✓ End-to-end flow works correctly")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("Testing edge cases...")

    # Test message without mode field
    panel = MockPanel(mode="SIM")
    panel.on_position_update({"symbol": "ESH25", "qty": 1})  # No mode field
    assert len(panel.position_updates) == 1, "Should accept message without mode field"

    # Test empty mode field
    panel.position_updates.clear()
    panel.on_position_update({"mode": "", "symbol": "ESH25", "qty": 1})
    assert len(panel.position_updates) == 1, "Should accept empty mode field"

    # Test None mode field
    panel.position_updates.clear()
    panel.on_position_update({"mode": None, "symbol": "ESH25", "qty": 1})
    assert len(panel.position_updates) == 1, "Should accept None mode field"

    print("✓ Edge cases handled correctly")


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("Integration Tests: Mode Filtering Flow")
    print("="*70 + "\n")

    try:
        test_dtc_parser_adds_mode()
        test_panel_mode_filtering()
        test_mode_switching_behavior()
        test_signal_bus_mode_routing()
        test_end_to_end_flow()
        test_edge_cases()

        print("\n" + "="*70)
        print("✓ ALL INTEGRATION TESTS PASSED (6/6)")
        print("="*70 + "\n")

        print("Summary:")
        print("  ✓ DTC parser correctly tags messages with mode")
        print("  ✓ Panels filter messages based on current_mode")
        print("  ✓ Mode switching prevents cross-contamination")
        print("  ✓ Signal bus routes to correct mode namespaces")
        print("  ✓ End-to-end flow maintains mode isolation")
        print("  ✓ Edge cases handled gracefully")
        print()

        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
