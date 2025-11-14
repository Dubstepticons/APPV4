# Theme Switching Debug Summary

## Problem
When switching modes using Ctrl+Shift+M hotkey, the theme does not visually update in the UI, even though the theme dictionary is being updated correctly.

## Root Cause Found

The issue is in `utils/mode_selector.py` line 89. When the hotkey cycles modes, it calls:
```python
apply_trading_mode_theme(new_mode)
```

This function only updates the global `THEME` dictionary but **DOES NOT emit signals** to notify panels to refresh.

## How It Should Work

When theme changes, this chain should occur:

1. `switch_theme(mode)` - Updates THEME dictionary ✓ (WORKING)
2. `themeChanged` signal emitted ✓ (FIXED)
3. `on_theme_changed()` handler called ✓ (FIXED)
4. `themeChangeRequested` signal emitted on SignalBus ✓ (FIXED)
5. Panel `refresh_theme()` methods called ✓ (SHOULD NOW WORK)

## The Fix

Changed `utils/mode_selector.py` line 89-103 to use `window._set_theme_mode()` instead of `apply_trading_mode_theme()`:

### Before (BROKEN):
```python
from config.theme import apply_trading_mode_theme
apply_trading_mode_theme(new_mode)  # Only updates dict, no signals!
```

### After (FIXED):
```python
# CRITICAL: Use MainWindow's _set_theme_mode to emit signals
if hasattr(window, '_set_theme_mode'):
    window._set_theme_mode(new_mode)  # Updates dict AND emits signals!
else:
    # Fallback (shouldn't happen)
    from config.theme import apply_trading_mode_theme
    apply_trading_mode_theme(new_mode)
```

## What Was Added

### 1. Comprehensive Debugging
Added debug print statements to:
- `config/theme.py` - Theme dictionary updates
- `utils/mode_selector.py` - Mode switching
- `core/app_manager.py` - Signal emission
- `utils/theme_mixin.py` - Panel refresh

### 2. Test Scripts
Created test scripts to verify theme switching:
- `run_theme_test.py` - Automated test of theme dictionary updates ✓ ALL TESTS PASSED
- `test_theme_mode_switching.py` - UI testing instructions

## Test Results

### Phase 1: Theme Dictionary Test ✓ PASSED
```
[OK] DEBUG  - PASS  (actual: #1E1E1E, expected: #1E1E1E)
[OK] SIM    - PASS  (actual: #FFFFFF, expected: #FFFFFF)
[OK] LIVE   - PASS  (actual: #000000, expected: #000000)

Total: 3 passed, 0 failed out of 3 tests
```

The theme dictionary updates correctly for all modes:
- DEBUG: #1E1E1E (Dark Gray)
- SIM: #FFFFFF (White)
- LIVE: #000000 (Black)

### Phase 2: UI Signal Test (TO BE VERIFIED)

Run the application and test:
1. Launch app: `python main.py`
2. Press Ctrl+Shift+M to cycle modes
3. Watch console for debug output
4. **Verify panels visually change colors**

Expected debug output when pressing Ctrl+Shift+M:
```
[MODE DEBUG] About to apply theme for mode: SIM
[MODE DEBUG] Found _set_theme_mode method, calling it
[THEME DEBUG] _set_theme_mode() called with mode='SIM'
[THEME SWITCH] Starting switch_theme('sim')
[THEME SWITCH] [OK] Successfully switched to theme: 'SIM'
[THEME DEBUG] Emitting themeChanged signal
[THEME DEBUG] ✓ themeChanged signal emitted
[THEME DEBUG] on_theme_changed() called
[THEME DEBUG] Emitting themeChangeRequested signal
[THEME DEBUG] ✓ themeChangeRequested signal emitted successfully
[THEME MIXIN] refresh_theme() called on Panel1
[THEME MIXIN] refresh_theme() called on Panel2
[THEME MIXIN] refresh_theme() called on Panel3
```

## Visual Changes Expected

### DEBUG Mode (Dark Gray)
- Background: #1E1E1E (Dark charcoal)
- Cards: #3A3A3A (Medium gray)
- Text: #C0C0C0 (Silver)

### SIM Mode (White)
- Background: #FFFFFF (Pure white)
- Cards: #E3F2FD (Light blue)
- Text: #000000 (Black)

### LIVE Mode (Black)
- Background: #000000 (Pure black)
- Cards: #0F2540 (Dark blue)
- Text: #FFD700 (Gold)

## Files Modified

1. `utils/mode_selector.py` - Fixed to emit signals
2. `config/theme.py` - Added debug logging
3. `core/app_manager.py` - Added debug logging
4. `utils/theme_mixin.py` - Added debug logging
5. `run_theme_test.py` - Created test script
6. `test_theme_mode_switching.py` - Created UI test instructions

## Next Steps

1. Run the application: `python main.py`
2. Press Ctrl+Shift+M multiple times
3. Verify the UI colors change (background, panels, text)
4. Check console output for complete signal chain
5. If panels don't refresh, check signal connections in Panel1/Panel2/Panel3

## Debugging Checklist

If theme still doesn't update visually:

- [ ] Check that `themeChanged` signal is emitted (should see in console)
- [ ] Check that `on_theme_changed()` is called (should see in console)
- [ ] Check that `themeChangeRequested` is emitted (should see in console)
- [ ] Check that Panel `refresh_theme()` is called (should see in console)
- [ ] Verify panels are connected to SignalBus.themeChangeRequested signal
- [ ] Check panel's `_build_theme_stylesheet()` returns correct CSS
- [ ] Verify `setStyleSheet()` is being called on panels

## Summary

**Root Cause**: Mode hotkey only updated THEME dict without emitting signals.

**Fix**: Changed mode selector to call `window._set_theme_mode()` which properly emits all signals.

**Status**: Theme dictionary updates ✓ VERIFIED | UI refresh pending user verification
