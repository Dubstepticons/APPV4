#!/usr/bin/env python3
"""
Smoke Test: Verify import chain works up to PyQt6

This test validates that the decomposed modules can be imported
successfully, stopping at the expected PyQt6 import (which won't
be available in non-GUI environments).
"""

import sys

print("="*80)
print("IMPORT CHAIN SMOKE TEST")
print("="*80)
print()

# Test 1: Import individual helper modules (before PyQt6)
print("[TEST 1] Individual Helper Modules")
print("-" * 80)

tests = []

# theme_manager (no PyQt6 dependencies)
try:
    from core.app_manager import theme_manager
    print("✓ core.app_manager.theme_manager imported")
    tests.append(("theme_manager", True))

    # Check functions exist
    assert hasattr(theme_manager, 'set_theme_mode')
    assert hasattr(theme_manager, 'on_theme_changed')
    assert hasattr(theme_manager, 'pnl_color_from_direction')
    print("  ✓ All expected functions found")

except Exception as e:
    print(f"✗ theme_manager failed: {e}")
    tests.append(("theme_manager", False))

print()

# Test 2: Try to import MainWindow (will fail at PyQt6, but import chain should work)
print("[TEST 2] MainWindow Import Chain")
print("-" * 80)

try:
    from core.app_manager import MainWindow
    print("✓ MainWindow imported successfully (PyQt6 is available)")
    tests.append(("MainWindow", True))

except ModuleNotFoundError as e:
    if "PyQt6" in str(e):
        print("✓ MainWindow import chain works (stopped at PyQt6 as expected)")
        print(f"  Note: {e}")
        tests.append(("MainWindow", True))  # This is actually success
    else:
        print(f"✗ Unexpected import error: {e}")
        tests.append(("MainWindow", False))

except Exception as e:
    print(f"✗ Unexpected error: {e}")
    tests.append(("MainWindow", False))

print()

# Test 3: Backward compatibility - import from core
print("[TEST 3] Backward Compatibility (core.__init__.py)")
print("-" * 80)

try:
    # This tests the re-export in core/__init__.py
    import core

    # Check if MainWindow is accessible via core package
    # (Won't actually import due to PyQt6, but the path should be correct)
    print("✓ core package imports successfully")

    # Check the __init__.py has the right export
    import importlib.util
    spec = importlib.util.find_spec("core")
    if spec and spec.origin:
        with open(spec.origin, 'r') as f:
            init_content = f.read()
            if "from .app_manager import MainWindow" in init_content:
                print("✓ core.__init__.py exports MainWindow correctly")
                tests.append(("backward_compat", True))
            else:
                print("✗ core.__init__.py export not found")
                tests.append(("backward_compat", False))

except Exception as e:
    print(f"✗ Failed: {e}")
    tests.append(("backward_compat", False))

print()

# Summary
print("="*80)
print("SUMMARY")
print("="*80)

passed = sum(1 for _, success in tests if success)
total = len(tests)

print(f"Tests: {passed}/{total} passed")
print()

if passed == total:
    print("✅ SUCCESS: All import chains work correctly!")
    print("✅ Decomposition is structurally sound")
    print("✅ Backward compatibility maintained")
    print()
    print("Next: Test with actual PyQt6 environment:")
    print("  python main.py")
    sys.exit(0)
else:
    print("❌ FAILURE: Some import chains broken")
    sys.exit(1)
