# -------------------- CLEAN SCHEMA (start)
"""
Clean DTC schema based on what Sierra Chart ACTUALLY sends:
- Type 401: TradeAccountResponse
- Type 501: MktDataResponse (market data, NOT positions)
- Type 600: AccountBalanceUpdate
- Type 3: Heartbeat

NO position data comes from Sierra - it only sends market data.
All position tracking must be INFERRED from order executions.

CRITICAL FIX: Added OpenPosition table for single source of truth.
Database is now authoritative for position state - fixes crash recovery issues.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Index, UniqueConstraint


class TradeRecord(SQLModel, table=True):
    """Complete trade record - entry to exit

    CRITICAL FIX: Composite indexes added for query optimization.
    """

    __tablename__ = "traderecord"  # Explicit table name

    # CRITICAL FIX: Composite indexes for faster queries
    # These significantly improve performance for mode-filtered queries
    __table_args__ = (
        Index("idx_trade_mode_exit_time", "mode", "exit_time"),
        Index("idx_trade_closed_mode", "is_closed", "mode"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Trade identification
    symbol: str
    side: str  # "LONG" or "SHORT"
    qty: int

    # Trade mode (SIM or LIVE)
    mode: str = Field(default="SIM", index=True)

    # Entry (from initial position or order execution)
    entry_time: datetime = Field(default_factory=datetime.utcnow, index=True)
    entry_price: float  # avg_entry from order/position data

    # Exit (empty until position is closed)
    exit_time: Optional[datetime] = Field(default=None, index=True)
    exit_price: Optional[float] = None
    is_closed: bool = Field(default=False)

    # P&L and commissions (for closed trades)
    realized_pnl: Optional[float] = None
    commissions: Optional[float] = None

    # Trade quality metrics
    r_multiple: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    efficiency: Optional[float] = None  # realized_pnl / mfe (capture ratio, 0.0-1.0+)

    # Account info
    account: Optional[str] = None

    # Entry/exit snapshots for UI navigation
    entry_vwap: Optional[float] = None
    entry_cum_delta: Optional[float] = None
    exit_vwap: Optional[float] = None
    exit_cum_delta: Optional[float] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class OrderRecord(SQLModel, table=True):
    """Order records for trade reconstruction"""

    id: Optional[int] = Field(default=None, primary_key=True)

    order_id: str = Field(index=True)
    symbol: str = Field(index=True)
    side: str  # "BUY" or "SELL"
    qty: int
    price: float

    filled_qty: int = Field(default=0)
    filled_price: Optional[float] = None
    status: str  # "PENDING", "FILLED", "CANCELLED"

    # Trade mode (SIM or LIVE)
    mode: str = Field(default="SIM", index=True)

    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    account: Optional[str] = None


class AccountBalance(SQLModel, table=True):
    """Account balance snapshots"""

    id: Optional[int] = Field(default=None, primary_key=True)

    account_id: str = Field(index=True)
    balance: float

    # Trade mode (SIM or LIVE)
    mode: str = Field(default="LIVE", index=True)

    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)


class OpenPosition(SQLModel, table=True):
    """
    Open position tracking - single source of truth for position state.

    CRITICAL FIX: Establishes database as authoritative source for position state.
    Fixes crash recovery, mode switching, and position inconsistency issues.

    INVARIANT: Only 0 or 1 row per (mode, account) combination.
    Composite unique constraint enforces this at database level.

    Design:
    - Write-through: Every position change → immediate DB write
    - Read on startup: Recover position state from DB
    - Read on mode switch: Load correct position for new mode
    - Delete on close: Move to TradeRecord table when trade completes

    Benefits:
    - Crash safety: Position persisted, survives restarts
    - Single source of truth: DB is authoritative, no conflicts
    - Mode isolation: Each (mode, account) has separate position
    - Audit trail: All position changes logged
    """

    __tablename__ = "openposition"

    # Composite unique constraint: Only one open position per (mode, account)
    # This enforces the invariant at database level
    __table_args__ = (
        UniqueConstraint('mode', 'account', name='uq_mode_account'),
        Index('idx_open_position_mode', 'mode'),  # Fast lookups by mode
    )

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Position identification (unique together)
    mode: str = Field(index=True)  # "SIM", "LIVE", or "DEBUG"
    account: str  # Account identifier (e.g., "Sim1", "120005")
    symbol: str  # Symbol (e.g., "MES", "MNQ", "MGC")

    # Position details
    qty: int  # Signed quantity: positive = long, negative = short
    side: str  # "LONG" or "SHORT" (redundant with qty sign, but explicit for clarity)
    entry_price: float  # Average entry price
    entry_time: datetime  # When position was opened (UTC)

    # Bracket orders (optional, if target/stop set)
    target_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Entry snapshots (captured at entry, for trade record)
    # These are static values from the moment position opened
    entry_vwap: Optional[float] = None  # VWAP at entry
    entry_cum_delta: Optional[float] = None  # Cumulative delta at entry
    entry_poc: Optional[float] = None  # Point of control at entry

    # Trade extremes (updated continuously while position open)
    # Used to calculate MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion)
    trade_min_price: Optional[float] = None  # Lowest price reached during trade
    trade_max_price: Optional[float] = None  # Highest price reached during trade

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# -------------------- CLEAN SCHEMA (end)
