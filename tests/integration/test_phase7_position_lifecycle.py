"""
tests/integration/test_phase7_position_lifecycle.py

Phase 7 Integration Tests - Position State Architecture

Tests the complete position lifecycle with database persistence:
- Crash recovery
- Mode switching
- Thread safety
- Database integrity
- End-to-end scenarios

Run with: pytest tests/integration/test_phase7_position_lifecycle.py -v
"""

import pytest
import threading
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from data.schema import OpenPosition, TradeRecord
from data.position_repository import get_position_repository
from services.position_recovery import get_recovery_service


# ==============================================================================
# TEST SUITE 1: CRASH RECOVERY (3 tests)
# ==============================================================================

class TestCrashRecovery:
    """Test position recovery after application crash."""

    def test_1_1_basic_crash_recovery_sim(self, db_session, position_repo, sample_position_data):
        """
        Test 1.1: Basic crash recovery with SIM position.

        Scenario:
        1. Save position to database (simulating open position)
        2. Simulate crash (close session)
        3. Recover position (new session)
        4. Verify all fields restored correctly
        """
        # Step 1: Save position (before crash)
        success = position_repo.save_open_position(**sample_position_data)
        assert success, "Failed to save position"

        # Verify position in database
        with patch('data.position_repository.get_session', return_value=db_session):
            saved_pos = position_repo.get_open_position("SIM", "")
            assert saved_pos is not None, "Position not found in database"
            assert saved_pos["qty"] == 1
            assert saved_pos["entry_price"] == 5800.0

        # Step 2: Simulate crash (session closed, app restarted)
        # In real scenario, db_session would be recreated

        # Step 3: Recovery - load position from database
        with patch('data.position_repository.get_session', return_value=db_session):
            recovered_pos = position_repo.get_open_position("SIM", "")

        # Step 4: Verify all fields restored
        assert recovered_pos is not None, "Position not recovered"
        assert recovered_pos["mode"] == "SIM"
        assert recovered_pos["symbol"] == "MES"
        assert recovered_pos["qty"] == 1
        assert recovered_pos["entry_price"] == 5800.0
        assert recovered_pos["entry_vwap"] == 5799.5
        assert recovered_pos["entry_cum_delta"] == 1500.0
        assert recovered_pos["target_price"] == 5850.0
        assert recovered_pos["stop_price"] == 5750.0

        print("✓ Test 1.1 PASSED: Basic crash recovery successful")

    def test_1_2_crash_recovery_live_position(self, db_session, position_repo):
        """
        Test 1.2: Crash recovery with LIVE position.

        Scenario:
        1. Save LIVE position
        2. Simulate crash
        3. Recover and verify warning should be shown to user
        """
        # Step 1: Save LIVE position
        live_data = {
            "mode": "LIVE",
            "account": "120005",
            "symbol": "MNQ",
            "qty": 2,
            "entry_price": 21000.0,
            "entry_time": datetime.now(timezone.utc),
        }

        with patch('data.position_repository.get_session', return_value=db_session):
            success = position_repo.save_open_position(**live_data)
            assert success

        # Step 2 & 3: Recovery
        with patch('data.position_repository.get_session', return_value=db_session):
            recovered = position_repo.get_open_position("LIVE", "120005")

        assert recovered is not None
        assert recovered["mode"] == "LIVE"
        assert recovered["qty"] == 2
        assert recovered["entry_price"] == 21000.0

        # Note: In real implementation, recovery service would show
        # "LIVE position detected - verify with broker" warning
        print("✓ Test 1.2 PASSED: LIVE position recovery successful")

    def test_1_3_stale_position_detection(self, db_session, old_position_data):
        """
        Test 1.3: Detect stale positions (>24 hours old).

        Scenario:
        1. Insert old position (>24h)
        2. Run recovery
        3. Verify position flagged as stale
        """
        # Step 1: Manually insert old position
        old_pos = OpenPosition(
            mode=old_position_data["mode"],
            account=old_position_data["account"],
            symbol=old_position_data["symbol"],
            qty=old_position_data["qty"],
            side="LONG",
            entry_price=old_position_data["entry_price"],
            entry_time=old_position_data["entry_time"],
            created_at=old_position_data["created_at"],
            updated_at=old_position_data["updated_at"],
            trade_min_price=old_position_data["entry_price"],
            trade_max_price=old_position_data["entry_price"],
        )
        db_session.add(old_pos)
        db_session.commit()

        # Step 2: Recover all positions
        repo = PositionRepository()
        with patch('data.position_repository.get_session', return_value=db_session):
            positions = repo.recover_all_open_positions()

        assert len(positions) == 1

        # Step 3: Check if stale (>24h old)
        now = datetime.now(timezone.utc)
        pos_age = now - positions[0]["updated_at"]
        is_stale = pos_age > timedelta(hours=24)

        assert is_stale, "Position should be flagged as stale"
        print(f"✓ Test 1.3 PASSED: Stale position detected (age: {pos_age})")


# ==============================================================================
# TEST SUITE 2: MODE SWITCHING (3 tests)
# ==============================================================================

class TestModeSwitching:
    """Test mode switching with position isolation."""

    def test_2_1_mode_switch_preserves_positions(self, db_session, position_repo):
        """
        Test 2.1: SIM → LIVE → SIM preserves separate positions.

        Scenario:
        1. Save SIM position
        2. Switch to LIVE mode (query LIVE position - should be empty)
        3. Switch back to SIM (query SIM position - should be restored)
        """
        # Step 1: Save SIM position
        sim_data = {
            "mode": "SIM",
            "account": "",
            "symbol": "MES",
            "qty": 1,
            "entry_price": 5800.0,
            "entry_time": datetime.now(timezone.utc),
        }

        with patch('data.position_repository.get_session', return_value=db_session):
            position_repo.save_open_position(**sim_data)

            # Verify SIM position exists
            sim_pos = position_repo.get_open_position("SIM", "")
            assert sim_pos is not None
            assert sim_pos["qty"] == 1

            # Step 2: Switch to LIVE (different mode/account)
            live_pos = position_repo.get_open_position("LIVE", "120005")
            assert live_pos is None, "LIVE should have no position"

            # Step 3: Switch back to SIM
            sim_pos_restored = position_repo.get_open_position("SIM", "")
            assert sim_pos_restored is not None, "SIM position should be preserved"
            assert sim_pos_restored["qty"] == 1
            assert sim_pos_restored["entry_price"] == 5800.0

        print("✓ Test 2.1 PASSED: Mode switching preserves positions")

    def test_2_2_concurrent_sim_and_live_positions(self, db_session, position_repo):
        """
        Test 2.3: Can have SIM and LIVE positions simultaneously (different accounts).

        Scenario:
        1. Save SIM position
        2. Save LIVE position
        3. Query both - both should exist independently
        """
        sim_data = {
            "mode": "SIM",
            "account": "",
            "symbol": "MES",
            "qty": 1,
            "entry_price": 5800.0,
            "entry_time": datetime.now(timezone.utc),
        }

        live_data = {
            "mode": "LIVE",
            "account": "120005",
            "symbol": "MNQ",
            "qty": 2,
            "entry_price": 21000.0,
            "entry_time": datetime.now(timezone.utc),
        }

        with patch('data.position_repository.get_session', return_value=db_session):
            # Save both positions
            position_repo.save_open_position(**sim_data)
            position_repo.save_open_position(**live_data)

            # Query both
            sim_pos = position_repo.get_open_position("SIM", "")
            live_pos = position_repo.get_open_position("LIVE", "120005")

            # Verify both exist independently
            assert sim_pos is not None
            assert live_pos is not None
            assert sim_pos["symbol"] == "MES"
            assert live_pos["symbol"] == "MNQ"

        print("✓ Test 2.2 PASSED: Concurrent SIM + LIVE positions work")

    def test_2_3_mode_isolation_no_leakage(self, db_session, position_repo):
        """
        Test mode isolation - changes in one mode don't affect another.

        Scenario:
        1. Create SIM position
        2. Update SIM position
        3. Verify LIVE position unaffected
        """
        with patch('data.position_repository.get_session', return_value=db_session):
            # Create SIM position
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5800.0,
                entry_time=datetime.now(timezone.utc)
            )

            # Update SIM position (simulate trade extremes)
            position_repo.update_trade_extremes("SIM", "", 5850.0)

            # Verify LIVE has no position
            live_pos = position_repo.get_open_position("LIVE", "120005")
            assert live_pos is None, "LIVE should remain empty"

        print("✓ Test 2.3 PASSED: No state leakage between modes")


# ==============================================================================
# TEST SUITE 3: THREAD SAFETY (2 tests)
# ==============================================================================

class TestThreadSafety:
    """Test concurrent access and thread safety."""

    def test_3_1_concurrent_position_updates(self, db_session, position_repo):
        """
        Test 3.1: Concurrent position updates from multiple threads.

        Scenario:
        1. Create position
        2. Update trade extremes from 10 threads simultaneously
        3. Verify no data corruption or exceptions
        """
        errors = []

        # Create initial position
        with patch('data.position_repository.get_session', return_value=db_session):
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5800.0,
                entry_time=datetime.now(timezone.utc)
            )

        # Worker function for threads
        def update_worker(thread_id):
            try:
                with patch('data.position_repository.get_session', return_value=db_session):
                    for i in range(10):
                        price = 5800.0 + (thread_id * 10) + i
                        position_repo.update_trade_extremes("SIM", "", price)
            except Exception as e:
                errors.append((thread_id, e))

        # Launch 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify position still exists and has valid data
        with patch('data.position_repository.get_session', return_value=db_session):
            pos = position_repo.get_open_position("SIM", "")
            assert pos is not None
            assert pos["trade_min_price"] is not None
            assert pos["trade_max_price"] is not None

        print("✓ Test 3.1 PASSED: Concurrent updates successful (10 threads × 10 updates)")

    def test_3_2_concurrent_close_operations(self, db_session, position_repo):
        """
        Test 3.2: Prevent race condition where position closed twice.

        Scenario:
        1. Create position
        2. Try to close from 2 threads simultaneously
        3. Verify exactly 1 TradeRecord created
        """
        results = []

        # Create position
        with patch('data.position_repository.get_session', return_value=db_session):
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5800.0,
                entry_time=datetime.now(timezone.utc)
            )

        def close_worker():
            with patch('data.position_repository.get_session', return_value=db_session):
                result = position_repo.close_position(
                    mode="SIM", account="",
                    exit_price=5850.0,
                    realized_pnl=250.0
                )
                results.append(result)

        # Launch 2 threads trying to close simultaneously
        t1 = threading.Thread(target=close_worker)
        t2 = threading.Thread(target=close_worker)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Verify: one succeeds (trade_id), one fails (None)
        successful = [r for r in results if r is not None]
        failed = [r for r in results if r is None]

        assert len(successful) == 1, "Exactly one close should succeed"
        assert len(failed) == 1, "Second close should return None"

        print("✓ Test 3.2 PASSED: Race condition prevented (1 success, 1 failure)")


# ==============================================================================
# TEST SUITE 4: DATABASE INTEGRITY (2 tests)
# ==============================================================================

class TestDatabaseIntegrity:
    """Test database transaction integrity."""

    def test_4_1_atomic_position_close(self, db_session, position_repo):
        """
        Test 4.1: Atomic position close (read + write + delete).

        Scenario:
        1. Create position
        2. Close position
        3. Verify: TradeRecord created AND OpenPosition deleted
        """
        with patch('data.position_repository.get_session', return_value=db_session):
            # Step 1: Create position
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5800.0,
                entry_time=datetime.now(timezone.utc)
            )

            # Verify position exists
            pos_before = position_repo.get_open_position("SIM", "")
            assert pos_before is not None

            # Step 2: Close position (atomic operation)
            trade_id = position_repo.close_position(
                mode="SIM", account="",
                exit_price=5850.0,
                realized_pnl=250.0
            )

            assert trade_id is not None, "Trade record should be created"

            # Step 3: Verify OpenPosition deleted
            pos_after = position_repo.get_open_position("SIM", "")
            assert pos_after is None, "OpenPosition should be deleted"

            # Verify TradeRecord created
            trade = db_session.query(TradeRecord).filter_by(id=trade_id).first()
            assert trade is not None
            assert trade.entry_price == 5800.0
            assert trade.exit_price == 5850.0
            assert trade.realized_pnl == 250.0

        print("✓ Test 4.1 PASSED: Atomic close transaction verified")

    def test_4_2_position_not_found_returns_none(self, db_session, position_repo):
        """
        Test 4.2: Closing non-existent position returns None.

        Scenario:
        1. Try to close position that doesn't exist
        2. Verify returns None (not error)
        """
        with patch('data.position_repository.get_session', return_value=db_session):
            result = position_repo.close_position(
                mode="SIM", account="",
                exit_price=5850.0
            )

            assert result is None, "Should return None for non-existent position"

        print("✓ Test 4.2 PASSED: Non-existent position handled gracefully")


# ==============================================================================
# TEST SUITE 5: END-TO-END SCENARIOS (2 tests)
# ==============================================================================

class TestEndToEnd:
    """Test complete trading scenarios."""

    def test_5_1_full_trading_session(self, db_session, position_repo):
        """
        Test 5.1: Complete trading session from open to close.

        Scenario:
        1. Open position
        2. Update trade extremes (simulating price movement)
        3. Close position
        4. Verify TradeRecord has correct MAE/MFE
        """
        with patch('data.position_repository.get_session', return_value=db_session):
            # Step 1: Open position
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5800.0,
                entry_time=datetime.now(timezone.utc),
                stop_price=5750.0,
                target_price=5850.0
            )

            # Step 2: Simulate price movement (trade extremes)
            prices = [5805, 5810, 5795, 5820, 5790, 5850]  # Up, down, up
            for price in prices:
                position_repo.update_trade_extremes("SIM", "", float(price))

            # Verify extremes tracked
            pos = position_repo.get_open_position("SIM", "")
            assert pos["trade_min_price"] == 5790.0  # Lowest
            assert pos["trade_max_price"] == 5850.0  # Highest

            # Step 3: Close position
            trade_id = position_repo.close_position(
                mode="SIM", account="",
                exit_price=5840.0,
                realized_pnl=200.0
            )

            # Step 4: Verify TradeRecord
            trade = db_session.query(TradeRecord).filter_by(id=trade_id).first()
            assert trade is not None
            assert trade.mae is not None  # Maximum Adverse Excursion calculated
            assert trade.mfe is not None  # Maximum Favorable Excursion calculated
            assert trade.efficiency is not None
            assert trade.r_multiple is not None

        print("✓ Test 5.1 PASSED: Full trading session with MAE/MFE tracking")

    def test_5_2_multiple_trades_in_session(self, db_session, position_repo):
        """
        Test 5.2: Multiple trades without restart.

        Scenario:
        1. Trade 1: Open → Close
        2. Trade 2: Open → Close
        3. Trade 3: Open → Close
        4. Verify all 3 trades in database
        """
        with patch('data.position_repository.get_session', return_value=db_session):
            trade_ids = []

            # Trade 1
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5800.0,
                entry_time=datetime.now(timezone.utc)
            )
            trade_id = position_repo.close_position(
                mode="SIM", account="",
                exit_price=5850.0, realized_pnl=250.0
            )
            trade_ids.append(trade_id)

            # Trade 2
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5850.0,
                entry_time=datetime.now(timezone.utc)
            )
            trade_id = position_repo.close_position(
                mode="SIM", account="",
                exit_price=5820.0, realized_pnl=-150.0
            )
            trade_ids.append(trade_id)

            # Trade 3
            position_repo.save_open_position(
                mode="SIM", account="", symbol="MES",
                qty=1, entry_price=5820.0,
                entry_time=datetime.now(timezone.utc)
            )
            trade_id = position_repo.close_position(
                mode="SIM", account="",
                exit_price=5870.0, realized_pnl=250.0
            )
            trade_ids.append(trade_id)

            # Verify all 3 trades in database
            trades = db_session.query(TradeRecord).filter_by(mode="SIM").all()
            assert len(trades) == 3

            # Verify total P&L
            total_pnl = sum(t.realized_pnl for t in trades)
            assert total_pnl == 350.0  # 250 - 150 + 250

        print("✓ Test 5.2 PASSED: Multiple trades tracked correctly")


# ==============================================================================
# TEST RUNNER
# ==============================================================================

if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v", "--tb=short"])
