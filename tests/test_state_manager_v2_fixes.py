"""
Test Suite: StateManager v2.0 Architectural Fixes

Tests all 9 architectural improvements:
1. update_position() disabled with RuntimeError
2. _state key whitelist enforcement
3. Duplicate position guards
4. Entry time None handling in recovery
5. Private mode properties with warnings
6. Signal emission order
7. positions property (legacy compatibility)
8. close_position() duplicate guard
9. Mode invariants

Run with: python tests/test_state_manager_v2_fixes.py
"""

import sys
import warnings
from datetime import datetime
from unittest.mock import Mock, MagicMock

sys.path.insert(0, "/home/user/APPV4")

# Mock PyQt6 before importing StateManager
class MockQObject:
    """Mock QObject that doesn't interfere with StateManager methods"""
    pass

class MockSignal:
    """Mock pyqtSignal that works like the real thing"""
    def __init__(self, *args):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for cb in self._callbacks:
            cb(*args, **kwargs)

# Create mock modules
mock_qtcore = type(sys)('QtCore')
mock_qtcore.QObject = MockQObject
mock_qtcore.pyqtSignal = lambda *args: MockSignal(*args)

mock_pyqt6 = type(sys)('PyQt6')
mock_pyqt6.QtCore = mock_qtcore

sys.modules['PyQt6'] = mock_pyqt6
sys.modules['PyQt6.QtCore'] = mock_qtcore

# Import StateManager directly
import importlib.util
spec = importlib.util.spec_from_file_location("state_manager", "/home/user/APPV4/core/state_manager.py")
state_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state_manager_module)
StateManager = state_manager_module.StateManager


def test_update_position_disabled():
    """Test that update_position() raises RuntimeError"""
    print("Testing update_position() disabled...")

    state = StateManager()

    try:
        result = state.update_position("ESH25", 2, 5800.25)
        assert False, "update_position() should raise RuntimeError"
    except RuntimeError as e:
        error_msg = str(e)
        # Verify error message contains expected content
        assert "DISABLED" in error_msg or "incompatible" in error_msg
        assert "open_position" in error_msg  # Don't need exact parentheses
        assert "close_position" in error_msg
        print(f"  ✓ RuntimeError raised with correct message")
    except Exception as e:
        print(f"  DEBUG: Unexpected exception: {type(e).__name__}: {e}")
        raise

    print("✓ update_position() correctly disabled\n")


def test_state_key_whitelist():
    """Test that _state enforces strict key whitelist"""
    print("Testing _state key whitelist enforcement...")

    state = StateManager()

    # Test allowed keys
    try:
        state.set("last_update", datetime.now())
        state.set("active_symbol", "ESH25")
        print("  ✓ Allowed keys accepted")
    except ValueError:
        assert False, "Allowed keys should not raise ValueError"

    # Test deprecated keys (should warn but allow)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        state.set("positions", {})  # Deprecated key
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        print("  ✓ Deprecated keys trigger warning")

    # Test unknown keys (should block)
    try:
        state.set("unknown_key", "value")
        assert False, "Unknown keys should raise ValueError"
    except ValueError as e:
        assert "not allowed" in str(e)
        print("  ✓ Unknown keys blocked with ValueError")

    print("✓ _state key whitelist working correctly\n")


def test_duplicate_position_guard():
    """Test that open_position() skips duplicate calls"""
    print("Testing duplicate position guards...")

    state = StateManager()

    # Open position first time
    state.open_position("ESH25", 2, 5800.25, datetime.now(), "SIM")
    assert state.has_active_position()
    assert state.position_symbol == "ESH25"
    print("  ✓ First open_position() accepted")

    # Try to open same position again (should skip)
    signal_count_before = len(state._pending_signals)
    state.open_position("ESH25", 2, 5800.25, datetime.now(), "SIM")
    signal_count_after = len(state._pending_signals)

    # No new signals should be emitted (duplicate guard worked)
    assert signal_count_after == signal_count_before, "Duplicate should not emit signals"
    print("  ✓ Duplicate open_position() skipped")

    # Try with different qty (should NOT skip)
    state.open_position("ESH25", 3, 5800.25, datetime.now(), "SIM")
    assert state.position_qty == 3
    print("  ✓ Different qty accepted (not a duplicate)")

    print("✓ Duplicate position guards working correctly\n")


def test_close_position_duplicate_guard():
    """Test that close_position() handles duplicate calls"""
    print("Testing close_position() duplicate guard...")

    state = StateManager()

    # Close when flat (should skip)
    result = state.close_position()
    assert result is None
    print("  ✓ close_position() when flat returns None")

    # Open position then close
    state.open_position("ESH25", 2, 5800.25, datetime.now(), "SIM")
    result = state.close_position()
    assert result is not None
    assert result["symbol"] == "ESH25"
    print("  ✓ close_position() returns trade record")

    # Close again (should skip)
    result = state.close_position()
    assert result is None
    print("  ✓ Duplicate close_position() returns None")

    print("✓ close_position() duplicate guard working correctly\n")


def test_entry_time_none_recovery():
    """Test that entry_time=None is handled correctly"""
    print("Testing entry_time=None recovery...")

    state = StateManager()

    # Open position with None entry_time (simulates DTC recovery)
    state.open_position("ESH25", 2, 5800.25, None, "SIM")

    assert state.has_active_position()
    assert state.position_symbol == "ESH25"
    assert state.position_entry_time is None
    assert state.position_recovered_from_dtc is True
    print("  ✓ Position opened with None entry_time")
    print("  ✓ position_recovered_from_dtc flag set")

    # Open position with real entry_time
    state.open_position("NQM24", 1, 18500.0, datetime.now(), "LIVE")
    assert state.position_entry_time is not None
    assert state.position_recovered_from_dtc is False
    print("  ✓ Position with real entry_time clears recovery flag")

    print("✓ Entry time None handling working correctly\n")


def test_private_mode_properties():
    """Test that mode properties are private with controlled access"""
    print("Testing private mode properties...")

    state = StateManager()

    # Read current_mode (should work)
    mode = state.current_mode
    assert mode in ["SIM", "LIVE", "DEBUG"]
    print(f"  ✓ Reading current_mode works: {mode}")

    # Read position_mode (should work)
    pos_mode = state.position_mode
    assert pos_mode is None  # Flat initially
    print(f"  ✓ Reading position_mode works: {pos_mode}")

    # Check that private fields exist
    assert hasattr(state, "_current_mode")
    assert hasattr(state, "_position_mode")
    print("  ✓ Private _current_mode and _position_mode fields exist")

    print("✓ Private mode properties working correctly\n")


def test_signal_emission_order():
    """Test that signals are emitted in correct order (mode → balance → position)"""
    print("Testing signal emission order...")

    state = StateManager()

    # Track signal order
    signal_order = []

    def mode_handler(new_mode):
        signal_order.append("mode")

    def balance_handler(balance):
        signal_order.append("balance")

    def position_handler(data):
        signal_order.append("position")

    # Connect handlers
    state.modeChanged.connect(mode_handler)
    state.balanceChanged.connect(balance_handler)
    state.positionChanged.connect(position_handler)

    # Trigger atomic update with all three signals in WRONG order
    state.begin_state_update()
    state._emit_signal("position", {"action": "test"})  # Buffered third
    state._emit_signal("mode", "LIVE")                  # Buffered first
    state._emit_signal("balance", 50000)                # Buffered second
    state.end_state_update()                            # Emit in CORRECT order

    # Verify signals emitted in CORRECT order: mode → balance → position
    assert signal_order == ["mode", "balance", "position"], \
        f"Wrong signal order: {signal_order}"
    print(f"  ✓ Signals emitted in correct order: {' → '.join(signal_order)}")

    print("✓ Signal emission order enforced correctly\n")


def test_positions_property_legacy():
    """Test legacy positions property for backward compatibility"""
    print("Testing legacy positions property...")

    state = StateManager()

    # When flat, positions should be empty dict
    positions = state.positions
    assert positions == {}
    print("  ✓ positions property returns {} when flat")

    # Open position
    state.open_position("ESH25", 2, 5800.25, datetime.now(), "SIM")

    # positions property should return dict representation
    positions = state.positions
    assert "ESH25" in positions
    assert positions["ESH25"]["qty"] == 2
    assert positions["ESH25"]["mode"] == "SIM"
    print("  ✓ positions property returns position dict when open")

    # Test deprecated get_positions() method
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        pos_list = state.get_positions()
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert len(pos_list) == 1
        assert pos_list[0]["symbol"] == "ESH25"
        print("  ✓ get_positions() works with deprecation warning")

    # Test deprecated set_positions() method (should raise)
    try:
        state.set_positions([{"symbol": "NQM24", "qty": 1}])
        assert False, "set_positions() should raise RuntimeError"
    except RuntimeError as e:
        assert "open_position()" in str(e)
        print("  ✓ set_positions() raises RuntimeError")

    print("✓ Legacy positions property working correctly\n")


def test_mode_invariants():
    """Test that mode invariants are enforced"""
    print("Testing mode invariants...")

    state = StateManager()

    # Initially: current_mode set, position_mode None (flat)
    assert state.current_mode in ["SIM", "LIVE", "DEBUG"]
    assert state.position_mode is None
    print(f"  ✓ Initial state: current_mode={state.current_mode}, position_mode=None")

    # Open position: current_mode == position_mode
    state.open_position("ESH25", 2, 5800.25, datetime.now(), "LIVE")
    assert state.current_mode == "LIVE"
    assert state.position_mode == "LIVE"
    assert state.current_mode == state.position_mode
    print("  ✓ Invariant enforced: current_mode == position_mode when open")

    # Close position: position_mode = None
    state.close_position()
    assert state.position_mode is None
    assert not state.has_active_position()
    print("  ✓ Invariant enforced: position_mode = None when flat")

    print("✓ Mode invariants enforced correctly\n")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("StateManager v2.0 Architectural Fixes - Test Suite")
    print("="*70 + "\n")

    try:
        test_update_position_disabled()
        test_state_key_whitelist()
        test_duplicate_position_guard()
        test_close_position_duplicate_guard()
        test_entry_time_none_recovery()
        test_private_mode_properties()
        test_signal_emission_order()
        test_positions_property_legacy()
        test_mode_invariants()

        print("="*70)
        print("✓ ALL TESTS PASSED (9/9)")
        print("="*70 + "\n")

        print("StateManager v2.0 Fixes Verified:")
        print("  ✓ update_position() disabled with RuntimeError")
        print("  ✓ _state key whitelist enforced")
        print("  ✓ Duplicate position guards active")
        print("  ✓ Entry time None recovery working")
        print("  ✓ Private mode properties implemented")
        print("  ✓ Signal emission order enforced")
        print("  ✓ Legacy positions property compatible")
        print("  ✓ close_position() duplicate guard active")
        print("  ✓ Mode invariants enforced")
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
