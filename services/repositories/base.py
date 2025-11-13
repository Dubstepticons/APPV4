"""
Base Repository - Abstract Data Access Layer

Provides generic repository interfaces following Repository Pattern.
Enables swapping database implementations and mocking for tests.

Design Principles:
- Dependency Inversion: High-level code depends on abstractions
- Single Responsibility: Repositories only handle data access
- Interface Segregation: Specific interfaces for each aggregate root

Benefits:
- Testable without real database (use mock repositories)
- Database agnostic (PostgreSQL, SQLite, in-memory)
- Clear separation between business logic and persistence
- Simplified testing with repository fakes
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any
from datetime import datetime
from contextlib import contextmanager

# Type variables for generic repositories
T = TypeVar('T')  # Entity type (TradeRecord, EquityCurvePoint, etc.)
ID = TypeVar('ID')  # ID type (int, str, UUID, etc.)


class Repository(ABC, Generic[T, ID]):
    """
    Base repository interface for data access.

    Generic parameters:
        T: Entity type (e.g., TradeRecord)
        ID: Primary key type (e.g., int)

    Standard CRUD operations with optional filters.
    """

    @abstractmethod
    def get_by_id(self, entity_id: ID) -> Optional[T]:
        """
        Retrieve entity by primary key.

        Args:
            entity_id: Primary key value

        Returns:
            Entity instance or None if not found
        """
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """
        Retrieve all entities of this type.

        Returns:
            List of all entities (may be empty)

        Warning:
            Can be slow for large datasets. Consider using get_filtered() instead.
        """
        pass

    @abstractmethod
    def get_filtered(self, **filters) -> List[T]:
        """
        Retrieve entities matching filters.

        Args:
            **filters: Key-value pairs for filtering
                      Example: mode="SIM", is_closed=True

        Returns:
            List of matching entities
        """
        pass

    @abstractmethod
    def add(self, entity: T) -> T:
        """
        Add new entity to repository.

        Args:
            entity: Entity to persist

        Returns:
            Persisted entity (with ID populated if auto-generated)

        Raises:
            IntegrityError: If constraint violated (duplicate key, etc.)
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update existing entity.

        Args:
            entity: Entity with updated values (must have valid ID)

        Returns:
            Updated entity

        Raises:
            ValueError: If entity ID is None or doesn't exist
        """
        pass

    @abstractmethod
    def delete(self, entity_id: ID) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Primary key of entity to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, entity_id: ID) -> bool:
        """
        Check if entity exists.

        Args:
            entity_id: Primary key to check

        Returns:
            True if entity exists, False otherwise
        """
        pass

    @abstractmethod
    def count(self, **filters) -> int:
        """
        Count entities matching filters.

        Args:
            **filters: Optional filters (same as get_filtered)

        Returns:
            Number of matching entities
        """
        pass


class UnitOfWork(ABC):
    """
    Unit of Work pattern for transaction management.

    Ensures multiple repository operations execute atomically.
    All changes commit together or roll back together.

    Usage:
        >>> with unit_of_work.transaction():
        ...     trade_repo.add(trade)
        ...     balance_repo.update(balance)
        ...     # Both commit together
    """

    @abstractmethod
    @contextmanager
    def transaction(self):
        """
        Context manager for transactional operations.

        Usage:
            with uow.transaction():
                repo1.add(entity1)
                repo2.update(entity2)
                # Auto-commit on success, rollback on exception
        """
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit current transaction"""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback current transaction"""
        pass


class TimeSeriesRepository(Repository[T, ID], ABC):
    """
    Repository specialized for time-series data.

    Adds time-based queries for equity curves, metrics, etc.
    """

    @abstractmethod
    def get_range(
        self,
        start: datetime,
        end: datetime,
        **filters
    ) -> List[T]:
        """
        Get entities within time range.

        Args:
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            **filters: Additional filters (e.g., mode="SIM")

        Returns:
            List of entities in time range
        """
        pass

    @abstractmethod
    def get_latest(self, n: int = 1, **filters) -> List[T]:
        """
        Get n most recent entities.

        Args:
            n: Number of recent entities to return
            **filters: Optional filters

        Returns:
            List of most recent entities (newest first)
        """
        pass

    @abstractmethod
    def get_oldest(self, n: int = 1, **filters) -> List[T]:
        """
        Get n oldest entities.

        Args:
            n: Number of oldest entities to return
            **filters: Optional filters

        Returns:
            List of oldest entities (oldest first)
        """
        pass


class AggregateRepository(Repository[T, ID], ABC):
    """
    Repository for aggregate operations (sum, avg, count).

    Used for statistics and analytics queries.
    """

    @abstractmethod
    def sum_field(self, field_name: str, **filters) -> float:
        """
        Sum a numeric field.

        Args:
            field_name: Name of field to sum
            **filters: Optional filters

        Returns:
            Sum of field values
        """
        pass

    @abstractmethod
    def avg_field(self, field_name: str, **filters) -> float:
        """
        Average a numeric field.

        Args:
            field_name: Name of field to average
            **filters: Optional filters

        Returns:
            Average of field values
        """
        pass

    @abstractmethod
    def min_field(self, field_name: str, **filters) -> Any:
        """Get minimum value of field"""
        pass

    @abstractmethod
    def max_field(self, field_name: str, **filters) -> Any:
        """Get maximum value of field"""
        pass


class InMemoryRepository(Repository[T, ID]):
    """
    Simple in-memory repository for testing.

    Stores entities in a dictionary. Not persistent.
    Useful for unit tests and mocking.
    """

    def __init__(self):
        self._storage: dict[ID, T] = {}
        self._next_id: int = 1

    def get_by_id(self, entity_id: ID) -> Optional[T]:
        return self._storage.get(entity_id)

    def get_all(self) -> List[T]:
        return list(self._storage.values())

    def get_filtered(self, **filters) -> List[T]:
        """
        Filter by matching attributes.

        Note: Simple equality check only. For complex queries use SQL repositories.
        """
        results = []
        for entity in self._storage.values():
            match = all(
                getattr(entity, key, None) == value
                for key, value in filters.items()
            )
            if match:
                results.append(entity)
        return results

    def add(self, entity: T) -> T:
        # Auto-assign ID if entity has 'id' attribute and it's None
        if hasattr(entity, 'id') and entity.id is None:
            entity.id = self._next_id
            self._next_id += 1

        entity_id = getattr(entity, 'id')
        self._storage[entity_id] = entity
        return entity

    def update(self, entity: T) -> T:
        entity_id = getattr(entity, 'id', None)
        if entity_id is None:
            raise ValueError("Entity must have an ID to update")

        if entity_id not in self._storage:
            raise ValueError(f"Entity with ID {entity_id} not found")

        self._storage[entity_id] = entity
        return entity

    def delete(self, entity_id: ID) -> bool:
        if entity_id in self._storage:
            del self._storage[entity_id]
            return True
        return False

    def exists(self, entity_id: ID) -> bool:
        return entity_id in self._storage

    def count(self, **filters) -> int:
        if not filters:
            return len(self._storage)
        return len(self.get_filtered(**filters))

    def clear(self) -> None:
        """Clear all data (testing only)"""
        self._storage.clear()
        self._next_id = 1
