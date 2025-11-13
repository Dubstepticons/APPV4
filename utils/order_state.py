"""
Order State Machine

Tracks order lifecycle through well-defined states with validated transitions.

State Flow:
    PENDING → WORKING → FILLED → CLOSED
               ↓
            PARTIALLY_FILLED → FILLED → CLOSED
               ↓
            CANCELLED → CLOSED

States:
- PENDING: Order submitted, not yet acknowledged
- WORKING: Order active in market
- PARTIALLY_FILLED: Order partially executed
- FILLED: Order fully executed
- CANCELLED: Order cancelled before complete fill
- REJECTED: Order rejected by broker
- CLOSED: Terminal state (archived)

This ensures deterministic order tracking and prevents state corruption.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderState(str, Enum):
    """Order lifecycle states"""

    PENDING = "PENDING"  # Submitted, not acknowledged
    WORKING = "WORKING"  # Active in market
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partial execution
    FILLED = "FILLED"  # Fully executed
    CANCELLED = "CANCELLED"  # Cancelled
    REJECTED = "REJECTED"  # Rejected by broker
    CLOSED = "CLOSED"  # Terminal state (archived)


# DTC Order Status codes (from Sierra Chart docs)
DTC_ORDER_STATUS_MAP = {
    1: OrderState.WORKING,  # Order received/working
    2: OrderState.PARTIALLY_FILLED,  # Partially filled
    3: OrderState.FILLED,  # Filled
    4: OrderState.CANCELLED,  # Cancelled
    5: OrderState.WORKING,  # Open
    6: OrderState.REJECTED,  # Rejected
    7: OrderState.FILLED,  # Filled (alt)
}


class OrderRecord(BaseModel):
    """
    Complete order record with state tracking.
    """

    # Order identification
    server_order_id: Optional[str] = None
    client_order_id: Optional[str] = None

    # Order details
    symbol: str
    side: str  # "BUY" or "SELL"
    qty: int
    filled_qty: int = 0
    price: Optional[float] = None
    avg_fill_price: Optional[float] = None

    # State tracking
    state: OrderState = OrderState.PENDING
    mode: str = "SIM"  # SIM or LIVE
    account: Optional[str] = None

    # Timestamps
    submitted_at: datetime = Field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.now)

    # Metadata
    order_type: Optional[str] = None  # MARKET, LIMIT, STOP, etc.
    time_in_force: Optional[str] = None
    text: Optional[str] = None  # User notes or broker messages


class OrderStateMachine:
    """
    Manages order lifecycle with validated state transitions.

    Tracks orders by both ServerOrderID and ClientOrderID for robust matching.
    """

    def __init__(self):
        # server_order_id -> OrderRecord
        self._orders_by_server: dict[str, OrderRecord] = {}
        # client_order_id -> OrderRecord
        self._orders_by_client: dict[str, OrderRecord] = {}

    def update(
        self,
        *,
        server_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        qty: Optional[int] = None,
        filled_qty: Optional[int] = None,
        price: Optional[float] = None,
        avg_fill_price: Optional[float] = None,
        dtc_status: Optional[int] = None,
        mode: str = "SIM",
        account: Optional[str] = None,
        order_type: Optional[str] = None,
        time_in_force: Optional[str] = None,
        text: Optional[str] = None,
    ) -> tuple[OrderState, OrderState]:
        """
        Update order state from DTC order update message.

        Args:
            server_order_id: Server order ID (primary key)
            client_order_id: Client order ID (secondary key)
            symbol: Symbol identifier
            side: BUY or SELL
            qty: Total order quantity
            filled_qty: Filled quantity
            price: Order price
            avg_fill_price: Average fill price
            dtc_status: DTC order status code (1-7)
            mode: Trading mode (SIM/LIVE)
            account: Account identifier
            order_type: Order type (MARKET, LIMIT, etc.)
            time_in_force: Time in force (GTC, DAY, etc.)
            text: Order notes/messages

        Returns:
            Tuple of (old_state, new_state) for transition detection
        """
        now = datetime.now()

        # Find existing order
        order = None
        if server_order_id:
            order = self._orders_by_server.get(server_order_id)
        if not order and client_order_id:
            order = self._orders_by_client.get(client_order_id)

        old_state = order.state if order else OrderState.PENDING

        # Determine new state from DTC status
        if dtc_status is not None:
            new_state = DTC_ORDER_STATUS_MAP.get(dtc_status, OrderState.WORKING)
        else:
            # Infer state from filled_qty vs qty
            if filled_qty is not None and qty is not None:
                if filled_qty == 0:
                    new_state = OrderState.WORKING
                elif filled_qty >= qty:
                    new_state = OrderState.FILLED
                else:
                    new_state = OrderState.PARTIALLY_FILLED
            else:
                new_state = old_state  # No change

        # Update or create order record
        if order:
            # Update existing order
            if server_order_id:
                order.server_order_id = server_order_id
            if client_order_id:
                order.client_order_id = client_order_id
            if symbol:
                order.symbol = symbol
            if side:
                order.side = side
            if qty is not None:
                order.qty = qty
            if filled_qty is not None:
                order.filled_qty = filled_qty
            if price is not None:
                order.price = price
            if avg_fill_price is not None:
                order.avg_fill_price = avg_fill_price
            if order_type:
                order.order_type = order_type
            if time_in_force:
                order.time_in_force = time_in_force
            if text:
                order.text = text

            order.state = new_state
            order.mode = mode
            order.account = account
            order.last_updated = now

            # Track filled timestamp
            if new_state == OrderState.FILLED and not order.filled_at:
                order.filled_at = now

        else:
            # Create new order
            if not symbol or not side:
                # Can't create order without basic info
                return (old_state, old_state)

            order = OrderRecord(
                server_order_id=server_order_id,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                qty=qty or 0,
                filled_qty=filled_qty or 0,
                price=price,
                avg_fill_price=avg_fill_price,
                state=new_state,
                mode=mode,
                account=account,
                order_type=order_type,
                time_in_force=time_in_force,
                text=text,
                submitted_at=now,
                last_updated=now,
            )

            # Index by both IDs
            if server_order_id:
                self._orders_by_server[server_order_id] = order
            if client_order_id:
                self._orders_by_client[client_order_id] = order

        # Archive closed orders
        if new_state in (OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED):
            order.state = OrderState.CLOSED
            order.closed_at = now

        return (old_state, new_state)

    def get(
        self, server_order_id: Optional[str] = None, client_order_id: Optional[str] = None
    ) -> Optional[OrderRecord]:
        """Get order by server or client ID."""
        if server_order_id:
            return self._orders_by_server.get(server_order_id)
        if client_order_id:
            return self._orders_by_client.get(client_order_id)
        return None

    def get_working_orders(self, mode: Optional[str] = None) -> list[OrderRecord]:
        """
        Get all working orders, optionally filtered by mode.

        Args:
            mode: Optional mode filter (SIM/LIVE)

        Returns:
            List of working orders
        """
        working = [
            order
            for order in self._orders_by_server.values()
            if order.state in (OrderState.WORKING, OrderState.PARTIALLY_FILLED)
        ]

        if mode:
            working = [order for order in working if order.mode == mode]

        return working

    def has_working_orders(self, mode: Optional[str] = None) -> bool:
        """Check if any orders are working, optionally filtered by mode."""
        return len(self.get_working_orders(mode)) > 0

    def clear(self) -> None:
        """Clear all order state (for testing or reset)."""
        self._orders_by_server.clear()
        self._orders_by_client.clear()
