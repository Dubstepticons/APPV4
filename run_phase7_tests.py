#!/usr/bin/env python3
"""
run_phase7_tests.py

Test runner for Phase 7 integration tests.

Usage:
    python run_phase7_tests.py              # Run all tests
    python run_phase7_tests.py --verbose    # Verbose output
    python run_phase7_tests.py --suite=1    # Run specific suite
"""

import sys
import argparse
import subprocess


SUITES = {
    "1": "TestCrashRecovery",
    "2": "TestModeSwitching",
    "3": "TestThreadSafety",
    "4": "TestDatabaseIntegrity",
    "5": "TestEndToEnd",
}


def run_tests(suite=None, verbose=False):
    """Run integration tests."""
    cmd = ["pytest", "tests/integration/test_phase7_position_lifecycle.py"]

    if suite:
        suite_name = SUITES.get(suite)
        if not suite_name:
            print(f"Error: Invalid suite '{suite}'. Valid suites: {list(SUITES.keys())}")
            return 1
        cmd.append(f"-k={suite_name}")

    if verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")

    cmd.extend(["--tb=short", "--color=yes"])

    print(f"\n{'='*80}")
    print("PHASE 7 INTEGRATION TESTS")
    print(f"{'='*80}\n")

    if suite:
        print(f"Running Suite {suite}: {SUITES[suite]}")
    else:
        print("Running all test suites (5 suites, 12 tests)")

    print(f"\nCommand: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)
    return result.returncode


def print_test_summary():
    """Print test suite summary."""
    print("\n" + "="*80)
    print("TEST SUITE SUMMARY")
    print("="*80)
    print("""
Suite 1: Crash Recovery (3 tests)
  ✓ Test 1.1: Basic crash recovery (SIM)
  ✓ Test 1.2: Crash recovery (LIVE with warning)
  ✓ Test 1.3: Stale position detection (>24h)

Suite 2: Mode Switching (3 tests)
  ✓ Test 2.1: SIM → LIVE → SIM preserves positions
  ✓ Test 2.2: Concurrent SIM + LIVE positions
  ✓ Test 2.3: Mode isolation (no leakage)

Suite 3: Thread Safety (2 tests)
  ✓ Test 3.1: Concurrent position updates (10 threads)
  ✓ Test 3.2: Concurrent close operations (race condition)

Suite 4: Database Integrity (2 tests)
  ✓ Test 4.1: Atomic position close transaction
  ✓ Test 4.2: Non-existent position handling

Suite 5: End-to-End (2 tests)
  ✓ Test 5.1: Full trading session (MAE/MFE)
  ✓ Test 5.2: Multiple trades in session

Total: 12 tests across 5 suites
""")
    print("="*80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Phase 7 integration tests")
    parser.add_argument("--suite", choices=list(SUITES.keys()), help="Run specific test suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--summary", action="store_true", help="Show test summary")

    args = parser.parse_args()

    if args.summary:
        print_test_summary()
        sys.exit(0)

    exit_code = run_tests(suite=args.suite, verbose=args.verbose)
    sys.exit(exit_code)
