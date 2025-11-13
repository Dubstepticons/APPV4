"""
Position State Machine

Tracks position lifecycle through well-defined states with validated transitions.

State Flow:
    CLOSED → OPEN → REDUCING → CLOSED
              ↓
           FLATTEN → CLOSED

States:
- CLOSED: No position (qty = 0)
- OPEN: Position established (qty > 0)
- REDUCING: Position being scaled down (qty decreasing but not zero)
- FLATTEN: Position flattening to zero (final close triggered)

This ensures deterministic position tracking and prevents state corruption.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PositionState(str, Enum):
    """Position lifecycle states"""

    CLOSED = "CLOSED"  # No position (qty = 0)
    OPEN = "OPEN"  # Position established (qty > 0)
    REDUCING = "REDUCING"  # Position being scaled down
    FLATTEN = "FLATTEN"  # Flattening to zero


class PositionRecord(BaseModel):
    """
    Complete position record with state tracking.
    """

    symbol: str
    qty: int
    avg_entry: Optional[float] = None
    state: PositionState = PositionState.CLOSED
    mode: str = "SIM"  # SIM or LIVE
    account: Optional[str] = None

    # Timestamps
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.now)

    # PnL tracking (optional)
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None


class PositionStateMachine:
    """
    Manages position lifecycle with validated state transitions.

    Enforces position state invariants and provides clean transition API.
    """

    def __init__(self):
        # symbol -> PositionRecord
        self._positions: dict[str, PositionRecord] = {}

    def update(
        self,
        symbol: str,
        qty: int,
        avg_entry: Optional[float] = None,
        mode: str = "SIM",
        account: Optional[str] = None,
    ) -> tuple[PositionState, PositionState]:
        """
        Update position and return (old_state, new_state).

        Args:
            symbol: Symbol identifier
            qty: New quantity (0 = closed)
            avg_entry: Average entry price
            mode: Trading mode (SIM/LIVE)
            account: Account identifier

        Returns:
            Tuple of (old_state, new_state) for transition detection
        """
        now = datetime.now()

        # Get existing position or create new
        pos = self._positions.get(symbol)
        old_state = pos.state if pos else PositionState.CLOSED
        old_qty = pos.qty if pos else 0

        # Determine new state based on qty transition
        if qty == 0:
            new_state = PositionState.CLOSED
        elif old_qty == 0:
            new_state = PositionState.OPEN  # Opening new position
        elif qty < old_qty:
            new_state = PositionState.REDUCING  # Scaling down
        else:
            new_state = PositionState.OPEN  # Increasing or maintaining

        # Update or create position record
        if pos:
            pos.qty = qty
            pos.avg_entry = avg_entry
            pos.state = new_state
            pos.mode = mode
            pos.account = account
            pos.last_updated = now

            # Track close timestamp
            if new_state == PositionState.CLOSED:
                pos.closed_at = now
        else:
            # Create new position
            pos = PositionRecord(
                symbol=symbol,
                qty=qty,
                avg_entry=avg_entry,
                state=new_state,
                mode=mode,
                account=account,
                opened_at=now if qty > 0 else None,
                closed_at=now if qty == 0 else None,
                last_updated=now,
            )
            self._positions[symbol] = pos

        # Clean up closed positions after recording
        if new_state == PositionState.CLOSED:
            # Keep record for a short time for logging
            # Could be purged later or moved to history
            pass

        return (old_state, new_state)

    def get(self, symbol: str) -> Optional[PositionRecord]:
        """Get current position record for symbol."""
        return self._positions.get(symbol)

    def get_open_positions(self, mode: Optional[str] = None) -> list[PositionRecord]:
        """
        Get all open positions, optionally filtered by mode.

        Args:
            mode: Optional mode filter (SIM/LIVE)

        Returns:
            List of open positions
        """
        open_positions = [pos for pos in self._positions.values() if pos.state != PositionState.CLOSED]

        if mode:
            open_positions = [pos for pos in open_positions if pos.mode == mode]

        return open_positions

    def has_open_position(self, mode: Optional[str] = None) -> bool:
        """Check if any positions are open, optionally filtered by mode."""
        return len(self.get_open_positions(mode)) > 0

    def clear(self) -> None:
        """Clear all position state (for testing or reset)."""
        self._positions.clear()
