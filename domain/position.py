"""
domain/position.py

Position domain model - pure business logic for position state and calculations.

PRIORITY #3: Extract position logic from Panel2 into clean domain model.

This module provides a Position class that encapsulates all position state
and behavior, separating business logic from UI concerns.

Key Responsibilities:
- Position state management (qty, entry price, side, times)
- P&L calculations (unrealized, realized, MAE, MFE)
- Bracket order tracking (targets, stops)
- Entry snapshots (VWAP, delta, POC)
- State validation and invariants

Thread Safety: Not thread-safe - caller must handle synchronization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from services.trade_constants import DOLLARS_PER_POINT


@dataclass
class Position:
    """
    Position domain model representing an open trading position.

    Immutable-style design: Methods return new Position instances rather
    than mutating state (except for trade extremes which update in place).

    Attributes:
        symbol: Trading symbol (e.g., "MES", "MNQ")
        qty: Signed quantity (positive=long, negative=short, 0=flat)
        entry_price: Average entry price
        entry_time: Entry timestamp (UTC)
        mode: Trading mode ("SIM", "LIVE", "DEBUG")
        account: Account identifier

        # Bracket orders
        target_price: Target price for profit exit
        stop_price: Stop price for loss exit

        # Entry snapshots (static once set)
        entry_vwap: VWAP at entry
        entry_cum_delta: Cumulative delta at entry
        entry_poc: Point of control at entry

        # Trade extremes (updated continuously)
        trade_min_price: Lowest price reached during trade
        trade_max_price: Highest price reached during trade
    """

    # Core position
    symbol: str
    qty: int  # Signed: positive=long, negative=short
    entry_price: float
    entry_time: datetime
    mode: str
    account: str

    # Bracket orders
    target_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Entry snapshots
    entry_vwap: Optional[float] = None
    entry_cum_delta: Optional[float] = None
    entry_poc: Optional[float] = None

    # Trade extremes (mutable - updated in place)
    trade_min_price: Optional[float] = field(default=None, init=False)
    trade_max_price: Optional[float] = field(default=None, init=False)

    def __post_init__(self):
        """Initialize trade extremes to entry price."""
        if self.trade_min_price is None:
            self.trade_min_price = self.entry_price
        if self.trade_max_price is None:
            self.trade_max_price = self.entry_price

    # ===== PROPERTIES =====

    @property
    def side(self) -> str:
        """Position side: 'LONG', 'SHORT', or 'FLAT'."""
        if self.qty > 0:
            return "LONG"
        elif self.qty < 0:
            return "SHORT"
        else:
            return "FLAT"

    @property
    def is_long(self) -> Optional[bool]:
        """True if long, False if short, None if flat."""
        if self.qty > 0:
            return True
        elif self.qty < 0:
            return False
        else:
            return None

    @property
    def qty_abs(self) -> int:
        """Absolute quantity (unsigned)."""
        return abs(self.qty)

    @property
    def is_flat(self) -> bool:
        """True if no position open (qty == 0)."""
        return self.qty == 0

    @property
    def duration_seconds(self) -> Optional[float]:
        """Time in position (seconds) from entry to now."""
        if self.is_flat:
            return None
        now = datetime.now(timezone.utc)
        return (now - self.entry_time).total_seconds()

    # ===== P&L CALCULATIONS =====

    def unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L at current price.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L in dollars (positive=profit, negative=loss)
        """
        if self.is_flat:
            return 0.0

        price_diff = current_price - self.entry_price
        pnl = price_diff * self.qty_abs * DOLLARS_PER_POINT

        # Adjust sign for short positions
        if self.qty < 0:
            pnl = -pnl

        return pnl

    def realized_pnl(self, exit_price: float) -> float:
        """
        Calculate realized P&L at exit price.

        Args:
            exit_price: Exit price

        Returns:
            Realized P&L in dollars
        """
        return self.unrealized_pnl(exit_price)

    def mae(self) -> Optional[float]:
        """
        Maximum Adverse Excursion: Worst unrealized loss during trade.

        Returns:
            MAE in dollars (negative value), or None if no extremes tracked
        """
        if self.trade_min_price is None or self.trade_max_price is None:
            return None

        if self.side == "LONG":
            # For LONG: MAE is entry - min_price (worst drawdown)
            return (self.trade_min_price - self.entry_price) * DOLLARS_PER_POINT * self.qty_abs
        elif self.side == "SHORT":
            # For SHORT: MAE is max_price - entry (worst run-up)
            return (self.entry_price - self.trade_max_price) * DOLLARS_PER_POINT * self.qty_abs
        else:
            return None

    def mfe(self) -> Optional[float]:
        """
        Maximum Favorable Excursion: Best unrealized profit during trade.

        Returns:
            MFE in dollars (positive value), or None if no extremes tracked
        """
        if self.trade_min_price is None or self.trade_max_price is None:
            return None

        if self.side == "LONG":
            # For LONG: MFE is max_price - entry (best run-up)
            return (self.trade_max_price - self.entry_price) * DOLLARS_PER_POINT * self.qty_abs
        elif self.side == "SHORT":
            # For SHORT: MFE is entry - min_price (best drawdown)
            return (self.entry_price - self.trade_min_price) * DOLLARS_PER_POINT * self.qty_abs
        else:
            return None

    def efficiency(self, current_price: float) -> Optional[float]:
        """
        Trade efficiency: realized_pnl / MFE.

        Measures what % of peak profit was captured.

        Args:
            current_price: Current or exit price

        Returns:
            Efficiency ratio [0, 1.5], or None if MFE unavailable
        """
        mfe_value = self.mfe()
        if mfe_value is None or mfe_value <= 0:
            return None

        realized = self.unrealized_pnl(current_price)
        eff = realized / mfe_value

        # Clamp to [0, 1.5] (can exceed 1 if exit > MFE peak)
        return max(0.0, min(1.5, eff))

    def r_multiple(self, current_price: float) -> Optional[float]:
        """
        R-multiple: realized_pnl / initial_risk.

        Measures return in terms of initial risk units.

        Args:
            current_price: Current or exit price

        Returns:
            R-multiple, or None if no stop price set
        """
        if self.stop_price is None:
            return None

        # Risk = distance from entry to stop (in dollars)
        stop_distance = abs(self.entry_price - self.stop_price)
        risk = stop_distance * DOLLARS_PER_POINT * self.qty_abs

        if risk <= 0:
            return None

        realized = self.unrealized_pnl(current_price)
        return realized / risk

    # ===== STATE UPDATES =====

    def update_extremes(self, current_price: float) -> None:
        """
        Update trade min/max prices (mutates in place).

        Called periodically (e.g., every 500ms) to track MAE/MFE.

        Args:
            current_price: Current market price
        """
        if self.trade_min_price is None or current_price < self.trade_min_price:
            self.trade_min_price = current_price

        if self.trade_max_price is None or current_price > self.trade_max_price:
            self.trade_max_price = current_price

    def with_bracket(
        self,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Position:
        """
        Return new Position with updated bracket orders.

        Args:
            target_price: New target price (None to clear)
            stop_price: New stop price (None to clear)

        Returns:
            New Position instance with updated brackets
        """
        return Position(
            symbol=self.symbol,
            qty=self.qty,
            entry_price=self.entry_price,
            entry_time=self.entry_time,
            mode=self.mode,
            account=self.account,
            target_price=target_price,
            stop_price=stop_price,
            entry_vwap=self.entry_vwap,
            entry_cum_delta=self.entry_cum_delta,
            entry_poc=self.entry_poc,
        )

    # ===== FACTORY METHODS =====

    @classmethod
    def open(
        cls,
        symbol: str,
        qty: int,
        entry_price: float,
        mode: str,
        account: str,
        entry_time: Optional[datetime] = None,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        entry_vwap: Optional[float] = None,
        entry_cum_delta: Optional[float] = None,
        entry_poc: Optional[float] = None,
    ) -> Position:
        """
        Open a new position.

        Args:
            symbol: Trading symbol
            qty: Signed quantity (positive=long, negative=short)
            entry_price: Entry price
            mode: Trading mode
            account: Account identifier
            entry_time: Entry timestamp (defaults to now UTC)
            target_price: Bracket target
            stop_price: Bracket stop
            entry_vwap: VWAP at entry
            entry_cum_delta: Cumulative delta at entry
            entry_poc: POC at entry

        Returns:
            New Position instance
        """
        if entry_time is None:
            entry_time = datetime.now(timezone.utc)

        return cls(
            symbol=symbol,
            qty=qty,
            entry_price=entry_price,
            entry_time=entry_time,
            mode=mode,
            account=account,
            target_price=target_price,
            stop_price=stop_price,
            entry_vwap=entry_vwap,
            entry_cum_delta=entry_cum_delta,
            entry_poc=entry_poc,
        )

    @classmethod
    def flat(cls, mode: str = "SIM", account: str = "") -> Position:
        """
        Create flat position (no position open).

        Args:
            mode: Trading mode
            account: Account identifier

        Returns:
            Flat position instance
        """
        return cls(
            symbol="",
            qty=0,
            entry_price=0.0,
            entry_time=datetime.now(timezone.utc),
            mode=mode,
            account=account,
        )

    # ===== SERIALIZATION =====

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "mode": self.mode,
            "account": self.account,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "entry_vwap": self.entry_vwap,
            "entry_cum_delta": self.entry_cum_delta,
            "entry_poc": self.entry_poc,
            "trade_min_price": self.trade_min_price,
            "trade_max_price": self.trade_max_price,
            "side": self.side,
            "is_long": self.is_long,
            "qty_abs": self.qty_abs,
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        if self.is_flat:
            return f"Position(FLAT, mode={self.mode})"
        return (
            f"Position({self.side} {self.qty_abs} {self.symbol} @ {self.entry_price}, "
            f"mode={self.mode})"
        )
