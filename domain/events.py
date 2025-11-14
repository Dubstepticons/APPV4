"""
domain/events.py

Typed domain events to replace dict payloads across the application.

This module provides strongly-typed dataclasses for all events flowing through
the SignalBus, replacing the previous dict-based approach with type-safe,
validated domain models.

Architecture Benefits:
- Type safety: IDE autocomplete and static type checking
- Validation: Automatic validation of required fields
- Documentation: Self-documenting event structures
- Testability: Easy to mock and test
- Maintainability: Clear contracts between components

Usage:
    from domain.events import OrderUpdateEvent, PositionUpdateEvent

    # Create event
    event = OrderUpdateEvent(
        account="Sim1",
        order_id=12345,
        price=Decimal("6750.25"),
        quantity=1,
        mode="SIM"
    )

    # Emit via SignalBus
    signal_bus.orderUpdateReceived.emit(event)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


# =============================================================================
# ACCOUNT EVENTS
# =============================================================================

@dataclass
class TradeAccountEvent:
    """Trade account response from DTC."""
    account: str
    balance: Optional[float] = None
    cash_balance: Optional[float] = None
    securities_value: Optional[float] = None
    margin_requirement: Optional[float] = None
    open_positions_profit_loss: Optional[float] = None
    daily_profit_loss: Optional[float] = None
    timestamp: Optional[datetime] = None

    # Raw DTC message (for debugging)
    raw_message: Optional[dict] = field(default=None, repr=False)


# =============================================================================
# POSITION EVENTS
# =============================================================================

@dataclass
class PositionUpdateEvent:
    """Position update from DTC."""
    symbol: str
    account: str
    quantity: float  # Positive = long, negative = short
    average_price: float
    mode: str  # "SIM", "LIVE", or "DEBUG"

    # Optional fields
    position_id: Optional[str] = None
    trade_account: Optional[str] = None
    unrealized_pnl: Optional[float] = None
    timestamp: Optional[datetime] = None

    # Raw DTC message (for debugging)
    raw_message: Optional[dict] = field(default=None, repr=False)

    @property
    def is_long(self) -> bool:
        """Return True if this is a long position."""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Return True if this is a short position."""
        return self.quantity < 0

    @property
    def is_flat(self) -> bool:
        """Return True if no position (flat)."""
        return self.quantity == 0


@dataclass
class PositionClosedEvent:
    """Position closed - complete trade record for analytics."""
    # Trade identification
    symbol: str
    account: str
    mode: str  # "SIM", "LIVE", or "DEBUG"

    # Trade details
    side: str  # "LONG" or "SHORT"
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime

    # Financial metrics
    realized_pnl: float
    commission: float
    net_pnl: float  # realized_pnl - commission

    # Risk metrics (optional)
    mae: Optional[float] = None  # Maximum Adverse Excursion
    mfe: Optional[float] = None  # Maximum Favorable Excursion
    r_multiple: Optional[float] = None

    # Market context (optional)
    entry_vwap: Optional[float] = None
    exit_vwap: Optional[float] = None
    entry_cum_delta: Optional[float] = None
    exit_cum_delta: Optional[float] = None
    entry_poc: Optional[float] = None
    exit_poc: Optional[float] = None

    # Database ID (if persisted)
    trade_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dict for backwards compatibility."""
        return {
            "symbol": self.symbol,
            "account": self.account,
            "mode": self.mode,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "realized_pnl": self.realized_pnl,
            "commission": self.commission,
            "net_pnl": self.net_pnl,
            "mae": self.mae,
            "mfe": self.mfe,
            "r_multiple": self.r_multiple,
            "entry_vwap": self.entry_vwap,
            "exit_vwap": self.exit_vwap,
            "entry_cum_delta": self.entry_cum_delta,
            "exit_cum_delta": self.exit_cum_delta,
            "entry_poc": self.entry_poc,
            "exit_poc": self.exit_poc,
            "trade_id": self.trade_id,
        }


@dataclass
class TradeCloseRequestEvent:
    """User-initiated trade close request from Panel2."""
    # Trade identification
    symbol: str
    account: str
    mode: str

    # Position details
    quantity: float
    side: str  # "LONG" or "SHORT"
    entry_price: float
    entry_time: datetime

    # Exit context
    exit_price: float
    exit_time: datetime

    # Market snapshots at entry
    entry_vwap: Optional[float] = None
    entry_cum_delta: Optional[float] = None
    entry_poc: Optional[float] = None

    # Market snapshots at exit
    exit_vwap: Optional[float] = None
    exit_cum_delta: Optional[float] = None
    exit_poc: Optional[float] = None

    # Risk metrics
    mae: Optional[float] = None
    mfe: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dict for backwards compatibility."""
        return {
            "symbol": self.symbol,
            "account": self.account,
            "mode": self.mode,
            "quantity": self.quantity,
            "side": self.side,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time,
            "entry_vwap": self.entry_vwap,
            "entry_cum_delta": self.entry_cum_delta,
            "entry_poc": self.entry_poc,
            "exit_vwap": self.exit_vwap,
            "exit_cum_delta": self.exit_cum_delta,
            "exit_poc": self.exit_poc,
            "mae": self.mae,
            "mfe": self.mfe,
        }


@dataclass
class PositionExtremesUpdateEvent:
    """Position extremes updated for MAE/MFE tracking."""
    mode: str
    account: str
    price: float
    timestamp: Optional[datetime] = None


# =============================================================================
# ORDER EVENTS
# =============================================================================

@dataclass
class OrderFillEvent:
    """Order fill received from DTC."""
    order_id: int
    symbol: str
    account: str
    fill_price: float
    fill_quantity: float
    fill_time: datetime
    mode: str

    # Optional fields
    commission: Optional[float] = None
    order_type: Optional[str] = None  # "MARKET", "LIMIT", "STOP", etc.

    # Raw DTC message (for debugging)
    raw_message: Optional[dict] = field(default=None, repr=False)


@dataclass
class OrderUpdateEvent:
    """Order status update from DTC."""
    order_id: int
    symbol: str
    account: str
    status: str  # "PENDING", "FILLED", "PARTIALLY_FILLED", "CANCELLED", etc.
    mode: str

    # Order details
    order_type: Optional[str] = None
    side: Optional[str] = None  # "BUY" or "SELL"
    price: Optional[float] = None
    quantity: Optional[float] = None
    filled_quantity: Optional[float] = None
    remaining_quantity: Optional[float] = None

    # Timestamps
    order_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    # Raw DTC message (for debugging)
    raw_message: Optional[dict] = field(default=None, repr=False)


@dataclass
class OrderSubmitRequestEvent:
    """Order submission request."""
    symbol: str
    account: str
    side: str  # "BUY" or "SELL"
    quantity: float
    order_type: str  # "MARKET", "LIMIT", "STOP", etc.
    mode: str

    # Optional fields
    price: Optional[float] = None  # For LIMIT/STOP orders
    stop_price: Optional[float] = None  # For STOP orders
    time_in_force: Optional[str] = None  # "DAY", "GTC", etc.


# =============================================================================
# BALANCE EVENTS
# =============================================================================

@dataclass
class BalanceUpdateEvent:
    """Balance updated event."""
    balance: float
    account: str
    mode: str
    timestamp: Optional[datetime] = None

    # Source of balance update (for debugging)
    source: Optional[str] = None  # "DTC", "TRADE_CLOSE", "MANUAL_RESET", etc.


@dataclass
class BalanceDisplayRequestEvent:
    """Request Panel1 to display balance."""
    balance: float
    mode: str


@dataclass
class EquityPointRequestEvent:
    """Request Panel1 to add equity point."""
    balance: float
    mode: str
    timestamp: Optional[datetime] = None


# =============================================================================
# MODE EVENTS
# =============================================================================

@dataclass
class ModeChangeEvent:
    """Trading mode changed."""
    old_mode: str
    new_mode: str
    account: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    # Reason for mode change
    reason: Optional[str] = None  # "DTC_MESSAGE", "USER_REQUEST", "POSITION_CLOSE", etc.


@dataclass
class ModeSwitchRequestEvent:
    """User requested mode switch."""
    requested_mode: str
    current_mode: str
    account: Optional[str] = None


@dataclass
class ModeDriftDetectedEvent:
    """Mode drift detected between expected and actual."""
    expected_mode: str
    actual_mode: str
    account: Optional[str] = None


# =============================================================================
# UI EVENTS
# =============================================================================

@dataclass
class StatusMessageEvent:
    """Status message to display."""
    message: str
    timeout_ms: int = 3000
    severity: str = "INFO"  # "INFO", "WARNING", "ERROR", "SUCCESS"


@dataclass
class ErrorMessageEvent:
    """Error message to display."""
    message: str
    error: Optional[Exception] = None
    context: Optional[str] = None


# =============================================================================
# ANALYTICS EVENTS
# =============================================================================

@dataclass
class TradeClosedForAnalyticsEvent:
    """Trade closed event specifically for Panel3 analytics."""
    # Same fields as PositionClosedEvent but semantically distinct
    symbol: str
    account: str
    mode: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    realized_pnl: float
    commission: float
    net_pnl: float

    # Risk metrics
    mae: Optional[float] = None
    mfe: Optional[float] = None
    r_multiple: Optional[float] = None

    # Market context
    entry_vwap: Optional[float] = None
    exit_vwap: Optional[float] = None
    entry_cum_delta: Optional[float] = None
    exit_cum_delta: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dict for backwards compatibility with existing analytics."""
        return {
            "symbol": self.symbol,
            "account": self.account,
            "mode": self.mode,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "realized_pnl": self.realized_pnl,
            "commission": self.commission,
            "net_pnl": self.net_pnl,
            "mae": self.mae,
            "mfe": self.mfe,
            "r_multiple": self.r_multiple,
            "entry_vwap": self.entry_vwap,
            "exit_vwap": self.exit_vwap,
            "entry_cum_delta": self.entry_cum_delta,
            "exit_cum_delta": self.exit_cum_delta,
        }


@dataclass
class MetricsReloadRequestEvent:
    """Metrics reload requested."""
    timeframe: str  # "1D", "1W", "1M", "ALL"
    mode: Optional[str] = None


# =============================================================================
# CHART EVENTS
# =============================================================================

@dataclass
class ChartClickEvent:
    """Chart click detected."""
    symbol: str
    price: float
    timestamp: Optional[datetime] = None


@dataclass
class VWAPUpdateEvent:
    """VWAP updated on chart."""
    symbol: str
    vwap: float
    timestamp: Optional[datetime] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def event_to_dict(event) -> dict:
    """
    Convert any event to dict for backwards compatibility.

    Args:
        event: Any dataclass event

    Returns:
        Dict representation of the event
    """
    if hasattr(event, 'to_dict'):
        return event.to_dict()

    from dataclasses import asdict
    return asdict(event)
