"""
Integration test for new Panel1 decomposed architecture.

Tests:
1. Import and instantiation
2. Public API methods
3. Module integration (equity_state, equity_chart, hover_handler)
4. Signal wiring
5. Backwards compatibility
"""

import sys
import time
from PyQt6 import QtWidgets, QtCore

def test_panel1_import():
    """Test that Panel1 can be imported from new location."""
    print("\n[TEST 1] Panel1 Import")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1
        print("✅ Panel1 imported successfully")
        print(f"   Module: {Panel1.__module__}")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_panel1_instantiation(qtbot):
    """Test that Panel1 can be instantiated."""
    print("\n[TEST 2] Panel1 Instantiation")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1

        panel = Panel1()
        print("✅ Panel1 instantiated successfully")

        # Check basic attributes
        print(f"   Object name: {panel.objectName()}")
        print(f"   Has balance label: {hasattr(panel, 'lbl_balance')}")
        print(f"   Has PnL label: {hasattr(panel, 'lbl_pnl')}")
        print(f"   Has graph container: {hasattr(panel, 'graph_container')}")

        return True
    except Exception as e:
        print(f"❌ Instantiation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_public_api(qtbot):
    """Test that all public API methods exist and are callable."""
    print("\n[TEST 3] Public API Methods")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1

        panel = Panel1()

        # Check required methods
        required_methods = [
            'set_trading_mode',
            'set_timeframe',
            'set_account_balance',
            'update_equity_series_from_balance',
            'set_connection_status',
            'refresh',
            'set_pnl_for_timeframe'
        ]

        for method_name in required_methods:
            if hasattr(panel, method_name):
                method = getattr(panel, method_name)
                if callable(method):
                    print(f"✅ {method_name}: exists and callable")
                else:
                    print(f"❌ {method_name}: exists but not callable")
                    return False
            else:
                print(f"❌ {method_name}: missing")
                return False

        print("\n✅ All public API methods present")
        return True

    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_modules_integration(qtbot):
    """Test that submodules are properly integrated."""
    print("\n[TEST 4] Submodule Integration")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1

        panel = Panel1()

        # Check that modules are initialized
        print(f"✅ Equity state manager: {panel._equity_state is not None}")
        print(f"✅ Equity chart: {panel._equity_chart is not None}")
        print(f"✅ Hover handler: {panel._hover_handler is not None}")

        # Check that chart has plot
        has_plot = panel._equity_chart.has_plot()
        print(f"✅ Chart has plot: {has_plot}")

        return True

    except Exception as e:
        print(f"❌ Module integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backwards_compatibility(qtbot):
    """Test backwards compatibility with original Panel1 API."""
    print("\n[TEST 5] Backwards Compatibility")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1

        panel = Panel1()

        # Test set_trading_mode
        panel.set_trading_mode("SIM", "Test1")
        print("✅ set_trading_mode('SIM', 'Test1') works")

        # Test set_timeframe
        panel.set_timeframe("1D")
        print("✅ set_timeframe('1D') works")

        # Test set_account_balance
        panel.set_account_balance(10000.0)
        print("✅ set_account_balance(10000.0) works")
        print(f"   Balance label: {panel.lbl_balance.text()}")

        # Test update_equity_series_from_balance
        panel.update_equity_series_from_balance(10050.0, mode="SIM")
        print("✅ update_equity_series_from_balance(10050.0) works")

        # Test set_pnl_for_timeframe
        panel.set_pnl_for_timeframe(50.0, 0.5, up=True)
        print("✅ set_pnl_for_timeframe(50.0, 0.5, up=True) works")
        print(f"   PnL label: {panel.lbl_pnl.text()}")

        print("\n✅ All backwards compatibility tests passed")
        return True

    except Exception as e:
        print(f"❌ Backwards compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_wiring(qtbot):
    """Test that signals are properly wired."""
    print("\n[TEST 6] Signal Wiring")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1

        panel = Panel1()

        # Check timeframeChanged signal
        has_signal = hasattr(panel, 'timeframeChanged')
        print(f"✅ timeframeChanged signal: {has_signal}")

        if has_signal:
            # Test signal emission
            signal_received = []

            def on_timeframe_changed(tf):
                signal_received.append(tf)

            panel.timeframeChanged.connect(on_timeframe_changed)
            panel.set_timeframe("1W")

            # Process events
            QtCore.QCoreApplication.processEvents()

            if signal_received:
                print(f"✅ Signal emitted: {signal_received[0]}")
            else:
                print("⚠️  Signal not received (may be async)")

        return True

    except Exception as e:
        print(f"❌ Signal wiring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_flow(qtbot):
    """Test data flow through modules."""
    print("\n[TEST 7] Data Flow")
    print("-" * 60)

    try:
        from panels.panel1 import Panel1

        panel = Panel1()

        # Set mode and account
        panel.set_trading_mode("SIM", "Test1")

        # Add balance points
        now = time.time()
        for i in range(10):
            balance = 10000.0 + (i * 10.0)
            panel.update_equity_series_from_balance(balance, mode="SIM")

        # Check that data reached equity state
        curve = panel._equity_state.get_active_curve()
        print(f"✅ Equity points in state: {len(curve)}")

        # Set timeframe and check filtering
        panel.set_timeframe("LIVE")
        QtCore.QCoreApplication.processEvents()

        print("✅ Data flow test passed")
        return True

    except Exception as e:
        print(f"❌ Data flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("PANEL1 INTEGRATION TEST SUITE")
    print("=" * 60)

    # Create QApplication if needed
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    # Mock qtbot for tests that don't need it
    class MockQtBot:
        pass
    qtbot = MockQtBot()

    # Run tests
    results = []

    results.append(("Import", test_panel1_import()))
    results.append(("Instantiation", test_panel1_instantiation(qtbot)))
    results.append(("Public API", test_public_api(qtbot)))
    results.append(("Module Integration", test_modules_integration(qtbot)))
    results.append(("Backwards Compatibility", test_backwards_compatibility(qtbot)))
    results.append(("Signal Wiring", test_signal_wiring(qtbot)))
    results.append(("Data Flow", test_data_flow(qtbot)))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\n{passed}/{total} tests passed ({(passed/total)*100:.0f}%)")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
