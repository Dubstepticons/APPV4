"""
Trade State Machine - Pure Business Logic

Extracted from Panel2 to follow Single Responsibility Principle.
Manages trade lifecycle states and transitions without UI dependencies.

State Flow:
    NO_POSITION → ENTERING → IN_POSITION → EXITING → CLOSED
                     ↑                          ↓
                     └──────── (re-entry) ──────┘

Thread Safety: Instance is NOT thread-safe. Use one instance per thread.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
from decimal import Decimal


class TradeState(Enum):
    """Trade lifecycle states"""
    NO_POSITION = auto()   # Flat, no active position
    ENTERING = auto()      # Order submitted, waiting for fill
    IN_POSITION = auto()   # Position open, tracking P&L
    EXITING = auto()       # Exit order submitted
    CLOSED = auto()        # Position closed, calculating final stats


class TradeEvent(Enum):
    """Events that trigger state transitions"""
    ORDER_SUBMITTED = auto()
    ORDER_FILLED = auto()
    POSITION_CONFIRMED = auto()
    EXIT_ORDER_SUBMITTED = auto()
    EXIT_FILLED = auto()
    POSITION_FLAT = auto()
    CANCEL_ORDER = auto()
    ERROR_OCCURRED = auto()


@dataclass
class Position:
    """
    Position data snapshot.

    Immutable record of position state at a point in time.
    All monetary values use Decimal for precision.
    """
    symbol: str
    qty: int  # Positive for long, negative for short
    entry_price: Decimal
    entry_time: datetime
    current_price: Optional[Decimal] = None
    mode: str = "SIM"  # SIM/LIVE/DEBUG
    account: str = "default"

    # Real-time metrics
    unrealized_pnl: Optional[Decimal] = None
    mae: Optional[Decimal] = None  # Maximum adverse excursion
    mfe: Optional[Decimal] = None  # Maximum favorable excursion

    # Order tracking
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None

    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.qty > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.qty < 0

    @property
    def side(self) -> str:
        """Get position side as string"""
        if self.qty > 0:
            return "LONG"
        elif self.qty < 0:
            return "SHORT"
        return "FLAT"


@dataclass
class ClosedTrade:
    """
    Completed trade record with final statistics.

    Immutable record created when position closes.
    """
    symbol: str
    side: str  # "LONG" or "SHORT"
    qty: int
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    realized_pnl: Decimal
    mode: str
    account: str

    # Advanced metrics
    mae: Optional[Decimal] = None
    mfe: Optional[Decimal] = None
    efficiency: Optional[float] = None  # realized_pnl / mfe
    r_multiple: Optional[float] = None
    commissions: Optional[Decimal] = None

    # Metadata
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None


StateChangeCallback = Callable[[TradeState, TradeState], None]
PositionUpdateCallback = Callable[[Position], None]
TradeClosedCallback = Callable[[ClosedTrade], None]


class TradeStateMachine:
    """
    Finite state machine for trade lifecycle management.

    Handles state transitions, validates events, and triggers callbacks.
    Pure business logic - no UI or database dependencies.

    Usage:
        >>> fsm = TradeStateMachine()
        >>> fsm.on_state_change(lambda old, new: print(f"{old} -> {new}"))
        >>> fsm.transition(TradeEvent.ORDER_SUBMITTED, order_id="123")
        NO_POSITION -> ENTERING
    """

    def __init__(self):
        self.state = TradeState.NO_POSITION
        self.position: Optional[Position] = None
        self.closed_trade: Optional[ClosedTrade] = None

        # Callbacks
        self._state_change_callbacks: list[StateChangeCallback] = []
        self._position_update_callbacks: list[PositionUpdateCallback] = []
        self._trade_closed_callbacks: list[TradeClosedCallback] = []

        # State transition rules
        self._transitions = {
            TradeState.NO_POSITION: {
                TradeEvent.ORDER_SUBMITTED: TradeState.ENTERING
            },
            TradeState.ENTERING: {
                TradeEvent.ORDER_FILLED: TradeState.IN_POSITION,
                TradeEvent.CANCEL_ORDER: TradeState.NO_POSITION,
                TradeEvent.ERROR_OCCURRED: TradeState.NO_POSITION
            },
            TradeState.IN_POSITION: {
                TradeEvent.EXIT_ORDER_SUBMITTED: TradeState.EXITING,
                TradeEvent.POSITION_FLAT: TradeState.CLOSED  # Emergency exit
            },
            TradeState.EXITING: {
                TradeEvent.EXIT_FILLED: TradeState.CLOSED,
                TradeEvent.POSITION_FLAT: TradeState.CLOSED,
                TradeEvent.ERROR_OCCURRED: TradeState.IN_POSITION  # Retry
            },
            TradeState.CLOSED: {
                TradeEvent.ORDER_SUBMITTED: TradeState.ENTERING  # New trade
            }
        }

    def transition(self, event: TradeEvent, **kwargs) -> bool:
        """
        Attempt state transition based on event.

        Args:
            event: Event that triggers transition
            **kwargs: Event-specific data (position info, prices, etc.)

        Returns:
            True if transition succeeded, False if invalid

        Raises:
            ValueError: If required data missing for transition
        """
        old_state = self.state

        # Get next state from transition table
        next_state = self._transitions.get(self.state, {}).get(event)

        if next_state is None:
            # Invalid transition
            return False

        # Execute transition-specific logic
        self._execute_transition(event, next_state, **kwargs)

        # Update state
        self.state = next_state

        # Notify observers
        self._notify_state_change(old_state, next_state)

        return True

    def _execute_transition(self, event: TradeEvent, next_state: TradeState, **kwargs) -> None:
        """Execute side effects for specific transitions"""

        if event == TradeEvent.ORDER_SUBMITTED:
            # Entering position
            self.position = None  # Clear old position
            self.closed_trade = None

        elif event == TradeEvent.ORDER_FILLED:
            # Position confirmed
            self.position = Position(
                symbol=kwargs.get('symbol', 'UNKNOWN'),
                qty=kwargs.get('qty', 0),
                entry_price=Decimal(str(kwargs.get('entry_price', 0))),
                entry_time=kwargs.get('entry_time', datetime.now()),
                mode=kwargs.get('mode', 'SIM'),
                account=kwargs.get('account', 'default'),
                entry_order_id=kwargs.get('order_id')
            )
            self._notify_position_update(self.position)

        elif event == TradeEvent.POSITION_FLAT:
            # Position closed
            if self.position:
                self.closed_trade = ClosedTrade(
                    symbol=self.position.symbol,
                    side=self.position.side,
                    qty=abs(self.position.qty),
                    entry_price=self.position.entry_price,
                    exit_price=Decimal(str(kwargs.get('exit_price', 0))),
                    entry_time=self.position.entry_time,
                    exit_time=kwargs.get('exit_time', datetime.now()),
                    realized_pnl=Decimal(str(kwargs.get('realized_pnl', 0))),
                    mode=self.position.mode,
                    account=self.position.account,
                    mae=self.position.mae,
                    mfe=self.position.mfe,
                    efficiency=kwargs.get('efficiency'),
                    r_multiple=kwargs.get('r_multiple'),
                    commissions=kwargs.get('commissions'),
                    entry_order_id=self.position.entry_order_id,
                    exit_order_id=self.position.exit_order_id
                )
                self._notify_trade_closed(self.closed_trade)

    def update_position_metrics(
        self,
        current_price: Decimal,
        unrealized_pnl: Decimal,
        mae: Optional[Decimal] = None,
        mfe: Optional[Decimal] = None
    ) -> None:
        """
        Update real-time position metrics (called on every price tick).

        Args:
            current_price: Current market price
            unrealized_pnl: Current unrealized P&L
            mae: Maximum adverse excursion (worst drawdown)
            mfe: Maximum favorable excursion (best profit)
        """
        if self.state != TradeState.IN_POSITION or not self.position:
            return

        self.position.current_price = current_price
        self.position.unrealized_pnl = unrealized_pnl

        if mae is not None:
            self.position.mae = mae
        if mfe is not None:
            self.position.mfe = mfe

        self._notify_position_update(self.position)

    def can_enter_trade(self) -> bool:
        """Check if new trade entry is allowed"""
        return self.state in (TradeState.NO_POSITION, TradeState.CLOSED)

    def has_active_position(self) -> bool:
        """Check if there's an active position"""
        return self.state == TradeState.IN_POSITION

    def is_transitioning(self) -> bool:
        """Check if in transient state (entering/exiting)"""
        return self.state in (TradeState.ENTERING, TradeState.EXITING)

    # Callback registration
    def on_state_change(self, callback: StateChangeCallback) -> None:
        """Register callback for state changes"""
        self._state_change_callbacks.append(callback)

    def on_position_update(self, callback: PositionUpdateCallback) -> None:
        """Register callback for position metric updates"""
        self._position_update_callbacks.append(callback)

    def on_trade_closed(self, callback: TradeClosedCallback) -> None:
        """Register callback for completed trades"""
        self._trade_closed_callbacks.append(callback)

    # Callback triggers
    def _notify_state_change(self, old_state: TradeState, new_state: TradeState) -> None:
        """Trigger state change callbacks"""
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                # Don't let callback errors crash state machine
                print(f"[FSM] Callback error: {e}")

    def _notify_position_update(self, position: Position) -> None:
        """Trigger position update callbacks"""
        for callback in self._position_update_callbacks:
            try:
                callback(position)
            except Exception:
                pass

    def _notify_trade_closed(self, trade: ClosedTrade) -> None:
        """Trigger trade closed callbacks"""
        for callback in self._trade_closed_callbacks:
            try:
                callback(trade)
            except Exception:
                pass

    def reset(self) -> None:
        """Reset state machine to initial state"""
        self.state = TradeState.NO_POSITION
        self.position = None
        self.closed_trade = None

    def __repr__(self) -> str:
        return f"TradeStateMachine(state={self.state.name}, has_position={self.position is not None})"
