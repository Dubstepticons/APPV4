"""
Trade Repository - Data Access for TradeRecord

Concrete implementation of Repository pattern for trade data.
Uses SQLAlchemy for database operations.

Features:
- Type-safe CRUD operations
- Mode-aware queries (SIM/LIVE/DEBUG filtering)
- Time-range queries for historical analysis
- Aggregate functions (total P&L, win rate, etc.)
- Transaction support via UnitOfWork

Usage:
    >>> from data.db_engine import get_session
    >>> repo = TradeRepository(session_factory=get_session)
    >>> trades = repo.get_closed_trades_by_mode("SIM")
    >>> total_pnl = repo.sum_pnl(mode="SIM", is_closed=True)
"""

from typing import List, Optional, Callable
from datetime import datetime, timedelta
from contextlib import contextmanager

from data.db_engine import get_session
from data.schema import TradeRecord
from services.repositories.base import (
    TimeSeriesRepository,
    AggregateRepository,
    UnitOfWork
)
from utils.logger import get_logger

log = get_logger(__name__)


class TradeRepository(TimeSeriesRepository[TradeRecord, int], AggregateRepository[TradeRecord, int]):
    """
    Repository for TradeRecord entities.

    Provides high-level data access operations for trade history.
    Abstracts SQLAlchemy implementation details.
    """

    def __init__(self, session_factory: Callable = get_session):
        """
        Initialize repository.

        Args:
            session_factory: Callable that returns SQLAlchemy session
                           (default: get_session from db_engine)
        """
        self.session_factory = session_factory

    # Basic CRUD Operations

    def get_by_id(self, entity_id: int) -> Optional[TradeRecord]:
        """Get trade by ID"""
        with self.session_factory() as session:
            return session.query(TradeRecord).filter(TradeRecord.id == entity_id).first()

    def get_all(self) -> List[TradeRecord]:
        """
        Get all trades.

        Warning: Can be slow with large datasets. Use get_filtered() instead.
        """
        with self.session_factory() as session:
            return session.query(TradeRecord).all()

    def get_filtered(self, **filters) -> List[TradeRecord]:
        """
        Get trades matching filters.

        Args:
            **filters: Key-value pairs for filtering
                      Examples:
                      - mode="SIM"
                      - is_closed=True
                      - symbol="ESH25"

        Returns:
            List of matching trades
        """
        with self.session_factory() as session:
            query = session.query(TradeRecord)

            # Apply each filter
            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            return query.all()

    def add(self, entity: TradeRecord) -> TradeRecord:
        """
        Add new trade to database.

        Args:
            entity: TradeRecord to persist

        Returns:
            Persisted trade with ID populated
        """
        with self.session_factory() as session:
            session.add(entity)
            session.commit()
            session.refresh(entity)  # Populate auto-generated ID
            log.info(f"Trade added: {entity.symbol} | ID={entity.id} | PnL={entity.realized_pnl}")
            return entity

    def update(self, entity: TradeRecord) -> TradeRecord:
        """Update existing trade"""
        with self.session_factory() as session:
            if entity.id is None:
                raise ValueError("Cannot update trade without ID")

            session.merge(entity)
            session.commit()
            log.info(f"Trade updated: ID={entity.id}")
            return entity

    def delete(self, entity_id: int) -> bool:
        """Delete trade by ID"""
        with self.session_factory() as session:
            trade = session.query(TradeRecord).filter(TradeRecord.id == entity_id).first()
            if trade:
                session.delete(trade)
                session.commit()
                log.info(f"Trade deleted: ID={entity_id}")
                return True
            return False

    def exists(self, entity_id: int) -> bool:
        """Check if trade exists"""
        with self.session_factory() as session:
            return session.query(TradeRecord).filter(TradeRecord.id == entity_id).count() > 0

    def count(self, **filters) -> int:
        """Count trades matching filters"""
        with self.session_factory() as session:
            query = session.query(TradeRecord)

            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            return query.count()

    # Time-Series Operations

    def get_range(
        self,
        start: datetime,
        end: datetime,
        **filters
    ) -> List[TradeRecord]:
        """
        Get trades within time range.

        Uses exit_time for filtering (when trade was closed).

        Args:
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            **filters: Additional filters (e.g., mode="SIM")

        Returns:
            List of trades closed within range
        """
        with self.session_factory() as session:
            query = session.query(TradeRecord).filter(
                TradeRecord.exit_time >= start,
                TradeRecord.exit_time <= end
            )

            # Apply additional filters
            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            return query.order_by(TradeRecord.exit_time.asc()).all()

    def get_latest(self, n: int = 1, **filters) -> List[TradeRecord]:
        """
        Get n most recent closed trades.

        Args:
            n: Number of trades to return
            **filters: Optional filters (e.g., mode="SIM")

        Returns:
            List of most recent trades (newest first)
        """
        with self.session_factory() as session:
            query = session.query(TradeRecord).filter(
                TradeRecord.is_closed == True
            )

            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            return query.order_by(TradeRecord.exit_time.desc()).limit(n).all()

    def get_oldest(self, n: int = 1, **filters) -> List[TradeRecord]:
        """Get n oldest trades"""
        with self.session_factory() as session:
            query = session.query(TradeRecord).filter(
                TradeRecord.is_closed == True
            )

            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            return query.order_by(TradeRecord.exit_time.asc()).limit(n).all()

    # Aggregate Operations

    def sum_field(self, field_name: str, **filters) -> float:
        """Sum a numeric field (e.g., realized_pnl)"""
        from sqlalchemy import func

        with self.session_factory() as session:
            query = session.query(func.sum(getattr(TradeRecord, field_name)))

            # Apply filters
            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            result = query.scalar()
            return float(result) if result is not None else 0.0

    def avg_field(self, field_name: str, **filters) -> float:
        """Average a numeric field"""
        from sqlalchemy import func

        with self.session_factory() as session:
            query = session.query(func.avg(getattr(TradeRecord, field_name)))

            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            result = query.scalar()
            return float(result) if result is not None else 0.0

    def min_field(self, field_name: str, **filters) -> float:
        """Get minimum value of field"""
        from sqlalchemy import func

        with self.session_factory() as session:
            query = session.query(func.min(getattr(TradeRecord, field_name)))

            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            result = query.scalar()
            return float(result) if result is not None else 0.0

    def max_field(self, field_name: str, **filters) -> float:
        """Get maximum value of field"""
        from sqlalchemy import func

        with self.session_factory() as session:
            query = session.query(func.max(getattr(TradeRecord, field_name)))

            for key, value in filters.items():
                if hasattr(TradeRecord, key):
                    query = query.filter(getattr(TradeRecord, key) == value)

            result = query.scalar()
            return float(result) if result is not None else 0.0

    # Domain-Specific Queries

    def get_closed_trades_by_mode(self, mode: str) -> List[TradeRecord]:
        """
        Get all closed trades for specific mode.

        Args:
            mode: Trading mode ("SIM", "LIVE", or "DEBUG")

        Returns:
            List of closed trades, ordered by exit time
        """
        return self.get_filtered(mode=mode, is_closed=True)

    def get_open_positions(self, mode: Optional[str] = None) -> List[TradeRecord]:
        """
        Get currently open positions (not closed).

        Args:
            mode: Optional mode filter

        Returns:
            List of open trades
        """
        filters = {"is_closed": False}
        if mode:
            filters["mode"] = mode

        return self.get_filtered(**filters)

    def sum_pnl(self, mode: Optional[str] = None, **filters) -> float:
        """
        Calculate total realized P&L.

        Args:
            mode: Optional mode filter ("SIM", "LIVE", "DEBUG")
            **filters: Additional filters

        Returns:
            Total realized P&L
        """
        query_filters = {"is_closed": True}
        if mode:
            query_filters["mode"] = mode
        query_filters.update(filters)

        return self.sum_field("realized_pnl", **query_filters)

    def calculate_win_rate(self, mode: Optional[str] = None) -> float:
        """
        Calculate win rate (percentage of winning trades).

        Args:
            mode: Optional mode filter

        Returns:
            Win rate as decimal (0.0 to 1.0)
        """
        filters = {"is_closed": True}
        if mode:
            filters["mode"] = mode

        total_trades = self.count(**filters)
        if total_trades == 0:
            return 0.0

        with self.session_factory() as session:
            query = session.query(TradeRecord).filter(TradeRecord.is_closed == True)

            if mode:
                query = query.filter(TradeRecord.mode == mode)

            winning_trades = query.filter(TradeRecord.realized_pnl > 0).count()

        return winning_trades / total_trades

    def get_trades_for_timeframe(
        self,
        mode: str,
        hours: int
    ) -> List[TradeRecord]:
        """
        Get trades closed within last N hours.

        Args:
            mode: Trading mode
            hours: Number of hours to look back

        Returns:
            List of trades in timeframe
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        return self.get_range(start_time, end_time, mode=mode, is_closed=True)


class TradeUnitOfWork(UnitOfWork):
    """
    Unit of Work for trade operations.

    Ensures multiple repository operations execute atomically.
    """

    def __init__(self, session_factory: Callable = get_session):
        self.session_factory = session_factory
        self._session = None

    @contextmanager
    def transaction(self):
        """
        Transaction context manager.

        Usage:
            with uow.transaction():
                repo.add(trade1)
                repo.add(trade2)
                # Both commit together
        """
        self._session = self.session_factory()
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise
        finally:
            self._session.close()
            self._session = None

    def commit(self) -> None:
        """Commit current transaction"""
        if self._session:
            self._session.commit()

    def rollback(self) -> None:
        """Rollback current transaction"""
        if self._session:
            self._session.rollback()
