"""
tests/integration/conftest.py

Pytest fixtures for integration testing.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlmodel import SQLModel

from data.db_engine import get_session
from data.schema import OpenPosition, TradeRecord
from data.position_repository import PositionRepository


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session.

    Uses in-memory SQLite for fast, isolated tests.
    Each test gets a fresh database.

    Note: check_same_thread=False allows multi-threaded access for testing.
    """
    # Create in-memory SQLite database with multi-threading support
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    SQLModel.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture
def test_engine():
    """
    Create a test database engine using a temporary file.

    File-based SQLite works better with multi-threading than in-memory.
    """
    import tempfile
    import os

    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup
    engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def position_repo(test_engine):
    """
    Get position repository instance configured for testing.

    Patches the global engine and get_session to use the test database.
    File-based SQLite allows proper multi-threaded access.
    """
    from unittest.mock import patch
    from contextlib import contextmanager

    @contextmanager
    def test_get_session():
        """Test version of get_session using the test engine."""
        session = sessionmaker(bind=test_engine)()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Patch both the engine and get_session
    with patch('data.db_engine.engine', test_engine):
        with patch('data.position_repository.get_session', test_get_session):
            with patch('data.db_engine.get_session', test_get_session):
                yield PositionRepository()


@pytest.fixture
def sample_position_data():
    """Sample position data for testing."""
    return {
        "mode": "SIM",
        "account": "",
        "symbol": "MES",
        "qty": 1,
        "entry_price": 5800.0,
        "entry_time": datetime.now(timezone.utc),
        "entry_vwap": 5799.5,
        "entry_cum_delta": 1500.0,
        "entry_poc": 5800.0,
        "target_price": 5850.0,
        "stop_price": 5750.0,
    }


@pytest.fixture
def old_position_data():
    """Old position data (>24h) for stale testing."""
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    return {
        "mode": "SIM",
        "account": "",
        "symbol": "MES",
        "qty": 1,
        "entry_price": 5800.0,
        "entry_time": old_time,
        "created_at": old_time,
        "updated_at": old_time,
    }
