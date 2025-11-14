"""
test_theme_simple_debug.py

Simple theme test WITHOUT pytest-qt dependency.
Tests actual theme switching without Qt GUI.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.theme import (
    THEME, switch_theme,
    LIVE_THEME, SIM_THEME, DEBUG_THEME,
    ColorTheme
)
from utils.logger import get_logger

log = get_logger(__name__)


def test_1_theme_dict_switching():
    """Test 1: Verify THEME dict actually switches."""
    log.info("\n" + "="*80)
    log.info("TEST 1: Theme dictionary switching")
    log.info("="*80)

    print("\n[TEST 1] Switching THEME dict...")

    # Start with LIVE
    switch_theme("live")
    live_bg = THEME.get('bg_primary')
    print(f"After switch_theme('live'): bg_primary = {live_bg}")
    assert live_bg == LIVE_THEME.get('bg_primary'), "LIVE theme not applied"

    # Switch to SIM
    switch_theme("sim")
    sim_bg = THEME.get('bg_primary')
    print(f"After switch_theme('sim'): bg_primary = {sim_bg}")
    assert sim_bg == SIM_THEME.get('bg_primary'), "SIM theme not applied"
    assert sim_bg != live_bg, "SIM and LIVE have same background!"

    # Switch to DEBUG
    switch_theme("debug")
    debug_bg = THEME.get('bg_primary')
    print(f"After switch_theme('debug'): bg_primary = {debug_bg}")
    assert debug_bg == DEBUG_THEME.get('bg_primary'), "DEBUG theme not applied"

    print("\n[PASS] TEST 1 PASSED: Theme dict switches correctly\n")


def test_2_all_colors_present():
    """Test 2: Verify all critical colors exist in each theme."""
    log.info("\n" + "="*80)
    log.info("TEST 2: All critical colors present")
    log.info("="*80)

    critical_colors = [
        'bg_primary', 'bg_panel', 'card_bg', 'pnl_pos_color', 'pnl_neg_color',
        'text_primary', 'ink', 'border'
    ]

    for mode in ['live', 'sim', 'debug']:
        print(f"\nChecking {mode.upper()} theme...")
        switch_theme(mode)

        for color_key in critical_colors:
            value = THEME.get(color_key)
            assert value is not None, f"{mode}.{color_key} is None"
            assert value != "", f"{mode}.{color_key} is empty"
            print(f"  {color_key}: {value}")

    print("\n[PASS] TEST 2 PASSED: All critical colors present\n")


def test_3_color_theme_helpers():
    """Test 3: Verify ColorTheme helper functions work."""
    log.info("\n" + "="*80)
    log.info("TEST 3: ColorTheme helper functions")
    log.info("="*80)

    print("\nTesting ColorTheme.pnl_color_from_value()...")

    switch_theme("live")

    # Positive value
    pos_color = ColorTheme.pnl_color_from_value(100)
    print(f"  pnl_color_from_value(100) = {pos_color}")
    assert pos_color is not None, "pnl_color_from_value(100) returned None"

    # Negative value
    neg_color = ColorTheme.pnl_color_from_value(-100)
    print(f"  pnl_color_from_value(-100) = {neg_color}")
    assert neg_color is not None, "pnl_color_from_value(-100) returned None"

    # Neutral value
    neu_color = ColorTheme.pnl_color_from_value(0)
    print(f"  pnl_color_from_value(0) = {neu_color}")
    assert neu_color is not None, "pnl_color_from_value(0) returned None"

    # None value
    none_color = ColorTheme.pnl_color_from_value(None)
    print(f"  pnl_color_from_value(None) = {none_color}")
    assert none_color is not None, "pnl_color_from_value(None) returned None"

    print("\n[PASS] TEST 3 PASSED: ColorTheme helpers work correctly\n")


def test_4_theme_switch_cascade():
    """Test 4: Simulate theme switch cascade with debug output."""
    log.info("\n" + "="*80)
    log.info("TEST 4: Theme switch cascade simulation")
    log.info("="*80)

    print("\nSimulating theme change cascade: LIVE -> SIM -> DEBUG -> LIVE...")

    modes = ["LIVE", "SIM", "DEBUG", "LIVE"]

    for mode in modes:
        print(f"\n--- Switching to {mode} ---")
        switch_theme(mode.lower())

        # Verify critical keys updated
        bg = THEME.get('bg_primary')
        card = THEME.get('card_bg')
        pnl_pos = THEME.get('pnl_pos_color')

        print(f"THEME['bg_primary'] = {bg}")
        print(f"THEME['card_bg'] = {card}")
        print(f"THEME['pnl_pos_color'] = {pnl_pos}")

        # Verify mode matches
        if mode == "LIVE":
            assert bg == LIVE_THEME.get('bg_primary'), f"LIVE bg mismatch"
        elif mode == "SIM":
            assert bg == SIM_THEME.get('bg_primary'), f"SIM bg mismatch"
        elif mode == "DEBUG":
            assert bg == DEBUG_THEME.get('bg_primary'), f"DEBUG bg mismatch"

    print("\n[PASS] TEST 4 PASSED: Theme cascade works correctly\n")


def test_5_pnl_colors_different_per_mode():
    """Test 5: Verify PnL colors are different between modes."""
    log.info("\n" + "="*80)
    log.info("TEST 5: PnL colors differ per mode")
    log.info("="*80)

    print("\nVerifying PnL colors are mode-specific...")

    switch_theme("live")
    live_pnl_pos = THEME.get('pnl_pos_color')
    print(f"LIVE pnl_pos_color: {live_pnl_pos}")

    switch_theme("sim")
    sim_pnl_pos = THEME.get('pnl_pos_color')
    print(f"SIM pnl_pos_color:  {sim_pnl_pos}")

    switch_theme("debug")
    debug_pnl_pos = THEME.get('pnl_pos_color')
    print(f"DEBUG pnl_pos_color: {debug_pnl_pos}")

    # They should all be different
    assert live_pnl_pos != sim_pnl_pos, "LIVE and SIM have same PnL color"
    assert live_pnl_pos != debug_pnl_pos, "LIVE and DEBUG have same PnL color"
    assert sim_pnl_pos != debug_pnl_pos, "SIM and DEBUG have same PnL color"

    print("\n[PASS] TEST 5 PASSED: PnL colors are mode-specific\n")


def test_6_make_weak_color():
    """Test 6: Verify ColorTheme.make_weak_color works."""
    log.info("\n" + "="*80)
    log.info("TEST 6: make_weak_color function")
    log.info("="*80)

    print("\nTesting ColorTheme.make_weak_color()...")

    switch_theme("live")

    # Test with hex color
    weak = ColorTheme.make_weak_color("#20B36F", 0.35)
    print(f"make_weak_color('#20B36F', 0.35) = {weak}")
    assert "rgba" in weak, "make_weak_color should return rgba format"

    # Test with oklch
    weak_oklch = ColorTheme.make_weak_color("oklch(65% 0.20 140)", 0.35)
    print(f"make_weak_color('oklch(65% 0.20 140)', 0.35) = {weak_oklch}")
    assert "rgba" in weak_oklch, "make_weak_color should convert oklch to rgba"

    print("\n[PASS] TEST 6 PASSED: make_weak_color works correctly\n")


if __name__ == "__main__":
    log.info("="*80)
    log.info("STARTING SIMPLE THEME DEBUG TEST SUITE (No Qt GUI)")
    log.info("="*80)

    try:
        test_1_theme_dict_switching()
        test_2_all_colors_present()
        test_3_color_theme_helpers()
        test_4_theme_switch_cascade()
        test_5_pnl_colors_different_per_mode()
        test_6_make_weak_color()

        print("\n" + "="*80)
        print("ALL TESTS PASSED!")
        print("="*80)
        log.info("ALL TESTS PASSED")

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        log.error(f"TEST FAILED: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        log.error(f"ERROR: {e}", exc_info=True)
        sys.exit(1)
