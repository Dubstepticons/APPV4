"""
Repository Package - Data Access Layer

Provides repository pattern implementations for clean architecture.

Usage:
    >>> from services.repositories import TradeRepository
    >>> repo = TradeRepository()
    >>> trades = repo.get_closed_trades_by_mode("SIM")
    >>> total_pnl = repo.sum_pnl(mode="SIM")

Available Repositories:
- TradeRepository: TradeRecord CRUD and analytics
- (Future) EquityRepository: EquityCurvePoint management
- (Future) AccountRepository: Account and balance management
"""

from services.repositories.base import (
    Repository,
    TimeSeriesRepository,
    AggregateRepository,
    UnitOfWork,
    InMemoryRepository
)

from services.repositories.trade_repository import (
    TradeRepository,
    TradeUnitOfWork
)

__all__ = [
    # Base classes
    "Repository",
    "TimeSeriesRepository",
    "AggregateRepository",
    "UnitOfWork",
    "InMemoryRepository",
    # Concrete repositories
    "TradeRepository",
    "TradeUnitOfWork",
]
