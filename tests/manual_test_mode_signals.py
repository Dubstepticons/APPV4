"""
Manual test script for mode-specific signal namespacing (no pytest required).

Run with: python tests/manual_test_mode_signals.py
"""

import sys
sys.path.insert(0, "/home/user/APPV4")

from utils.signal_bus import SignalBus, ModeNamespace


def test_mode_namespace_creation():
    """Test ModeNamespace initialization."""
    print("Testing ModeNamespace creation...")

    sim_ns = ModeNamespace("SIM")
    assert sim_ns.mode == "SIM", "Mode attribute failed"
    assert hasattr(sim_ns, "position"), "Missing position signal"
    assert hasattr(sim_ns, "order"), "Missing order signal"
    assert hasattr(sim_ns, "balance"), "Missing balance signal"
    assert hasattr(sim_ns, "trade_account"), "Missing trade_account signal"

    print("✓ ModeNamespace creation passed")


def test_signal_bus_initialization():
    """Test SignalBus with mode namespaces."""
    print("Testing SignalBus initialization...")

    bus = SignalBus()
    assert hasattr(bus, "sim"), "Missing SIM namespace"
    assert hasattr(bus, "live"), "Missing LIVE namespace"
    assert hasattr(bus, "debug"), "Missing DEBUG namespace"
    assert isinstance(bus.sim, ModeNamespace), "SIM not ModeNamespace"
    assert isinstance(bus.live, ModeNamespace), "LIVE not ModeNamespace"

    # Global signals
    assert hasattr(bus, "position"), "Missing global position"
    assert hasattr(bus, "order"), "Missing global order"

    print("✓ SignalBus initialization passed")


def test_emit_to_global_only():
    """Test emission to global signal without mode."""
    print("Testing global signal emission...")

    bus = SignalBus()
    global_received = []
    sim_received = []

    # Subscribe to both
    bus.position.connect(lambda sender, **kwargs: global_received.append(kwargs))
    bus.sim.position.connect(lambda sender, **kwargs: sim_received.append(kwargs))

    # Emit without mode
    bus.emit_all("position", {"symbol": "ESH25", "qty": 2})

    # Only global should receive
    assert len(global_received) == 1, f"Global received {len(global_received)}, expected 1"
    assert len(sim_received) == 0, f"SIM received {len(sim_received)}, expected 0"

    print("✓ Global emission passed")


def test_emit_with_sim_mode():
    """Test emission with SIM mode routing."""
    print("Testing SIM mode routing...")

    bus = SignalBus()
    global_received = []
    sim_received = []
    live_received = []

    # Subscribe to all three
    bus.position.connect(lambda sender, **kwargs: global_received.append(kwargs))
    bus.sim.position.connect(lambda sender, **kwargs: sim_received.append(kwargs))
    bus.live.position.connect(lambda sender, **kwargs: live_received.append(kwargs))

    # Emit with SIM mode
    bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 2})

    # Global and SIM should receive, LIVE should not
    assert len(global_received) == 1, f"Global received {len(global_received)}, expected 1"
    assert len(sim_received) == 1, f"SIM received {len(sim_received)}, expected 1"
    assert len(live_received) == 0, f"LIVE received {len(live_received)}, expected 0"

    print("✓ SIM mode routing passed")


def test_emit_with_live_mode():
    """Test emission with LIVE mode routing."""
    print("Testing LIVE mode routing...")

    bus = SignalBus()
    global_received = []
    sim_received = []
    live_received = []

    # Subscribe to all three
    bus.order.connect(lambda sender, **kwargs: global_received.append(kwargs))
    bus.sim.order.connect(lambda sender, **kwargs: sim_received.append(kwargs))
    bus.live.order.connect(lambda sender, **kwargs: live_received.append(kwargs))

    # Emit with LIVE mode
    bus.emit_with_mode("order", {"mode": "LIVE", "Symbol": "ESH25", "OrderStatus": 3})

    # Global and LIVE should receive, SIM should not
    assert len(global_received) == 1, f"Global received {len(global_received)}, expected 1"
    assert len(sim_received) == 0, f"SIM received {len(sim_received)}, expected 0"
    assert len(live_received) == 1, f"LIVE received {len(live_received)}, expected 1"

    print("✓ LIVE mode routing passed")


def test_cross_mode_isolation():
    """Test modes don't interfere with each other."""
    print("Testing cross-mode isolation...")

    bus = SignalBus()
    sim_calls = []
    live_calls = []

    bus.sim.position.connect(lambda sender, **kwargs: sim_calls.append(kwargs))
    bus.live.position.connect(lambda sender, **kwargs: live_calls.append(kwargs))

    # Emit multiple messages
    bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 1})
    bus.emit_with_mode("position", {"mode": "LIVE", "symbol": "NQM24", "qty": 2})
    bus.emit_with_mode("position", {"mode": "SIM", "symbol": "MESZ25", "qty": 3})

    # SIM should have 2, LIVE should have 1
    assert len(sim_calls) == 2, f"SIM calls: {len(sim_calls)}, expected 2"
    assert len(live_calls) == 1, f"LIVE calls: {len(live_calls)}, expected 1"
    assert sim_calls[0]["symbol"] == "ESH25", "SIM first symbol mismatch"
    assert sim_calls[1]["symbol"] == "MESZ25", "SIM second symbol mismatch"
    assert live_calls[0]["symbol"] == "NQM24", "LIVE symbol mismatch"

    print("✓ Cross-mode isolation passed")


def test_backward_compatibility():
    """Test backward compatibility with global signals."""
    print("Testing backward compatibility...")

    bus = SignalBus()
    received = []

    bus.position.connect(lambda sender, **kwargs: received.append(kwargs))

    # Emit without mode field (old behavior)
    bus.position.send({"symbol": "ESH25", "qty": 1})

    assert len(received) == 1, f"Received {len(received)}, expected 1"
    assert received[0]["symbol"] == "ESH25", "Payload mismatch"

    print("✓ Backward compatibility passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Mode-Specific Signals Manual Tests")
    print("="*60 + "\n")

    try:
        test_mode_namespace_creation()
        test_signal_bus_initialization()
        test_emit_to_global_only()
        test_emit_with_sim_mode()
        test_emit_with_live_mode()
        test_cross_mode_isolation()
        test_backward_compatibility()

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60 + "\n")
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
