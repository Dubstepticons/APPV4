"""
tests/integration/conftest.py

Pytest fixtures for integration testing.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data.db_engine import get_session
from data.schema import Base, OpenPosition, TradeRecord
from data.position_repository import PositionRepository


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session.

    Uses in-memory SQLite for fast, isolated tests.
    Each test gets a fresh database.
    """
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture
def position_repo():
    """Get position repository instance."""
    return PositionRepository()


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
