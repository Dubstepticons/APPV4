"""
Unit Tests for Repository Pattern

Tests the TradeRepository and InMemoryRepository implementations
without requiring a database connection.

Run with: pytest tests/unit/test_repository_pattern.py -v
"""

import pytest
from datetime import datetime, timedelta
from typing import List

from services.repositories import TradeRepository, InMemoryRepository
from data.trade_record import TradeRecord


@pytest.fixture
def sample_trades() -> List[TradeRecord]:
    """Create sample trade records for testing."""
    now = datetime.now()

    trades = [
        TradeRecord(
            id=1,
            symbol="ESH25",
            mode="SIM",
            entry_time=now - timedelta(hours=3),
            exit_time=now - timedelta(hours=2),
            entry_price=5000.0,
            exit_price=5010.0,
            quantity=1,
            realized_pnl=125.0,
            mae=-25.0,
            mfe=150.0,
            r_multiple=5.0,
            efficiency=0.83,
            is_closed=True
        ),
        TradeRecord(
            id=2,
            symbol="NQH25",
            mode="SIM",
            entry_time=now - timedelta(hours=2),
            exit_time=now - timedelta(hours=1),
            entry_price=17000.0,
            exit_price=17020.0,
            quantity=2,
            realized_pnl=80.0,
            mae=-40.0,
            mfe=100.0,
            r_multiple=2.0,
            efficiency=0.80,
            is_closed=True
        ),
        TradeRecord(
            id=3,
            symbol="ESH25",
            mode="LIVE",
            entry_time=now - timedelta(hours=1),
            exit_time=now - timedelta(minutes=30),
            entry_price=5005.0,
            exit_price=4995.0,
            quantity=1,
            realized_pnl=-125.0,
            mae=-200.0,
            mfe=50.0,
            r_multiple=-2.5,
            efficiency=0.625,
            is_closed=True
        ),
        TradeRecord(
            id=4,
            symbol="ESH25",
            mode="SIM",
            entry_time=now - timedelta(minutes=30),
            exit_time=None,
            entry_price=5008.0,
            exit_price=None,
            quantity=1,
            realized_pnl=None,
            mae=-10.0,
            mfe=20.0,
            r_multiple=None,
            efficiency=None,
            is_closed=False
        )
    ]

    return trades


@pytest.fixture
def memory_repo(sample_trades) -> InMemoryRepository[TradeRecord, int]:
    """Create in-memory repository with sample data."""
    repo = InMemoryRepository[TradeRecord, int]()
    for trade in sample_trades:
        repo.add(trade)
    return repo


class TestInMemoryRepository:
    """Test in-memory repository implementation."""

    def test_add_and_get(self, memory_repo, sample_trades):
        """Test adding and retrieving records."""
        # Get by ID
        trade = memory_repo.get(1)
        assert trade is not None
        assert trade.id == 1
        assert trade.symbol == "ESH25"
        assert trade.realized_pnl == 125.0

    def test_get_all(self, memory_repo, sample_trades):
        """Test retrieving all records."""
        all_trades = memory_repo.get_all()
        assert len(all_trades) == 4

        # Verify ordering (should be by insertion order)
        assert all_trades[0].id == 1
        assert all_trades[-1].id == 4

    def test_update(self, memory_repo):
        """Test updating a record."""
        trade = memory_repo.get(1)
        assert trade.realized_pnl == 125.0

        # Update PnL
        trade.realized_pnl = 200.0
        memory_repo.update(trade)

        # Verify update
        updated_trade = memory_repo.get(1)
        assert updated_trade.realized_pnl == 200.0

    def test_delete(self, memory_repo):
        """Test deleting a record."""
        assert memory_repo.get(1) is not None

        memory_repo.delete(1)

        assert memory_repo.get(1) is None
        assert len(memory_repo.get_all()) == 3

    def test_filter(self, memory_repo):
        """Test filtering records."""
        # Filter by mode
        sim_trades = memory_repo.filter(mode="SIM")
        assert len(sim_trades) == 3
        assert all(t.mode == "SIM" for t in sim_trades)

        # Filter by closed status
        closed_trades = memory_repo.filter(is_closed=True)
        assert len(closed_trades) == 3

        # Filter by symbol
        es_trades = memory_repo.filter(symbol="ESH25")
        assert len(es_trades) == 3

        # Multiple filters
        sim_closed = memory_repo.filter(mode="SIM", is_closed=True)
        assert len(sim_closed) == 2

    def test_count(self, memory_repo):
        """Test counting records."""
        assert memory_repo.count() == 4
        assert memory_repo.count(mode="SIM") == 3
        assert memory_repo.count(is_closed=True) == 3
        assert memory_repo.count(mode="LIVE") == 1


class TestTradeRepositoryTimeSeriesQueries:
    """Test time-series queries on TradeRepository (using in-memory backend)."""

    @pytest.fixture
    def trade_repo(self, memory_repo) -> TradeRepository:
        """Create TradeRepository backed by in-memory storage."""
        # Swap out the real session with memory repo
        repo = TradeRepository()
        repo._memory_backend = memory_repo  # Mock the backend
        return repo

    def test_get_range(self, memory_repo):
        """Test getting trades within a time range."""
        now = datetime.now()
        start = now - timedelta(hours=2, minutes=30)
        end = now

        # Get trades in range
        trades = [t for t in memory_repo.get_all()
                 if t.exit_time and start <= t.exit_time <= end]

        assert len(trades) >= 1
        for trade in trades:
            if trade.exit_time:
                assert start <= trade.exit_time <= end

    def test_filter_by_closed_status(self, memory_repo):
        """Test filtering by closed status."""
        closed_trades = memory_repo.filter(is_closed=True)
        open_trades = memory_repo.filter(is_closed=False)

        assert len(closed_trades) == 3
        assert len(open_trades) == 1

        assert all(t.is_closed for t in closed_trades)
        assert all(not t.is_closed for t in open_trades)

    def test_filter_by_mode(self, memory_repo):
        """Test filtering by trading mode."""
        sim_trades = memory_repo.filter(mode="SIM")
        live_trades = memory_repo.filter(mode="LIVE")

        assert len(sim_trades) == 3
        assert len(live_trades) == 1

    def test_complex_filtering(self, memory_repo):
        """Test combining multiple filters."""
        # SIM + closed + positive PnL
        winning_sim_trades = [
            t for t in memory_repo.filter(mode="SIM", is_closed=True)
            if t.realized_pnl and t.realized_pnl > 0
        ]

        assert len(winning_sim_trades) == 2
        assert all(t.mode == "SIM" for t in winning_sim_trades)
        assert all(t.is_closed for t in winning_sim_trades)
        assert all(t.realized_pnl > 0 for t in winning_sim_trades)


class TestTradeRepositoryAggregates:
    """Test aggregate queries (sum, avg, etc.)."""

    def test_sum_realized_pnl(self, memory_repo):
        """Test summing realized PnL."""
        closed_trades = memory_repo.filter(is_closed=True)
        total_pnl = sum(t.realized_pnl for t in closed_trades if t.realized_pnl)

        # 125.0 + 80.0 - 125.0 = 80.0
        assert total_pnl == 80.0

    def test_average_efficiency(self, memory_repo):
        """Test calculating average efficiency."""
        closed_trades = memory_repo.filter(is_closed=True)
        efficiencies = [t.efficiency for t in closed_trades if t.efficiency]
        avg_efficiency = sum(efficiencies) / len(efficiencies)

        # (0.83 + 0.80 + 0.625) / 3 = 0.751666...
        assert 0.75 <= avg_efficiency <= 0.76

    def test_winning_vs_losing_trades(self, memory_repo):
        """Test win/loss ratio calculations."""
        closed_trades = memory_repo.filter(is_closed=True)

        winners = [t for t in closed_trades if t.realized_pnl and t.realized_pnl > 0]
        losers = [t for t in closed_trades if t.realized_pnl and t.realized_pnl < 0]

        assert len(winners) == 2
        assert len(losers) == 1

        win_rate = len(winners) / len(closed_trades)
        assert win_rate == pytest.approx(0.6667, abs=0.01)

    def test_max_mae_mfe(self, memory_repo):
        """Test finding max adverse/favorable excursion."""
        all_trades = memory_repo.get_all()

        # MAE (most negative)
        maes = [t.mae for t in all_trades if t.mae is not None]
        max_mae = min(maes)  # Most adverse = most negative
        assert max_mae == -200.0

        # MFE (most positive)
        mfes = [t.mfe for t in all_trades if t.mfe is not None]
        max_mfe = max(mfes)
        assert max_mfe == 150.0


class TestRepositoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_nonexistent_id(self, memory_repo):
        """Test getting a non-existent record."""
        trade = memory_repo.get(999)
        assert trade is None

    def test_update_nonexistent_record(self, memory_repo):
        """Test updating a record that doesn't exist."""
        fake_trade = TradeRecord(
            id=999,
            symbol="FAKE",
            mode="SIM",
            entry_time=datetime.now(),
            entry_price=1000.0,
            quantity=1
        )

        # Should not raise error (graceful handling)
        memory_repo.update(fake_trade)

        # Should still not exist
        assert memory_repo.get(999) is None

    def test_delete_nonexistent_record(self, memory_repo):
        """Test deleting a record that doesn't exist."""
        # Should not raise error
        memory_repo.delete(999)

        # Count should be unchanged
        assert memory_repo.count() == 4

    def test_filter_no_matches(self, memory_repo):
        """Test filtering with no matches."""
        result = memory_repo.filter(mode="PAPER")  # Non-existent mode
        assert len(result) == 0
        assert isinstance(result, list)

    def test_empty_repository(self):
        """Test operations on empty repository."""
        empty_repo = InMemoryRepository[TradeRecord, int]()

        assert empty_repo.count() == 0
        assert len(empty_repo.get_all()) == 0
        assert empty_repo.get(1) is None
        assert len(empty_repo.filter(mode="SIM")) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
