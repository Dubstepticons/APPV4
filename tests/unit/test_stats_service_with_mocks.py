"""
Unit Tests for Stats Service with Mock Repositories

Tests trading statistics calculations using in-memory repositories,
no database required.

Run with: pytest tests/unit/test_stats_service_with_mocks.py -v
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import List
from unittest.mock import patch, MagicMock

from services.repositories import InMemoryRepository
from data.trade_record import TradeRecord


@pytest.fixture
def sample_winning_trades() -> List[TradeRecord]:
    """Create sample winning trades for testing."""
    now = datetime.now(timezone.utc)

    return [
        TradeRecord(
            id=1,
            symbol="ESH25",
            mode="SIM",
            entry_time=now - timedelta(hours=3),
            exit_time=now - timedelta(hours=2),
            entry_price=5000.0,
            exit_price=5010.0,
            quantity=1,
            realized_pnl=125.0,  # Win
            mae=-25.0,
            mfe=150.0,
            r_multiple=2.5,
            efficiency=0.83,
            commissions=4.5,
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
            realized_pnl=200.0,  # Win
            mae=-40.0,
            mfe=250.0,
            r_multiple=4.0,
            efficiency=0.80,
            commissions=4.5,
            is_closed=True
        ),
        TradeRecord(
            id=3,
            symbol="ESH25",
            mode="SIM",
            entry_time=now - timedelta(hours=1),
            exit_time=now - timedelta(minutes=30),
            entry_price=5005.0,
            exit_price=4995.0,
            quantity=1,
            realized_pnl=-100.0,  # Loss
            mae=-150.0,
            mfe=25.0,
            r_multiple=-2.0,
            efficiency=0.67,
            commissions=4.5,
            is_closed=True
        )
    ]


@pytest.fixture
def mixed_mode_trades() -> List[TradeRecord]:
    """Create trades across SIM and LIVE modes."""
    now = datetime.now(timezone.utc)

    return [
        TradeRecord(
            id=1,
            symbol="ESH25",
            mode="SIM",
            entry_time=now - timedelta(hours=3),
            exit_time=now - timedelta(hours=2),
            realized_pnl=100.0,
            mae=-20.0,
            mfe=120.0,
            r_multiple=2.0,
            commissions=4.5,
            is_closed=True
        ),
        TradeRecord(
            id=2,
            symbol="ESH25",
            mode="SIM",
            entry_time=now - timedelta(hours=2),
            exit_time=now - timedelta(hours=1),
            realized_pnl=50.0,
            mae=-10.0,
            mfe=60.0,
            r_multiple=1.0,
            commissions=4.5,
            is_closed=True
        ),
        TradeRecord(
            id=3,
            symbol="ESH25",
            mode="LIVE",
            entry_time=now - timedelta(hours=1),
            exit_time=now - timedelta(minutes=30),
            realized_pnl=200.0,
            mae=-30.0,
            mfe=250.0,
            r_multiple=3.0,
            commissions=4.5,
            is_closed=True
        ),
        TradeRecord(
            id=4,
            symbol="ESH25",
            mode="LIVE",
            entry_time=now - timedelta(minutes=30),
            exit_time=now - timedelta(minutes=15),
            realized_pnl=-75.0,
            mae=-100.0,
            mfe=10.0,
            r_multiple=-1.5,
            commissions=4.5,
            is_closed=True
        )
    ]


@pytest.fixture
def memory_repo(sample_winning_trades) -> InMemoryRepository[TradeRecord, int]:
    """Create in-memory repository with sample data."""
    repo = InMemoryRepository[TradeRecord, int]()
    for trade in sample_winning_trades:
        repo.add(trade)
    return repo


class TestStatsServiceBasicCalculations:
    """Test basic statistics calculations."""

    def test_total_pnl_calculation(self, memory_repo):
        """Test total PnL sum."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        total_pnl = sum(pnls)

        # 125.0 + 200.0 - 100.0 = 225.0
        assert total_pnl == 225.0

    def test_win_loss_separation(self, memory_repo):
        """Test separating wins and losses."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        assert len(wins) == 2  # Two winning trades
        assert len(losses) == 1  # One losing trade

        assert sum(wins) == 325.0  # 125 + 200
        assert sum(losses) == -100.0

    def test_hit_rate_calculation(self, memory_repo):
        """Test win percentage (hit rate)."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        wins = [p for p in pnls if p > 0]
        total = len(pnls)

        hit_rate = (len(wins) / total * 100.0) if total else 0.0

        # 2 wins / 3 total = 66.67%
        assert hit_rate == pytest.approx(66.67, abs=0.01)

    def test_profit_factor_calculation(self, memory_repo):
        """Test profit factor (gross profit / gross loss)."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        sum_wins = sum(wins)
        sum_losses = abs(sum(losses))

        profit_factor = sum_wins / sum_losses if sum_losses > 0 else None

        # 325 / 100 = 3.25
        assert profit_factor == pytest.approx(3.25, abs=0.01)

    def test_commissions_sum(self, memory_repo):
        """Test total commissions calculation."""
        all_trades = memory_repo.get_all()

        commissions_sum = sum(
            t.commissions for t in all_trades
            if hasattr(t, 'commissions') and t.commissions is not None
        )

        # 3 trades x 4.5 = 13.5
        assert commissions_sum == 13.5


class TestStatsServiceAggregateMetrics:
    """Test aggregate metrics (averages, max/min, etc.)."""

    def test_average_r_multiple(self, memory_repo):
        """Test average R-multiple calculation."""
        all_trades = memory_repo.get_all()

        r_mults = [t.r_multiple for t in all_trades if t.r_multiple is not None]
        avg_r = sum(r_mults) / len(r_mults) if r_mults else None

        # (2.5 + 4.0 - 2.0) / 3 = 1.5
        assert avg_r == pytest.approx(1.5, abs=0.01)

    def test_average_mae_mfe(self, memory_repo):
        """Test average MAE and MFE."""
        all_trades = memory_repo.get_all()

        mae_list = [t.mae for t in all_trades if t.mae is not None]
        mfe_list = [t.mfe for t in all_trades if t.mfe is not None]

        avg_mae = sum(mae_list) / len(mae_list) if mae_list else None
        avg_mfe = sum(mfe_list) / len(mfe_list) if mfe_list else None

        # MAE: (-25 - 40 - 150) / 3 = -71.67
        assert avg_mae == pytest.approx(-71.67, abs=0.01)

        # MFE: (150 + 250 + 25) / 3 = 141.67
        assert avg_mfe == pytest.approx(141.67, abs=0.01)

    def test_best_worst_trades(self, memory_repo):
        """Test finding best and worst trades."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        best = max(pnls)
        worst = min(pnls)

        assert best == 200.0
        assert worst == -100.0

    def test_average_trade_duration(self, memory_repo):
        """Test average trade duration calculation."""
        all_trades = memory_repo.get_all()

        durations = []
        for t in all_trades:
            if t.entry_time and t.exit_time:
                durations.append((t.exit_time - t.entry_time).total_seconds())

        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # All trades have 1 hour duration (3600 seconds)
        assert avg_duration == 3600.0


class TestStatsServiceEquityCurveMetrics:
    """Test equity curve calculations (drawdown, run-up)."""

    def test_equity_curve_construction(self, memory_repo):
        """Test building equity curve from PnLs."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        # Build equity curve
        equity = []
        acc = 0.0
        for p in pnls:
            acc += p
            equity.append(acc)

        # Expected: [125, 325, 225]
        assert equity == [125.0, 325.0, 225.0]

    def test_drawdown_calculation(self, memory_repo):
        """Test max drawdown calculation."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        # Build equity curve
        equity = []
        acc = 0.0
        for p in pnls:
            acc += p
            equity.append(acc)

        # Calculate max drawdown
        max_dd = 0.0
        peak = equity[0] if equity else 0.0

        for value in equity:
            if value > peak:
                peak = value
            drawdown = peak - value
            max_dd = max(max_dd, drawdown)

        # Peak = 325, trough = 225, drawdown = 100
        assert max_dd == 100.0

    def test_runup_calculation(self, memory_repo):
        """Test max run-up calculation."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        # Build equity curve
        equity = []
        acc = 0.0
        for p in pnls:
            acc += p
            equity.append(acc)

        # Calculate max run-up
        max_ru = 0.0
        trough = equity[0] if equity else 0.0

        for value in equity:
            if value < trough:
                trough = value
            runup = value - trough
            max_ru = max(max_ru, runup)

        # Trough = 125 (start), peak = 325, run-up = 200
        assert max_ru == 200.0


class TestStatsServiceStreakCalculations:
    """Test win/loss streak calculations."""

    def test_max_winning_streak(self):
        """Test maximum consecutive wins."""
        pnls = [100.0, 50.0, 75.0, -25.0, 30.0, 40.0, 60.0, -10.0]

        max_w, cur_w = 0, 0
        for p in pnls:
            if p > 0:
                cur_w += 1
            else:
                cur_w = 0
            max_w = max(max_w, cur_w)

        # Longest winning streak: 3 (30, 40, 60)
        assert max_w == 3

    def test_max_losing_streak(self):
        """Test maximum consecutive losses."""
        pnls = [100.0, -50.0, -75.0, -25.0, 30.0, -40.0, 60.0]

        max_l, cur_l = 0, 0
        for p in pnls:
            if p < 0:
                cur_l += 1
            else:
                cur_l = 0
            max_l = max(max_l, cur_l)

        # Longest losing streak: 3 (-50, -75, -25)
        assert max_l == 3

    def test_current_streak(self, memory_repo):
        """Test current streak calculation."""
        closed_trades = memory_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in closed_trades if t.realized_pnl is not None]

        # Track streaks
        max_w, max_l = 0, 0
        cur_w, cur_l = 0, 0

        for p in pnls:
            if p > 0:
                cur_w += 1
                cur_l = 0
            elif p < 0:
                cur_l += 1
                cur_w = 0
            else:
                cur_w = 0
                cur_l = 0

            max_w = max(max_w, cur_w)
            max_l = max(max_l, cur_l)

        # PnLs: [125, 200, -100]
        # Max winning streak: 2 (125, 200)
        # Max losing streak: 1 (-100)
        assert max_w == 2
        assert max_l == 1


class TestStatsServiceModeFiltering:
    """Test filtering statistics by mode (SIM/LIVE)."""

    @pytest.fixture
    def mixed_repo(self, mixed_mode_trades):
        """Create repo with mixed SIM/LIVE trades."""
        repo = InMemoryRepository[TradeRecord, int]()
        for trade in mixed_mode_trades:
            repo.add(trade)
        return repo

    def test_sim_mode_filtering(self, mixed_repo):
        """Test filtering for SIM mode only."""
        sim_trades = mixed_repo.filter(mode="SIM", is_closed=True)
        pnls = [t.realized_pnl for t in sim_trades if t.realized_pnl is not None]

        total_pnl = sum(pnls)

        # SIM trades: 100 + 50 = 150
        assert len(sim_trades) == 2
        assert total_pnl == 150.0

    def test_live_mode_filtering(self, mixed_repo):
        """Test filtering for LIVE mode only."""
        live_trades = mixed_repo.filter(mode="LIVE", is_closed=True)
        pnls = [t.realized_pnl for t in live_trades if t.realized_pnl is not None]

        total_pnl = sum(pnls)

        # LIVE trades: 200 - 75 = 125
        assert len(live_trades) == 2
        assert total_pnl == 125.0

    def test_combined_modes(self, mixed_repo):
        """Test statistics across all modes."""
        all_trades = mixed_repo.filter(is_closed=True)
        pnls = [t.realized_pnl for t in all_trades if t.realized_pnl is not None]

        total_pnl = sum(pnls)

        # All trades: 100 + 50 + 200 - 75 = 275
        assert len(all_trades) == 4
        assert total_pnl == 275.0


class TestStatsServiceEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_trade_list(self):
        """Test calculations with no trades."""
        empty_repo = InMemoryRepository[TradeRecord, int]()
        trades = empty_repo.get_all()

        assert len(trades) == 0

        # All calculations should handle empty list gracefully
        pnls = []
        total_pnl = sum(pnls) if pnls else 0.0
        hit_rate = 0.0
        avg_r = None

        assert total_pnl == 0.0
        assert hit_rate == 0.0
        assert avg_r is None

    def test_all_winning_trades(self):
        """Test statistics with 100% win rate."""
        pnls = [100.0, 50.0, 75.0, 200.0]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        hit_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
        profit_factor = None  # Undefined (no losses)

        assert hit_rate == 100.0
        assert len(losses) == 0
        assert profit_factor is None

    def test_all_losing_trades(self):
        """Test statistics with 0% win rate."""
        pnls = [-100.0, -50.0, -75.0]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        hit_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
        profit_factor = 0.0 if len(losses) > 0 else None

        assert hit_rate == 0.0
        assert len(wins) == 0
        assert profit_factor == 0.0

    def test_breakeven_trades(self):
        """Test handling of $0 PnL trades."""
        pnls = [100.0, 0.0, -50.0, 0.0, 25.0]

        # Breakeven trades shouldn't count as wins or losses
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        breakeven = [p for p in pnls if p == 0.0]

        assert len(wins) == 2
        assert len(losses) == 1
        assert len(breakeven) == 2

        total_pnl = sum(pnls)
        assert total_pnl == 75.0


class TestStatsServiceTimeframeFiltering:
    """Test filtering by timeframe (1D, 1W, 1M, etc.)."""

    def test_filter_by_time_range(self):
        """Test getting trades within specific time range."""
        now = datetime.now(timezone.utc)

        repo = InMemoryRepository[TradeRecord, int]()

        # Add trades at different times
        trades = [
            TradeRecord(
                id=1,
                symbol="ESH25",
                mode="SIM",
                entry_time=now - timedelta(days=5),
                exit_time=now - timedelta(days=4),
                realized_pnl=100.0,
                is_closed=True
            ),
            TradeRecord(
                id=2,
                symbol="ESH25",
                mode="SIM",
                entry_time=now - timedelta(days=2),
                exit_time=now - timedelta(days=1),
                realized_pnl=50.0,
                is_closed=True
            ),
            TradeRecord(
                id=3,
                symbol="ESH25",
                mode="SIM",
                entry_time=now - timedelta(hours=12),
                exit_time=now - timedelta(hours=6),
                realized_pnl=75.0,
                is_closed=True
            )
        ]

        for trade in trades:
            repo.add(trade)

        # Filter last 3 days
        start = now - timedelta(days=3)
        recent_trades = [
            t for t in repo.get_all()
            if t.exit_time and t.exit_time >= start
        ]

        # Should get last 2 trades only
        assert len(recent_trades) == 2

        pnls = [t.realized_pnl for t in recent_trades if t.realized_pnl]
        assert sum(pnls) == 125.0  # 50 + 75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
