"""
panels/panel2/metrics_calculator.py

Pure P&L calculation functions for Panel2.

This module provides stateless calculation functions for all trading metrics
displayed in Panel2. All functions are pure (no side effects) and take
PositionState as input.

Architecture:
- Pure functions (stateless, no side effects)
- No dependencies on UI or database
- Easy to test in isolation
- Can be cached/memoized for performance

Usage:
    from panels.panel2.position_state import PositionState
    from panels.panel2.metrics_calculator import MetricsCalculator

    state = PositionState(entry_qty=1, entry_price=6750.0, ...)
    calculator = MetricsCalculator()

    metrics = calculator.calculate_all(state)
    print(f"P&L: {metrics['unrealized_pnl']}")
    print(f"R-multiple: {metrics['r_multiple']}")
"""

from __future__ import annotations

from typing import Optional

from services.trade_constants import COMM_PER_CONTRACT, DOLLARS_PER_POINT

from .position_state import PositionState


class MetricsCalculator:
    """
    Pure calculation functions for trading metrics.

    All methods are stateless and take PositionState as input.
    No side effects, no mutations.
    """

    @staticmethod
    def calculate_unrealized_pnl(state: PositionState) -> float:
        """
        Calculate current unrealized P&L.

        Args:
            state: Position state snapshot

        Returns:
            P&L in dollars (positive = profit, negative = loss)
        """
        return state.current_pnl()

    @staticmethod
    def calculate_mae(state: PositionState) -> Optional[float]:
        """
        Calculate Maximum Adverse Excursion.

        Args:
            state: Position state snapshot

        Returns:
            MAE in dollars (always negative or zero), or None if no position
        """
        return state.mae()

    @staticmethod
    def calculate_mfe(state: PositionState) -> Optional[float]:
        """
        Calculate Maximum Favorable Excursion.

        Args:
            state: Position state snapshot

        Returns:
            MFE in dollars (always positive or zero), or None if no position
        """
        return state.mfe()

    @staticmethod
    def calculate_risk_amount(state: PositionState) -> Optional[float]:
        """
        Calculate risk amount (distance to stop).

        Args:
            state: Position state snapshot

        Returns:
            Risk in dollars, or None if no stop set
        """
        return state.risk_amount()

    @staticmethod
    def calculate_reward_amount(state: PositionState) -> Optional[float]:
        """
        Calculate reward amount (distance to target).

        Args:
            state: Position state snapshot

        Returns:
            Reward in dollars, or None if no target set
        """
        return state.reward_amount()

    @staticmethod
    def calculate_r_multiple(state: PositionState) -> Optional[float]:
        """
        Calculate R-multiple (current P&L / risk).

        Args:
            state: Position state snapshot

        Returns:
            R-multiple (e.g., 2.5 = 2.5R), or None if no risk defined
        """
        return state.r_multiple()

    @staticmethod
    def calculate_efficiency(state: PositionState) -> Optional[float]:
        """
        Calculate efficiency (current P&L / MFE).

        Args:
            state: Position state snapshot

        Returns:
            Efficiency as percentage (0-100), or None if no MFE
        """
        return state.efficiency()

    @staticmethod
    def calculate_risk_reward_ratio(state: PositionState) -> Optional[float]:
        """
        Calculate risk:reward ratio.

        Args:
            state: Position state snapshot

        Returns:
            Risk:reward ratio (e.g., 3.0 = 1:3), or None if not defined
        """
        risk = state.risk_amount()
        reward = state.reward_amount()

        if risk is None or reward is None or risk == 0:
            return None

        return reward / risk

    @staticmethod
    def calculate_range_percent(state: PositionState) -> Optional[float]:
        """
        Calculate where current price is within the trade range.

        Args:
            state: Position state snapshot

        Returns:
            Percentage (0-100) where 0 = at worst, 100 = at best, or None if no position
        """
        if state.is_flat():
            return None

        trade_range = state.trade_max_price - state.trade_min_price
        if trade_range == 0:
            return 50.0  # No range yet

        if state.is_long:
            # For long: range is from min to max
            price_in_range = state.last_price - state.trade_min_price
        else:
            # For short: range is reversed (max is worst, min is best)
            price_in_range = state.trade_max_price - state.last_price

        range_pct = (price_in_range / trade_range) * 100.0

        # Clamp to 0-100
        return max(0.0, min(100.0, range_pct))

    @staticmethod
    def calculate_vwap_distance(state: PositionState) -> float:
        """
        Calculate distance from current price to VWAP.

        Args:
            state: Position state snapshot

        Returns:
            Distance in points (positive = above VWAP, negative = below)
        """
        if state.vwap == 0:
            return 0.0

        return state.last_price - state.vwap

    @staticmethod
    def calculate_entry_vwap_distance(state: PositionState) -> Optional[float]:
        """
        Calculate distance from entry to entry VWAP.

        Args:
            state: Position state snapshot

        Returns:
            Distance in points, or None if no entry VWAP captured
        """
        if state.entry_vwap is None:
            return None

        return state.entry_price - state.entry_vwap

    @staticmethod
    def calculate_time_in_trade(state: PositionState, current_epoch: int) -> Optional[int]:
        """
        Calculate time in trade (seconds).

        Args:
            state: Position state snapshot
            current_epoch: Current Unix timestamp

        Returns:
            Seconds in trade, or None if no position
        """
        if state.is_flat() or state.entry_time_epoch == 0:
            return None

        duration_sec = current_epoch - state.entry_time_epoch
        return max(0, duration_sec)

    @staticmethod
    def calculate_heat_duration(state: PositionState, current_epoch: int) -> Optional[int]:
        """
        Calculate heat duration (time in drawdown).

        Args:
            state: Position state snapshot
            current_epoch: Current Unix timestamp

        Returns:
            Seconds in drawdown, or None if not in drawdown
        """
        if state.heat_start_epoch is None:
            return None

        duration_sec = current_epoch - state.heat_start_epoch
        return max(0, duration_sec)

    @staticmethod
    def calculate_points_moved(state: PositionState) -> float:
        """
        Calculate points moved from entry.

        Args:
            state: Position state snapshot

        Returns:
            Signed points moved (positive = favorable, negative = adverse)
        """
        if state.is_flat():
            return 0.0

        direction = 1 if state.is_long else -1
        return direction * (state.last_price - state.entry_price)

    @staticmethod
    def calculate_commission(state: PositionState) -> float:
        """
        Calculate estimated round-trip commission.

        Args:
            state: Position state snapshot

        Returns:
            Commission in dollars
        """
        if state.is_flat():
            return 0.0

        # Round-trip commission (entry + exit)
        return abs(state.entry_qty) * COMM_PER_CONTRACT * 2

    @staticmethod
    def calculate_net_pnl(state: PositionState) -> float:
        """
        Calculate net P&L (unrealized P&L - commission).

        Args:
            state: Position state snapshot

        Returns:
            Net P&L in dollars
        """
        unrealized = state.current_pnl()
        commission = MetricsCalculator.calculate_commission(state)

        return unrealized - commission

    @staticmethod
    def calculate_all(state: PositionState, current_epoch: Optional[int] = None) -> dict:
        """
        Calculate all metrics at once.

        Args:
            state: Position state snapshot
            current_epoch: Current Unix timestamp (optional, for time-based metrics)

        Returns:
            Dict with all calculated metrics:
            {
                'unrealized_pnl': float,
                'mae': float | None,
                'mfe': float | None,
                'risk_amount': float | None,
                'reward_amount': float | None,
                'r_multiple': float | None,
                'efficiency': float | None,
                'risk_reward_ratio': float | None,
                'range_percent': float | None,
                'vwap_distance': float,
                'entry_vwap_distance': float | None,
                'time_in_trade': int | None,
                'heat_duration': int | None,
                'points_moved': float,
                'commission': float,
                'net_pnl': float
            }
        """
        calc = MetricsCalculator()

        metrics = {
            "unrealized_pnl": calc.calculate_unrealized_pnl(state),
            "mae": calc.calculate_mae(state),
            "mfe": calc.calculate_mfe(state),
            "risk_amount": calc.calculate_risk_amount(state),
            "reward_amount": calc.calculate_reward_amount(state),
            "r_multiple": calc.calculate_r_multiple(state),
            "efficiency": calc.calculate_efficiency(state),
            "risk_reward_ratio": calc.calculate_risk_reward_ratio(state),
            "range_percent": calc.calculate_range_percent(state),
            "vwap_distance": calc.calculate_vwap_distance(state),
            "entry_vwap_distance": calc.calculate_entry_vwap_distance(state),
            "points_moved": calc.calculate_points_moved(state),
            "commission": calc.calculate_commission(state),
            "net_pnl": calc.calculate_net_pnl(state),
        }

        # Add time-based metrics if current_epoch provided
        if current_epoch is not None:
            metrics["time_in_trade"] = calc.calculate_time_in_trade(state, current_epoch)
            metrics["heat_duration"] = calc.calculate_heat_duration(state, current_epoch)

        return metrics


# =============================================================================
# FORMATTING HELPERS
# =============================================================================

def format_pnl(pnl: Optional[float]) -> str:
    """
    Format P&L for display.

    Args:
        pnl: P&L in dollars

    Returns:
        Formatted string (e.g., "+125.50", "-75.25", "0.00")
    """
    if pnl is None:
        return "--"

    if pnl > 0:
        return f"+{pnl:.2f}"
    elif pnl < 0:
        return f"{pnl:.2f}"  # Already has minus sign
    else:
        return "0.00"


def format_r_multiple(r_mult: Optional[float]) -> str:
    """
    Format R-multiple for display.

    Args:
        r_mult: R-multiple value

    Returns:
        Formatted string (e.g., "+2.5R", "-1.2R", "--")
    """
    if r_mult is None:
        return "--"

    if r_mult > 0:
        return f"+{r_mult:.1f}R"
    elif r_mult < 0:
        return f"{r_mult:.1f}R"
    else:
        return "0.0R"


def format_efficiency(efficiency: Optional[float]) -> str:
    """
    Format efficiency for display.

    Args:
        efficiency: Efficiency percentage

    Returns:
        Formatted string (e.g., "75%", "120%", "--")
    """
    if efficiency is None:
        return "--"

    return f"{efficiency:.0f}%"


def format_time(seconds: Optional[int]) -> str:
    """
    Format time duration for display.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1:23", "10:05", "20s")
    """
    if seconds is None:
        return "--"

    if seconds < 60:
        return f"{seconds}s"

    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def format_points(points: float, show_sign: bool = True) -> str:
    """
    Format points for display.

    Args:
        points: Points value
        show_sign: Whether to show + sign for positive values

    Returns:
        Formatted string (e.g., "+2.5", "-1.25", "0.0")
    """
    if show_sign and points > 0:
        return f"+{points:.2f}"
    else:
        return f"{points:.2f}"
