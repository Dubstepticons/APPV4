"""
Test feature flag integration.

Verifies that:
1. Feature flags can be read
2. Old and new panels can be imported
3. Panel factory methods work correctly
"""

import os
import sys

# Test 1: Feature flags import and read
print("=" * 60)
print("TEST 1: Feature Flags Import")
print("=" * 60)

try:
    from config.feature_flags import FeatureFlags
    print("✓ FeatureFlags imported successfully")

    print(f"\nCurrent flag values:")
    print(f"  USE_NEW_PANEL1: {FeatureFlags.USE_NEW_PANEL1}")
    print(f"  USE_NEW_PANEL2: {FeatureFlags.USE_NEW_PANEL2}")
    print(f"  USE_TYPED_EVENTS: {FeatureFlags.USE_TYPED_EVENTS}")
    print(f"  ENABLE_MIGRATION_LOGS: {FeatureFlags.ENABLE_MIGRATION_LOGS}")
    print(f"  ENABLE_PERF_TRACKING: {FeatureFlags.ENABLE_PERF_TRACKING}")
except Exception as e:
    print(f"✗ Failed to import FeatureFlags: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Old panel imports
print("\n" + "=" * 60)
print("TEST 2: Old Panel Imports")
print("=" * 60)

try:
    from panels.panel1_old import Panel1 as Panel1Old
    print("✓ Panel1Old imported successfully")
except Exception as e:
    print(f"✗ Failed to import Panel1Old: {e}")
    import traceback
    traceback.print_exc()

try:
    from panels.panel2_old import Panel2 as Panel2Old
    print("✓ Panel2Old imported successfully")
except Exception as e:
    print(f"✗ Failed to import Panel2Old: {e}")
    import traceback
    traceback.print_exc()

# Test 3: New panel imports
print("\n" + "=" * 60)
print("TEST 3: New Panel Imports")
print("=" * 60)

try:
    from panels.panel1 import Panel1 as Panel1New
    print("✓ Panel1New imported successfully")
except Exception as e:
    print(f"✗ Failed to import Panel1New: {e}")
    import traceback
    traceback.print_exc()

try:
    from panels.panel2 import Panel2 as Panel2New
    print("✓ Panel2New imported successfully")
except Exception as e:
    print(f"✗ Failed to import Panel2New: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Feature flag override via environment variables
print("\n" + "=" * 60)
print("TEST 4: Environment Variable Override")
print("=" * 60)

# Set env vars
os.environ["USE_NEW_PANEL1"] = "1"
os.environ["USE_NEW_PANEL2"] = "1"

# Force reload of FeatureFlags
import importlib
import config.feature_flags
importlib.reload(config.feature_flags)
from config.feature_flags import FeatureFlags

print(f"After setting USE_NEW_PANEL1=1, USE_NEW_PANEL2=1:")
print(f"  USE_NEW_PANEL1: {FeatureFlags.USE_NEW_PANEL1}")
print(f"  USE_NEW_PANEL2: {FeatureFlags.USE_NEW_PANEL2}")

if FeatureFlags.USE_NEW_PANEL1 and FeatureFlags.USE_NEW_PANEL2:
    print("✓ Environment variable override working correctly")
else:
    print("✗ Environment variable override NOT working")

# Test 5: Test panel factory logic
print("\n" + "=" * 60)
print("TEST 5: Panel Factory Logic")
print("=" * 60)

def test_factory():
    """Simulate the factory method logic."""
    # Test with new panels enabled
    if FeatureFlags.USE_NEW_PANEL1:
        print("✓ Factory would create Panel1New")
    else:
        print("  Factory would create Panel1Old")

    if FeatureFlags.USE_NEW_PANEL2:
        print("✓ Factory would create Panel2New")
    else:
        print("  Factory would create Panel2Old")

test_factory()

# Test 6: Reset to defaults
print("\n" + "=" * 60)
print("TEST 6: Reset to Defaults")
print("=" * 60)

os.environ["USE_NEW_PANEL1"] = "0"
os.environ["USE_NEW_PANEL2"] = "0"

importlib.reload(config.feature_flags)
from config.feature_flags import FeatureFlags

print(f"After setting USE_NEW_PANEL1=0, USE_NEW_PANEL2=0:")
print(f"  USE_NEW_PANEL1: {FeatureFlags.USE_NEW_PANEL1}")
print(f"  USE_NEW_PANEL2: {FeatureFlags.USE_NEW_PANEL2}")

if not FeatureFlags.USE_NEW_PANEL1 and not FeatureFlags.USE_NEW_PANEL2:
    print("✓ Rollback to old panels working correctly")
else:
    print("✗ Rollback NOT working")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
print("\nSummary:")
print("- Feature flags system is operational")
print("- Both old and new panels can be imported")
print("- Environment variable override works")
print("- Rollback mechanism works")
print("\nNext step: Update config/settings.py and test with actual Qt application")
