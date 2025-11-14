"""
Quick Theme Test Runner

Run this script to automatically test theme switching in the running application.
This script will:
1. Cycle through DEBUG -> SIM -> LIVE modes
2. Print diagnostic output showing theme changes
3. Verify that the THEME dictionary updates correctly
4. Check if signals are being emitted

Usage:
    python run_theme_test.py
"""

import sys
import time
from pathlib import Path

# Add the app directory to path
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))


def run_automated_test():
    """Run automated theme switching test"""

    print("\n" + "="*100)
    print("AUTOMATED THEME SWITCHING TEST")
    print("="*100 + "\n")

    try:
        # Import the theme module
        from config.theme import THEME, switch_theme

        print("[TEST] [OK] Successfully imported theme module\n")

        # Define test modes and expected colors
        test_cases = [
            ("DEBUG", "#1E1E1E", "Dark Gray (Development Mode)"),
            ("SIM", "#FFFFFF", "White (Simulation Mode)"),
            ("LIVE", "#000000", "Black (Live Trading Mode)"),
        ]

        results = []

        for mode, expected_bg, description in test_cases:
            print(f"\n{'-'*100}")
            print(f"TEST CASE: {mode} - {description}")
            print(f"{'-'*100}\n")

            # Get current state
            old_bg = THEME.get('bg_primary', 'UNKNOWN')
            print(f"[BEFORE] bg_primary = {old_bg}")

            # Perform switch
            print(f"\n[ACTION] Calling switch_theme('{mode.lower()}')")
            print(f"{'-'*100}")
            switch_theme(mode.lower())
            print(f"{'-'*100}\n")

            # Get new state
            new_bg = THEME.get('bg_primary', 'UNKNOWN')
            print(f"[AFTER] bg_primary = {new_bg}")

            # Verify
            success = (new_bg == expected_bg)
            if success:
                print(f"[RESULT] [PASS] Theme correctly switched to {mode}")
                print(f"[RESULT] [OK] Color is {new_bg} (expected {expected_bg})")
                results.append(("PASS", mode, new_bg, expected_bg))
            else:
                print(f"[RESULT] [FAIL] Theme did not switch correctly!")
                print(f"[RESULT] [ERROR] Color is {new_bg} (expected {expected_bg})")
                results.append(("FAIL", mode, new_bg, expected_bg))

            # Show all theme values
            print(f"\n[THEME VALUES] Complete THEME dictionary for {mode}:")
            for key in ['bg_primary', 'bg_panel', 'card_bg', 'ink', 'text_primary',
                       'pnl_pos_color', 'pnl_neg_color']:
                value = THEME.get(key, 'MISSING')
                print(f"  {key:20s} = {value}")

            time.sleep(1)

        # Summary
        print(f"\n\n{'='*100}")
        print("TEST SUMMARY")
        print(f"{'='*100}\n")

        passed = sum(1 for r in results if r[0] == "PASS")
        failed = sum(1 for r in results if r[0] == "FAIL")

        for status, mode, actual, expected in results:
            icon = "[OK]" if status == "PASS" else "[FAIL]"
            print(f"  {icon} {mode:8s} - {status:5s} (actual: {actual:10s}, expected: {expected:10s})")

        print(f"\n  Total: {passed} passed, {failed} failed out of {len(results)} tests")

        if failed == 0:
            print(f"\n{'='*100}")
            print("[SUCCESS] ALL TESTS PASSED - Theme dictionary updates correctly")
            print(f"{'='*100}\n")
            print("\n[NEXT STEP] Now test with UI signals:")
            print("  1. Run the app: python main.py")
            print("  2. Press Ctrl+Shift+M to cycle modes")
            print("  3. Watch for debug output showing signal emission")
            print("  4. Verify that panel colors actually change in the UI")
        else:
            print(f"\n{'='*100}")
            print("[ERROR] SOME TESTS FAILED - Theme dictionary is not updating correctly")
            print(f"{'='*100}\n")

    except ImportError as e:
        print(f"[ERROR] Failed to import theme module: {e}")
        print("[ERROR] Make sure you're running this from the APPV4 directory")
        return False
    except Exception as e:
        print(f"[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    return failed == 0


if __name__ == "__main__":
    success = run_automated_test()
    sys.exit(0 if success else 1)
