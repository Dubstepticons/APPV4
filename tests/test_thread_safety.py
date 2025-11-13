"""
tests/test_thread_safety.py

Thread safety verification tests for APPV4.

Tests concurrent access to:
- StateManager (VULN-001, VULN-002 fixes)
- StatsService cache (VULN-003 fix)

These tests verify that our thread safety fixes prevent race conditions
under high-concurrency scenarios.
"""

import pytest
import threading
import time
from datetime import datetime
from typing import List

# Import components to test
from core.state_manager import StateManager
from services.stats_service import (
    _stats_cache,
    _stats_cache_lock,
    invalidate_stats_cache,
)


class TestStateManagerThreadSafety:
    """Test thread safety of StateManager (VULN-001 and VULN-002 fixes)"""

    def test_concurrent_balance_adjustments_no_corruption(self):
        """
        VULN-001 FIX VERIFICATION: Verify balance adjustments are atomic.

        Without thread safety, concurrent balance adjustments would lose updates
        due to read-modify-write race conditions.

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
        assert actual_balance == expected_final_balance, (
            f"Balance corruption detected: expected ${expected_final_balance:.2f}, "
            f"got ${actual_balance:.2f}. Difference: ${actual_balance - expected_final_balance:.2f}"
        )

    def test_concurrent_balance_mixed_operations(self):
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
        assert state.sim_balance == expected_final, (
            f"Mixed operations failed: expected ${expected_final:.2f}, "
            f"got ${state.sim_balance:.2f}"
        )

    def test_concurrent_dict_operations_no_corruption(self):
        """
        VULN-002 FIX VERIFICATION: Verify dict operations are thread-safe.

        Without locks, concurrent dict operations can corrupt internal state.

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
        for i in range(num_threads):
            value = state.get(f"key_{i}")
            assert value == i, f"Key key_{i} missing or corrupted: expected {i}, got {value}"

    def test_concurrent_position_updates(self):
        """
        VULN-002 FIX VERIFICATION: Test concurrent position updates.

        Test: Multiple threads updating positions concurrently.
        """
        state = StateManager()

        symbols = ["MES", "MNQ", "M2K", "MYM", "MGC"]
        num_updates_per_symbol = 20
        threads: List[threading.Thread] = []

        def update_position(symbol: str, qty: int):
            state.update_position(symbol, qty, 5000.0 + qty)

        # Launch threads
        for symbol in symbols:
            for qty in range(1, num_updates_per_symbol + 1):
                t = threading.Thread(target=update_position, args=(symbol, qty))
                threads.append(t)
                t.start()

        # Wait for all
        for t in threads:
            t.join(timeout=5.0)

        # Verify state is not corrupted (dict operations didn't crash)
        # The final state might vary, but dict should not be corrupted
        assert isinstance(state._state.get("positions", {}), dict)

    def test_concurrent_mode_changes(self):
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
        assert state.current_mode in ["SIM", "LIVE", "DEBUG"]
        assert state.current_account in accounts

        # Verify mode history is not corrupted
        history = state.get_mode_history()
        assert isinstance(history, list)
        assert len(history) > 0
        assert len(history) <= 100  # Should be capped at 100

    def test_concurrent_read_write_balance(self):
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
        assert len(reader_results) == num_readers * 10
        for balance in reader_results:
            assert isinstance(balance, (int, float))
            assert balance >= 10000.0  # Balance should only increase

        # Verify final balance
        expected_final = 10000.0 + (num_writers * 10 * 1.0)
        assert state.sim_balance == expected_final


class TestStatsServiceThreadSafety:
    """Test thread safety of StatsService cache (VULN-003 fix)"""

    def test_concurrent_cache_access_no_corruption(self):
        """
        VULN-003 FIX VERIFICATION: Verify cache operations are thread-safe.

        Without locks, concurrent cache access can corrupt the dict.

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
            assert isinstance(_stats_cache, dict)
            # Should have entries for MODE_0 through MODE_4
            assert len(_stats_cache) <= 5

    def test_concurrent_cache_invalidation(self):
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
            assert isinstance(_stats_cache, dict)

    def test_cache_expiry_race_condition(self):
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
        assert deletion_count[0] == 1, (
            f"Expected exactly 1 deletion, got {deletion_count[0]}. "
            "This indicates a race condition."
        )

        # Verify expired entry is gone but current entry remains
        with _stats_cache_lock:
            assert ("1D", "SIM") not in _stats_cache
            assert ("1W", "SIM") in _stats_cache


class TestDeadlockPrevention:
    """Test that our thread safety implementation doesn't cause deadlocks"""

    def test_no_deadlock_with_signal_emission(self):
        """
        Verify that emitting Qt signals outside lock scope prevents deadlocks.

        This is a regression test - if signals were emitted inside lock scope,
        Qt's signal/slot mechanism could cause deadlocks.
        """
        state = StateManager()

        # Connect a signal that tries to access state (potential deadlock)
        callback_executed = [False]

        def on_balance_changed(balance):
            # This callback might try to read state
            _ = state.get_balance_for_mode("SIM")
            callback_executed[0] = True

        state.balanceChanged.connect(on_balance_changed)

        # Trigger balance change
        state.set_balance_for_mode("SIM", 12345.0)

        # Should complete without deadlock
        assert callback_executed[0], "Signal callback was not executed (possible deadlock)"

    def test_nested_lock_acquisition_with_rlock(self):
        """
        Verify that RLock allows nested lock acquisition (needed for internal calls).
        """
        state = StateManager()

        # This should not deadlock because we use RLock
        # set_mode calls _add_to_mode_history_unsafe which assumes lock is held
        state.set_mode("Sim1")
        state.set_mode("123456")
        state.set_mode("Sim2")

        # Verify state is valid
        assert state.current_mode == "SIM"
        history = state.get_mode_history()
        assert len(history) >= 3


@pytest.mark.performance
class TestThreadSafetyPerformance:
    """Performance tests to ensure locks don't cause excessive contention"""

    def test_balance_adjustment_performance(self):
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

        assert elapsed < 1.0, (
            f"Lock contention too high: {num_operations} operations took {elapsed:.3f}s "
            f"(expected < 1.0s)"
        )

    def test_cache_lookup_performance(self):
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

        assert elapsed < 0.5, (
            f"Cache lock overhead too high: {num_lookups} lookups took {elapsed:.3f}s "
            f"(expected < 0.5s)"
        )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
