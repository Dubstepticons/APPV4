"""
panels/panel2/position_state.py

Immutable position state snapshots for Panel2.

This module provides the PositionState dataclass - an immutable snapshot
of all position-related state at a point in time. Using immutable state
enables:
- Thread-safe sharing between modules
- Easy serialization/deserialization
- Clear state contracts
- No hidden mutations

Architecture:
- Frozen dataclass (immutable by design)
- No business logic (pure data)
- Helper methods for state queries only
- Used by all other Panel2 modules

Usage:
    # Create flat state
    state = PositionState.flat()

    # Create position state
    state = PositionState(
        entry_qty=1,
        entry_price=6750.0,
        is_long=True,
        symbol="MES",
        entry_time_epoch=1699999999,
        last_price=6755.0,
        ...
    )

    # Update state (creates new instance)
    new_state = state.with_price(6760.0)

    # Query state
    if state.is_flat():
        print("No position")
    else:
        print(f"P&L: {state.current_pnl()}")
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from services.trade_constants import DOLLARS_PER_POINT


@dataclass(frozen=True)
class PositionState:
    """
    Immutable snapshot of position state.

    This dataclass captures all state needed to render Panel2 at a
    point in time. Being frozen (immutable) makes it thread-safe and
    prevents accidental mutations.

    Attributes are grouped into logical categories for clarity.
    """

    # =========================================================================
    # POSITION CORE
    # =========================================================================
    entry_qty: float = 0.0  # Positive = long, negative = short, 0 = flat
    entry_price: float = 0.0  # Entry price
    is_long: Optional[bool] = None  # True = long, False = short, None = flat
    symbol: str = "ES"  # Trading symbol
    entry_time_epoch: int = 0  # Entry time (Unix timestamp)

    # =========================================================================
    # TARGETS & STOPS
    # =========================================================================
    target_price: Optional[float] = None  # Target price (if set)
    stop_price: Optional[float] = None  # Stop loss price (if set)

    # =========================================================================
    # CURRENT MARKET DATA
    # =========================================================================
    last_price: float = 0.0  # Current market price
    session_high: float = 0.0  # Session high
    session_low: float = 0.0  # Session low
    vwap: float = 0.0  # Volume-weighted average price
    cum_delta: float = 0.0  # Cumulative delta
    poc: float = 0.0  # Point of control

    # =========================================================================
    # TRADE EXTREMES (for MAE/MFE)
    # =========================================================================
    trade_min_price: float = 0.0  # Lowest price during trade
    trade_max_price: float = 0.0  # Highest price during trade

    # =========================================================================
    # ENTRY SNAPSHOTS (captured at entry)
    # =========================================================================
    entry_vwap: Optional[float] = None  # VWAP at entry
    entry_cum_delta: Optional[float] = None  # Cum delta at entry
    entry_poc: Optional[float] = None  # POC at entry

    # =========================================================================
    # HEAT TRACKING (UI-specific)
    # =========================================================================
    heat_start_epoch: Optional[int] = None  # When drawdown started (Unix timestamp)

    # =========================================================================
    # MODE & ACCOUNT (for scoping)
    # =========================================================================
    current_mode: str = "SIM"  # "SIM", "LIVE", or "DEBUG"
    current_account: str = ""  # Account identifier

    # =========================================================================
    # QUERY METHODS (read-only, no mutations)
    # =========================================================================

    def is_flat(self) -> bool:
        """Return True if no position (flat)."""
        return self.entry_qty == 0.0

    def has_position(self) -> bool:
        """Return True if position is open."""
        return self.entry_qty != 0.0

    def current_pnl(self) -> float:
        """
        Calculate current unrealized P&L.

        Returns:
            P&L in dollars (positive = profit, negative = loss)
        """
        if self.is_flat():
            return 0.0

        # Calculate P&L based on direction
        direction = 1 if self.is_long else -1
        pnl_points = direction * (self.last_price - self.entry_price)
        pnl_dollars = pnl_points * abs(self.entry_qty) * DOLLARS_PER_POINT

        return pnl_dollars

    def mae(self) -> Optional[float]:
        """
        Calculate Maximum Adverse Excursion.

        Returns:
            MAE in dollars (always negative or zero), or None if no position
        """
        if self.is_flat():
            return None

        if self.is_long:
            # For long: worst case is trade_min_price
            adverse_price = self.trade_min_price
        else:
            # For short: worst case is trade_max_price
            adverse_price = self.trade_max_price

        # Calculate worst P&L
        direction = 1 if self.is_long else -1
        mae_points = direction * (adverse_price - self.entry_price)
        mae_dollars = mae_points * abs(self.entry_qty) * DOLLARS_PER_POINT

        # MAE should be negative or zero
        return min(0.0, mae_dollars)

    def mfe(self) -> Optional[float]:
        """
        Calculate Maximum Favorable Excursion.

        Returns:
            MFE in dollars (always positive or zero), or None if no position
        """
        if self.is_flat():
            return None

        if self.is_long:
            # For long: best case is trade_max_price
            favorable_price = self.trade_max_price
        else:
            # For short: best case is trade_min_price
            favorable_price = self.trade_min_price

        # Calculate best P&L
        direction = 1 if self.is_long else -1
        mfe_points = direction * (favorable_price - self.entry_price)
        mfe_dollars = mfe_points * abs(self.entry_qty) * DOLLARS_PER_POINT

        # MFE should be positive or zero
        return max(0.0, mfe_dollars)

    def risk_amount(self) -> Optional[float]:
        """
        Calculate risk amount (distance to stop).

        Returns:
            Risk in dollars, or None if no stop set
        """
        if self.is_flat() or self.stop_price is None:
            return None

        direction = 1 if self.is_long else -1
        risk_points = direction * (self.entry_price - self.stop_price)
        risk_dollars = risk_points * abs(self.entry_qty) * DOLLARS_PER_POINT

        return abs(risk_dollars)

    def reward_amount(self) -> Optional[float]:
        """
        Calculate reward amount (distance to target).

        Returns:
            Reward in dollars, or None if no target set
        """
        if self.is_flat() or self.target_price is None:
            return None

        direction = 1 if self.is_long else -1
        reward_points = direction * (self.target_price - self.entry_price)
        reward_dollars = reward_points * abs(self.entry_qty) * DOLLARS_PER_POINT

        return abs(reward_dollars)

    def r_multiple(self) -> Optional[float]:
        """
        Calculate R-multiple (current P&L / risk).

        Returns:
            R-multiple (e.g., 2.5 = 2.5R), or None if no risk defined
        """
        risk = self.risk_amount()
        if risk is None or risk == 0:
            return None

        current_pnl = self.current_pnl()
        return current_pnl / risk

    def efficiency(self) -> Optional[float]:
        """
        Calculate efficiency (current P&L / MFE).

        Returns:
            Efficiency as percentage (0-100), or None if no MFE
        """
        mfe = self.mfe()
        if mfe is None or mfe == 0:
            return None

        current_pnl = self.current_pnl()
        efficiency_pct = (current_pnl / mfe) * 100.0

        return efficiency_pct

    # =========================================================================
    # IMMUTABLE UPDATE METHODS (return new instances)
    # =========================================================================

    def with_price(self, last_price: float) -> PositionState:
        """
        Update last_price (immutable - returns new instance).

        Also updates trade extremes (min/max).
        """
        new_min = min(self.trade_min_price, last_price) if self.has_position() else last_price
        new_max = max(self.trade_max_price, last_price) if self.has_position() else last_price

        return replace(
            self,
            last_price=last_price,
            trade_min_price=new_min,
            trade_max_price=new_max
        )

    def with_market_data(
        self,
        last_price: float,
        session_high: float,
        session_low: float,
        vwap: float,
        cum_delta: float,
        poc: float
    ) -> PositionState:
        """
        Update all market data fields (immutable - returns new instance).
        """
        # Update price and extremes
        new_state = self.with_price(last_price)

        # Update other market data
        return replace(
            new_state,
            session_high=session_high,
            session_low=session_low,
            vwap=vwap,
            cum_delta=cum_delta,
            poc=poc
        )

    def with_targets(
        self,
        target_price: Optional[float],
        stop_price: Optional[float]
    ) -> PositionState:
        """
        Update target and stop prices (immutable - returns new instance).
        """
        return replace(
            self,
            target_price=target_price,
            stop_price=stop_price
        )

    def with_heat(self, heat_start_epoch: Optional[int]) -> PositionState:
        """
        Update heat tracking (immutable - returns new instance).
        """
        return replace(self, heat_start_epoch=heat_start_epoch)

    # =========================================================================
    # FACTORY METHODS
    # =========================================================================

    @classmethod
    def flat(cls, mode: str = "SIM", account: str = "") -> PositionState:
        """
        Create a flat (no position) state.

        Args:
            mode: Trading mode ("SIM", "LIVE", "DEBUG")
            account: Account identifier

        Returns:
            PositionState with no position
        """
        return cls(
            entry_qty=0.0,
            entry_price=0.0,
            is_long=None,
            current_mode=mode,
            current_account=account
        )

    @classmethod
    def from_position_domain(cls, position, market_data: dict) -> PositionState:
        """
        Create PositionState from Position domain model.

        Args:
            position: Position domain object
            market_data: Dict with market data fields

        Returns:
            PositionState instance
        """
        return cls(
            # Position core
            entry_qty=position.qty,
            entry_price=position.entry_price,
            is_long=position.is_long,
            symbol=position.symbol,
            entry_time_epoch=int(position.entry_time.timestamp()) if position.entry_time else 0,

            # Targets
            target_price=position.target_price,
            stop_price=position.stop_price,

            # Market data
            last_price=market_data.get("last_price", 0.0),
            session_high=market_data.get("session_high", 0.0),
            session_low=market_data.get("session_low", 0.0),
            vwap=market_data.get("vwap", 0.0),
            cum_delta=market_data.get("cum_delta", 0.0),
            poc=market_data.get("poc", 0.0),

            # Trade extremes
            trade_min_price=position.min_price,
            trade_max_price=position.max_price,

            # Entry snapshots
            entry_vwap=position.entry_vwap,
            entry_cum_delta=position.entry_cum_delta,
            entry_poc=position.entry_poc,

            # Mode/account
            current_mode=position.mode,
            current_account=position.account
        )

    def to_dict(self) -> dict:
        """
        Convert to dict for serialization.

        Returns:
            Dict representation of state
        """
        return {
            "entry_qty": self.entry_qty,
            "entry_price": self.entry_price,
            "is_long": self.is_long,
            "symbol": self.symbol,
            "entry_time_epoch": self.entry_time_epoch,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "last_price": self.last_price,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "vwap": self.vwap,
            "cum_delta": self.cum_delta,
            "poc": self.poc,
            "trade_min_price": self.trade_min_price,
            "trade_max_price": self.trade_max_price,
            "entry_vwap": self.entry_vwap,
            "entry_cum_delta": self.entry_cum_delta,
            "entry_poc": self.entry_poc,
            "heat_start_epoch": self.heat_start_epoch,
            "current_mode": self.current_mode,
            "current_account": self.current_account,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PositionState:
        """
        Create PositionState from dict.

        Args:
            data: Dict representation

        Returns:
            PositionState instance
        """
        return cls(
            entry_qty=data.get("entry_qty", 0.0),
            entry_price=data.get("entry_price", 0.0),
            is_long=data.get("is_long"),
            symbol=data.get("symbol", "ES"),
            entry_time_epoch=data.get("entry_time_epoch", 0),
            target_price=data.get("target_price"),
            stop_price=data.get("stop_price"),
            last_price=data.get("last_price", 0.0),
            session_high=data.get("session_high", 0.0),
            session_low=data.get("session_low", 0.0),
            vwap=data.get("vwap", 0.0),
            cum_delta=data.get("cum_delta", 0.0),
            poc=data.get("poc", 0.0),
            trade_min_price=data.get("trade_min_price", 0.0),
            trade_max_price=data.get("trade_max_price", 0.0),
            entry_vwap=data.get("entry_vwap"),
            entry_cum_delta=data.get("entry_cum_delta"),
            entry_poc=data.get("entry_poc"),
            heat_start_epoch=data.get("heat_start_epoch"),
            current_mode=data.get("current_mode", "SIM"),
            current_account=data.get("current_account", ""),
        )
