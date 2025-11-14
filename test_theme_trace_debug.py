"""
test_theme_trace_debug.py

Trace exactly what happens during app startup to find theme switching issues.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Patch switch_theme to trace all calls
original_switch_theme = None

def patched_switch_theme(theme_name: str) -> None:
    """Patched switch_theme that logs all calls with stack trace."""
    import traceback
    print(f"\n[TRACE] switch_theme('{theme_name}') called from:")
    # Print full stack with line numbers and function names
    stack = traceback.extract_stack(limit=7)
    for frame in stack[-7:-1]:  # Skip last frame (this function)
        print(f"  {frame.filename}:{frame.lineno} in {frame.name}: {frame.line}")
    original_switch_theme(theme_name)

from config import theme as theme_module
original_switch_theme = theme_module.switch_theme
theme_module.switch_theme = patched_switch_theme

# Also patch the imported reference in other modules
from config.theme import THEME, switch_theme, LIVE_THEME, SIM_THEME, DEBUG_THEME
from core.app_manager import MainWindow
from core.signal_bus import get_signal_bus, reset_signal_bus
from PyQt6 import QtWidgets, QtCore
from utils.logger import get_logger

log = get_logger(__name__)

def test_startup_trace():
    """Trace theme switching during startup."""
    print("\n" + "="*80)
    print("TRACING THEME CHANGES DURING STARTUP")
    print("="*80)

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    print("\n[STARTUP] Creating MainWindow...")
    reset_signal_bus()

    try:
        window = MainWindow()
        print(f"\n[STARTUP] MainWindow created")
        app.processEvents()

        print(f"\n[FINAL STATE]")
        print(f"  window.current_theme_mode: {window.current_theme_mode}")
        print(f"  THEME['bg_primary']: {THEME.get('bg_primary')}")

        window.close()
        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        log.error(f"Trace test error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_startup_trace()
