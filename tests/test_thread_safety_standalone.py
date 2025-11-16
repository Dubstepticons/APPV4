#!/usr/bin/env python3
"""
tests/test_thread_safety_standalone.py

Thread safety verification tests for APPV4 (standalone version).

Tests concurrent access to:
- StateManager (VULN-001, VULN-002 fixes)
- StatsService cache (VULN-003 fix)

Can be run directly without pytest: python tests/test_thread_safety_standalone.py
"""

import sys
import os
import threading
import time
from datetime import datetime
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import components to test
from core.state_manager import StateManager
from services.stats_service import (
    _stats_cache,
    _stats_cache_lock,
    invalidate_stats_cache,
)


class TestRunner:
    """Simple test runner"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, test_func, test_name):
        """Run a single test"""
        try:
            print(f"\n{'='*70}")
            print(f"Running: {test_name}")
            print('='*70)
            test_func()
            self.passed += 1
            print(f" PASSED: {test_name}")
        except AssertionError as e:
            self.failed += 1
            error_msg = f" FAILED: {test_name}\n  {str(e)}"
            print(error_msg)
            self.errors.append(error_msg)
        except Exception as e:
            self.failed += 1
            error_msg = f" ERROR: {test_name}\n  {type(e).__name__}: {str(e)}"
            print(error_msg)
            self.errors.append(error_msg)

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*70}")
        print("TEST SUMMARY")
        print('='*70)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total:  {self.passed + self.failed}")

        if self.errors:
            print(f"\n{'='*70}")
            print("FAILURES:")
            print('='*70)
            for error in self.errors:
                print(error)

        return self.failed == 0


# ========== StateManager Thread Safety Tests ==========

def test_concurrent_balance_adjustments_no_corruption():
    """
    VULN-001 FIX VERIFICATION: Verify balance adjustments are atomic.

    Test: 100 threads each adding $10.00, should result in exactly $10,100.00
    """
    state = StateManager()
    state.sim_balance = 10000.0

    num_threads = 100
    adjustment_amount = 10.0
    expected_final_balance = 10000.0 + (num_threads * adjustment_amount)

    threads: List[threading.Thread] = []

    def adjust_balance():
        state.adjust_sim_balance_by_pnl(adjustment_amount)

    # Launch threads
    for _ in range(num_threads):
        t = threading.Thread(target=adjust_balance)
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join(timeout=5.0)

    # Verify no corruption
    actual_balance = state.sim_balance
    print(f"  Expected: ${expected_final_balance:.2f}")
    print(f"  Actual:   ${actual_balance:.2f}")

    assert actual_balance == expected_final_balance, (
        f"Balance corruption detected: expected ${expected_final_balance:.2f}, "
        f"got ${actual_balance:.2f}. Difference: ${actual_balance - expected_final_balance:.2f}"
    )


def test_concurrent_balance_mixed_operations():
    """
    VULN-001 FIX VERIFICATION: Test mixed win/loss adjustments.

    Test: 50 wins (+$20) and 50 losses (-$10) should result in $10,500
    """
    state = StateManager()
    state.sim_balance = 10000.0

    num_wins = 50
    num_losses = 50
    win_amount = 20.0
    loss_amount = -10.0
    expected_final = 10000.0 + (num_wins * win_amount) + (num_losses * loss_amount)

    threads: List[threading.Thread] = []

    # Create win threads
    for _ in range(num_wins):
        t = threading.Thread(target=lambda: state.adjust_sim_balance_by_pnl(win_amount))
        threads.append(t)

    # Create loss threads
    for _ in range(num_losses):
        t = threading.Thread(target=lambda: state.adjust_sim_balance_by_pnl(loss_amount))
        threads.append(t)

    # Shuffle and start all threads
    import random
    random.shuffle(threads)
    for t in threads:
        t.start()

    # Wait for completion
    for t in threads:
        t.join(timeout=5.0)

    # Verify
    print(f"  Expected: ${expected_final:.2f}")
    print(f"  Actual:   ${state.sim_balance:.2f}")

    assert state.sim_balance == expected_final, (
        f"Mixed operations failed: expected ${expected_final:.2f}, "
        f"got ${state.sim_balance:.2f}"
    )


def test_concurrent_dict_operations_no_corruption():
    """
    VULN-002 FIX VERIFICATION: Verify dict operations are thread-safe.

    Test: 100 threads each setting different keys, all should be present.
    """
    state = StateManager()

    num_threads = 100
    threads: List[threading.Thread] = []

    def set_key(key: str, value: int):
        state.set(key, value)

    # Launch threads to set keys
    for i in range(num_threads):
        t = threading.Thread(target=set_key, args=(f"key_{i}", i))
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=5.0)

    # Verify all keys are present
    missing_keys = []
    for i in range(num_threads):
        value = state.get(f"key_{i}")
        if value != i:
            missing_keys.append(f"key_{i}")

    print(f"  Threads:     {num_threads}")
    print(f"  Keys set:    {len(state.keys())}")
    print(f"  Missing:     {len(missing_keys)}")

    assert len(missing_keys) == 0, f"Keys missing or corrupted: {missing_keys[:10]}"


def test_concurrent_mode_changes():
    """
    VULN-002 FIX VERIFICATION: Test concurrent mode changes.

    Test: Multiple threads changing modes concurrently.
    """
    state = StateManager()

    num_threads = 50
    threads: List[threading.Thread] = []

    accounts = ["Sim1", "Sim2", "123456", "654321", "DEBUG"]

    def change_mode(account: str):
        state.set_mode(account)

    # Launch threads
    for i in range(num_threads):
        account = accounts[i % len(accounts)]
        t = threading.Thread(target=change_mode, args=(account,))
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=5.0)

    # Verify state is valid
    print(f"  Final mode:    {state.current_mode}")
    print(f"  Final account: {state.current_account}")

    assert state.current_mode in ["SIM", "LIVE", "DEBUG"]
    assert state.current_account in accounts

    # Verify mode history is not corrupted
    history = state.get_mode_history()
    print(f"  History size:  {len(history)}")

    assert isinstance(history, list)
    assert len(history) > 0
    assert len(history) <= 100  # Should be capped at 100


def test_concurrent_read_write_balance():
    """
    Test concurrent reads and writes don't cause deadlocks or corruption.
    """
    state = StateManager()
    state.sim_balance = 10000.0

    num_readers = 50
    num_writers = 50

    reader_results: List[float] = []
    results_lock = threading.Lock()

    def reader():
        for _ in range(10):
            balance = state.get_balance_for_mode("SIM")
            with results_lock:
                reader_results.append(balance)
            time.sleep(0.001)

    def writer():
        for _ in range(10):
            state.adjust_sim_balance_by_pnl(1.0)
            time.sleep(0.001)

    threads: List[threading.Thread] = []

    # Launch readers and writers
    for _ in range(num_readers):
        t = threading.Thread(target=reader)
        threads.append(t)
        t.start()

    for _ in range(num_writers):
        t = threading.Thread(target=writer)
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=10.0)

    # Verify all readers got valid results (no corruption)
    print(f"  Readers:       {num_readers}")
    print(f"  Writers:       {num_writers}")
    print(f"  Read results:  {len(reader_results)}")

    assert len(reader_results) == num_readers * 10
    for balance in reader_results:
        assert isinstance(balance, (int, float))
        assert balance >= 10000.0  # Balance should only increase

    # Verify final balance
    expected_final = 10000.0 + (num_writers * 10 * 1.0)
    print(f"  Final balance: ${state.sim_balance:.2f} (expected ${expected_final:.2f})")
    assert state.sim_balance == expected_final


# ========== StatsService Cache Thread Safety Tests ==========

def test_concurrent_cache_access_no_corruption():
    """
    VULN-003 FIX VERIFICATION: Verify cache operations are thread-safe.

    Test: Multiple threads reading/writing cache concurrently.
    """
    # Clear cache first
    invalidate_stats_cache()

    num_threads = 50
    threads: List[threading.Thread] = []

    def cache_operation(thread_id: int):
        # Mix of read and write operations
        cache_key = (f"1D", f"MODE_{thread_id % 5}")

        # Write to cache
        with _stats_cache_lock:
            _stats_cache[cache_key] = (time.time(), {"test": thread_id})

        # Read from cache
        with _stats_cache_lock:
            if cache_key in _stats_cache:
                cached_time, cached_data = _stats_cache[cache_key]
                assert isinstance(cached_data, dict)

    # Launch threads
    for i in range(num_threads):
        t = threading.Thread(target=cache_operation, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=5.0)

    # Verify cache is not corrupted
    with _stats_cache_lock:
        cache_size = len(_stats_cache)
        print(f"  Threads:    {num_threads}")
        print(f"  Cache size: {cache_size}")

        assert isinstance(_stats_cache, dict)
        # Should have entries for MODE_0 through MODE_4
        assert cache_size <= 5


def test_concurrent_cache_invalidation():
    """
    VULN-003 FIX VERIFICATION: Test concurrent cache invalidation.

    Test: Multiple threads invalidating cache while others read/write.
    """
    # Populate cache
    with _stats_cache_lock:
        for i in range(10):
            _stats_cache[(f"1D", f"MODE_{i}")] = (time.time(), {"test": i})

    num_invalidators = 10
    num_readers = 20
    threads: List[threading.Thread] = []

    def invalidator():
        for _ in range(5):
            invalidate_stats_cache()
            time.sleep(0.001)

    def reader():
        for _ in range(10):
            with _stats_cache_lock:
                cache_keys = list(_stats_cache.keys())
            time.sleep(0.001)

    # Launch invalidators
    for _ in range(num_invalidators):
        t = threading.Thread(target=invalidator)
        threads.append(t)
        t.start()

    # Launch readers
    for _ in range(num_readers):
        t = threading.Thread(target=reader)
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=10.0)

    # Verify cache is in valid state (not corrupted)
    with _stats_cache_lock:
        print(f"  Cache state: valid (size={len(_stats_cache)})")
        assert isinstance(_stats_cache, dict)


def test_cache_expiry_race_condition():
    """
    VULN-003 FIX VERIFICATION: Test cache expiry handling under concurrency.

    Test: Multiple threads checking and deleting expired entries.
    """
    # Clear cache
    invalidate_stats_cache()

    # Add expired entry
    expired_time = time.time() - 10.0  # 10 seconds ago (expired)
    current_time = time.time()

    with _stats_cache_lock:
        _stats_cache[("1D", "SIM")] = (expired_time, {"old": "data"})
        _stats_cache[("1W", "SIM")] = (current_time, {"new": "data"})

    num_threads = 20
    threads: List[threading.Thread] = []
    deletion_count = [0]
    count_lock = threading.Lock()

    def check_and_delete_expired():
        cache_key = ("1D", "SIM")
        ttl = 5.0

        with _stats_cache_lock:
            if cache_key in _stats_cache:
                cached_time, _ = _stats_cache[cache_key]
                if time.time() - cached_time >= ttl:
                    del _stats_cache[cache_key]
                    with count_lock:
                        deletion_count[0] += 1

    # Launch threads
    for _ in range(num_threads):
        t = threading.Thread(target=check_and_delete_expired)
        threads.append(t)
        t.start()

    # Wait for all
    for t in threads:
        t.join(timeout=5.0)

    # Verify only one thread deleted the entry (no double-delete)
    print(f"  Deletion count: {deletion_count[0]} (expected 1)")

    assert deletion_count[0] == 1, (
        f"Expected exactly 1 deletion, got {deletion_count[0]}. "
        "This indicates a race condition."
    )

    # Verify expired entry is gone but current entry remains
    with _stats_cache_lock:
        assert ("1D", "SIM") not in _stats_cache
        assert ("1W", "SIM") in _stats_cache


# ========== Performance Tests ==========

def test_balance_adjustment_performance():
    """
    Verify that lock contention doesn't severely impact performance.

    Target: 1000 balance adjustments should complete in < 1 second.
    """
    state = StateManager()
    state.sim_balance = 10000.0

    num_operations = 1000
    start_time = time.time()

    for _ in range(num_operations):
        state.adjust_sim_balance_by_pnl(1.0)

    elapsed = time.time() - start_time

    print(f"  Operations: {num_operations}")
    print(f"  Time:       {elapsed:.3f}s")
    print(f"  Rate:       {num_operations/elapsed:.0f} ops/sec")

    assert elapsed < 1.0, (
        f"Lock contention too high: {num_operations} operations took {elapsed:.3f}s "
        f"(expected < 1.0s)"
    )


def test_cache_lookup_performance():
    """
    Verify cache lock doesn't cause excessive overhead.

    Target: 1000 cache lookups should complete in < 0.5 seconds.
    """
    # Populate cache
    with _stats_cache_lock:
        _stats_cache[("1D", "SIM")] = (time.time(), {"test": "data"})

    num_lookups = 1000
    start_time = time.time()

    for _ in range(num_lookups):
        with _stats_cache_lock:
            if ("1D", "SIM") in _stats_cache:
                _ = _stats_cache[("1D", "SIM")]

    elapsed = time.time() - start_time

    print(f"  Lookups:    {num_lookups}")
    print(f"  Time:       {elapsed:.3f}s")
    print(f"  Rate:       {num_lookups/elapsed:.0f} lookups/sec")

    assert elapsed < 0.5, (
        f"Cache lock overhead too high: {num_lookups} lookups took {elapsed:.3f}s "
        f"(expected < 0.5s)"
    )


# ========== Main Test Runner ==========

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("APPV4 Thread Safety Test Suite")
    print("Testing VULN-001, VULN-002, VULN-003 fixes")
    print("="*70)

    runner = TestRunner()

    # StateManager tests
    runner.run_test(
        test_concurrent_balance_adjustments_no_corruption,
        "StateManager: Concurrent balance adjustments (VULN-001)"
    )
    runner.run_test(
        test_concurrent_balance_mixed_operations,
        "StateManager: Mixed win/loss operations (VULN-001)"
    )
    runner.run_test(
        test_concurrent_dict_operations_no_corruption,
        "StateManager: Concurrent dict operations (VULN-002)"
    )
    runner.run_test(
        test_concurrent_mode_changes,
        "StateManager: Concurrent mode changes (VULN-002)"
    )
    runner.run_test(
        test_concurrent_read_write_balance,
        "StateManager: Concurrent reads/writes"
    )

    # StatsService tests
    runner.run_test(
        test_concurrent_cache_access_no_corruption,
        "StatsService: Concurrent cache access (VULN-003)"
    )
    runner.run_test(
        test_concurrent_cache_invalidation,
        "StatsService: Concurrent cache invalidation (VULN-003)"
    )
    runner.run_test(
        test_cache_expiry_race_condition,
        "StatsService: Cache expiry race condition (VULN-003)"
    )

    # Performance tests
    runner.run_test(
        test_balance_adjustment_performance,
        "Performance: Balance adjustment throughput"
    )
    runner.run_test(
        test_cache_lookup_performance,
        "Performance: Cache lookup throughput"
    )

    # Print summary
    success = runner.print_summary()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
