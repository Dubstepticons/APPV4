"""
Test Script: Theme Mode Switching Verification

This script tests whether theme changes properly when switching modes.
It will simulate mode switching and verify that:
1. The THEME dictionary gets updated
2. Signals are emitted
3. Panels refresh their styling

Run this script while the app is running to test mode switching.
"""

import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

def test_theme_switching():
    """Test theme switching by cycling through all modes"""

    print("\n" + "="*80)
    print("THEME MODE SWITCHING TEST")
    print("="*80 + "\n")

    # Import after app is running
    from config.theme import THEME, switch_theme
    from config import settings

    modes = ["DEBUG", "SIM", "LIVE"]

    for mode in modes:
        print(f"\n{'='*80}")
        print(f"TESTING MODE: {mode}")
        print(f"{'='*80}\n")

        # Get current theme state before switch
        old_bg = THEME.get('bg_primary', 'N/A')
        print(f"[TEST] Before switch: bg_primary = {old_bg}")

        # Switch theme
        print(f"[TEST] Calling switch_theme('{mode.lower()}')")
        switch_theme(mode.lower())

        # Get new theme state after switch
        new_bg = THEME.get('bg_primary', 'N/A')
        print(f"[TEST] After switch: bg_primary = {new_bg}")

        # Verify theme changed
        expected_colors = {
            "DEBUG": "#1E1E1E",  # Dark gray
            "SIM": "#FFFFFF",     # White
            "LIVE": "#000000",    # Black
        }

        expected = expected_colors[mode]
        if new_bg == expected:
            print(f"[TEST]  Theme CORRECTLY updated to {mode}")
            print(f"[TEST]  bg_primary = {new_bg} (expected {expected})")
        else:
            print(f"[TEST]  Theme FAILED to update!")
            print(f"[TEST]  bg_primary = {new_bg} (expected {expected})")

        # Check other critical keys
        print(f"\n[TEST] Verifying all theme keys for {mode}:")
        critical_keys = ['bg_primary', 'bg_panel', 'card_bg', 'ink', 'text_primary']
        for key in critical_keys:
            value = THEME.get(key, 'MISSING')
            print(f"[TEST]   {key:20s} = {value}")

        print(f"\n[TEST] Sleeping 2 seconds before next mode...\n")
        time.sleep(2)

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

def test_mode_switching_with_signals():
    """Test mode switching using the hotkey simulation"""

    print("\n" + "="*80)
    print("MODE SWITCHING WITH SIGNALS TEST")
    print("="*80 + "\n")

    app = QApplication.instance()
    if not app:
        print("[TEST] ERROR: No QApplication instance found!")
        return

    # Find the main window
    main_window = None
    for widget in app.topLevelWidgets():
        if hasattr(widget, '_set_theme_mode'):
            main_window = widget
            break

    if not main_window:
        print("[TEST] ERROR: Could not find MainWindow!")
        return

    print(f"[TEST] Found MainWindow: {main_window}")

    from config.theme import THEME

    modes = ["DEBUG", "SIM", "LIVE"]

    for mode in modes:
        print(f"\n{'='*80}")
        print(f"TESTING MODE SWITCH VIA _set_theme_mode: {mode}")
        print(f"{'='*80}\n")

        old_bg = THEME.get('bg_primary', 'N/A')
        print(f"[TEST] Before: bg_primary = {old_bg}")

        # Use the MainWindow's method (this is what toolbar buttons use)
        print(f"[TEST] Calling main_window._set_theme_mode('{mode}')")
        main_window._set_theme_mode(mode)

        # Process events to allow signals to propagate
        app.processEvents()

        new_bg = THEME.get('bg_primary', 'N/A')
        print(f"[TEST] After: bg_primary = {new_bg}")

        expected_colors = {
            "DEBUG": "#1E1E1E",
            "SIM": "#FFFFFF",
            "LIVE": "#000000",
        }

        expected = expected_colors[mode]
        if new_bg == expected:
            print(f"[TEST]  Theme updated via _set_theme_mode")
        else:
            print(f"[TEST]  Theme failed to update via _set_theme_mode")

        print(f"\n[TEST] Sleeping 3 seconds to observe UI changes...\n")
        time.sleep(3)

    print("\n" + "="*80)
    print("SIGNAL TEST COMPLETE")
    print("="*80 + "\n")

def test_hotkey_simulation():
    """Simulate pressing Ctrl+Shift+M to cycle modes"""

    print("\n" + "="*80)
    print("HOTKEY SIMULATION TEST (Ctrl+Shift+M)")
    print("="*80 + "\n")

    from config import settings
    from config.theme import THEME

    print(f"[TEST] Current TRADING_MODE: {settings.TRADING_MODE}")
    print(f"[TEST] Current bg_primary: {THEME.get('bg_primary', 'N/A')}")

    print("\n[TEST] Now press Ctrl+Shift+M in the application window")
    print("[TEST] Watch the console output for debugging messages")
    print("[TEST] The theme should change when you press the hotkey")
    print("\n[TEST] Expected debug output:")
    print("[TEST]   1. [MODE DEBUG] About to apply theme for mode: ...")
    print("[TEST]   2. [MODE DEBUG] Found _set_theme_mode method, calling it")
    print("[TEST]   3. [THEME DEBUG] _set_theme_mode() called with mode='...'")
    print("[TEST]   4. [THEME SWITCH] Starting switch_theme('...')")
    print("[TEST]   5. [THEME SWITCH]  Successfully switched to theme: '...'")
    print("[TEST]   6. [THEME DEBUG] Emitting themeChanged signal")
    print("[TEST]   7. [THEME DEBUG] on_theme_changed() called")
    print("[TEST]   8. [THEME MIXIN] refresh_theme() called on Panel1/Panel2/Panel3")
    print("\n[TEST] If you don't see all these messages, the signal chain is broken!")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("APPSIERRA THEME MODE SWITCHING TEST SUITE")
    print("="*80)
    print("\nThis script must be run AFTER the application has started.")
    print("Run it in a separate terminal or import it in the app.\n")

    # Check if app is running
    app = QApplication.instance()
    if app:
        print("[TEST]  QApplication instance found - app is running")
        print("\n[TEST] Running Test 1: Basic Theme Switching")
        test_theme_switching()

        print("\n[TEST] Running Test 2: Mode Switching with Signals")
        test_mode_switching_with_signals()

        print("\n[TEST] Running Test 3: Hotkey Simulation Instructions")
        test_hotkey_simulation()

    else:
        print("[TEST]  No QApplication instance - app is not running")
        print("[TEST] Please start the application first, then run this test")
        print("\n[TEST] You can also import and run this test from within the app:")
        print("[TEST]   >>> from test_theme_mode_switching import test_theme_switching")
        print("[TEST]   >>> test_theme_switching()")
