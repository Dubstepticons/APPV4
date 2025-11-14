"""
test_theme_visual_debug.py

Visual theme test that actually shows theme changes.
Run this to see if widgets actually update when theme changes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore, QtTest
from config.theme import THEME, switch_theme, LIVE_THEME, SIM_THEME, DEBUG_THEME
from core.app_manager import MainWindow
from core.signal_bus import get_signal_bus, reset_signal_bus
from utils.logger import get_logger

log = get_logger(__name__)


def test_visual_theme_switch():
    """
    Actually create the MainWindow and test theme switching visually.
    This is the real integration test.
    """
    log.info("\n" + "="*80)
    log.info("VISUAL THEME TEST: Creating MainWindow and switching themes")
    log.info("="*80)

    # Create QApplication
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    print("\n[1] Creating MainWindow...")
    reset_signal_bus()

    try:
        window = MainWindow()
        print(f"    - Window created: {window}")
        print(f"    - Initial theme mode: {window.current_theme_mode}")

        # Process events
        app.processEvents()

        # Get initial state
        print(f"\n[2] Initial state (LIVE):")
        print(f"    - THEME['bg_primary']: {THEME.get('bg_primary')}")
        print(f"    - THEME['card_bg']: {THEME.get('card_bg')}")
        print(f"    - Window title: {window.windowTitle()}")

        # Switch to SIM
        print(f"\n[3] Calling window._set_theme_mode('SIM')...")
        window._set_theme_mode("SIM")
        print(f"    - Call completed")
        app.processEvents()
        print(f"    - Events processed")

        # Check state after SIM
        print(f"\n[4] After switching to SIM:")
        print(f"    - window.current_theme_mode: {window.current_theme_mode}")
        print(f"    - THEME['bg_primary']: {THEME.get('bg_primary')}")
        print(f"    - THEME['card_bg']: {THEME.get('card_bg')}")

        # Verify it actually switched
        expected_bg = SIM_THEME.get('bg_primary')
        actual_bg = THEME.get('bg_primary')
        if actual_bg == expected_bg:
            print(f"    [OK] bg_primary matches SIM theme")
        else:
            print(f"    [FAIL] bg_primary mismatch! Expected {expected_bg}, got {actual_bg}")
            return False

        # Switch to DEBUG
        print(f"\n[5] Calling window._set_theme_mode('DEBUG')...")
        window._set_theme_mode("DEBUG")
        app.processEvents()

        print(f"\n[6] After switching to DEBUG:")
        print(f"    - window.current_theme_mode: {window.current_theme_mode}")
        print(f"    - THEME['bg_primary']: {THEME.get('bg_primary')}")
        print(f"    - THEME['card_bg']: {THEME.get('card_bg')}")

        expected_bg = DEBUG_THEME.get('bg_primary')
        actual_bg = THEME.get('bg_primary')
        if actual_bg == expected_bg:
            print(f"    [OK] bg_primary matches DEBUG theme")
        else:
            print(f"    [FAIL] bg_primary mismatch! Expected {expected_bg}, got {actual_bg}")
            return False

        # Switch back to LIVE
        print(f"\n[7] Calling window._set_theme_mode('LIVE')...")
        window._set_theme_mode("LIVE")
        app.processEvents()

        print(f"\n[8] After switching back to LIVE:")
        print(f"    - window.current_theme_mode: {window.current_theme_mode}")
        print(f"    - THEME['bg_primary']: {THEME.get('bg_primary')}")
        print(f"    - THEME['card_bg']: {THEME.get('card_bg')}")

        expected_bg = LIVE_THEME.get('bg_primary')
        actual_bg = THEME.get('bg_primary')
        if actual_bg == expected_bg:
            print(f"    [OK] bg_primary matches LIVE theme")
        else:
            print(f"    [FAIL] bg_primary mismatch! Expected {expected_bg}, got {actual_bg}")
            return False

        # Check panels exist and have refresh_theme
        print(f"\n[9] Checking panels...")
        panels = [
            ("Panel1 (Balance)", window.panel_balance),
            ("Panel2 (Live)", window.panel_live),
            ("Panel3 (Stats)", window.panel_stats),
        ]

        all_good = True
        for panel_name, panel in panels:
            if panel is None:
                print(f"    [FAIL] {panel_name} is None!")
                all_good = False
            elif not hasattr(panel, 'refresh_theme'):
                print(f"    [FAIL] {panel_name} missing refresh_theme method!")
                all_good = False
            else:
                print(f"    [OK] {panel_name} exists and has refresh_theme")

        if not all_good:
            return False

        # Try calling refresh_theme on panels
        print(f"\n[10] Calling manual refresh_theme on all panels...")
        try:
            window.panel_balance.refresh_theme()
            print(f"    - Panel1.refresh_theme() OK")
        except Exception as e:
            print(f"    [FAIL] Panel1.refresh_theme() error: {e}")
            return False

        try:
            window.panel_live.refresh_theme()
            print(f"    - Panel2.refresh_theme() OK")
        except Exception as e:
            print(f"    [FAIL] Panel2.refresh_theme() error: {e}")
            return False

        try:
            window.panel_stats.refresh_theme()
            print(f"    - Panel3.refresh_theme() OK")
        except Exception as e:
            print(f"    [FAIL] Panel3.refresh_theme() error: {e}")
            return False

        print(f"\n[11] Closing window...")
        window.close()
        app.processEvents()

        print("\n" + "="*80)
        print("VISUAL TEST PASSED!")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        log.error(f"Visual test error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    log.info("="*80)
    log.info("STARTING VISUAL THEME DEBUG TEST")
    log.info("="*80)

    success = test_visual_theme_switch()
    sys.exit(0 if success else 1)
