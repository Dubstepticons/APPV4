"""
data/position_repository.py

Repository pattern for position persistence - single source of truth.

This module provides a clean abstraction for position database operations,
implementing the Repository pattern to decouple business logic from SQL.

Key Operations:
- save_open_position(): Upsert open position (write-through)
- get_open_position(): Read current open position for mode/account
- close_position(): Move from OpenPosition → TradeRecord
- update_trade_extremes(): Update MAE/MFE tracking
- recover_all_open_positions(): Startup recovery

Thread Safety: All methods acquire database session per call.
SQLAlchemy handles connection pooling and thread safety.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.exc import IntegrityError

from data.db_engine import get_session
from data.schema import OpenPosition, TradeRecord
from utils.logger import get_logger

log = get_logger(__name__)


class PositionRepository:
    """
    Repository for position persistence operations.

    Implements single source of truth pattern:
    - Database is authoritative
    - Write-through on every change
    - Read on demand (startup, mode switch)

    All methods are instance-based (not static) for testability.
    """

    def save_open_position(
        self,
        mode: str,
        account: str,
        symbol: str,
        qty: int,
        entry_price: float,
        entry_time: Optional[datetime] = None,
        entry_vwap: Optional[float] = None,
        entry_cum_delta: Optional[float] = None,
        entry_poc: Optional[float] = None,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> bool:
        """
        Save (insert or update) open position to database.

        Uses UPSERT semantics: If position exists for (mode, account), update it.
        Otherwise, insert new position.

        Args:
            mode: Trading mode ("SIM", "LIVE", "DEBUG")
            account: Account identifier
            symbol: Trading symbol (e.g., "MES", "MNQ")
            qty: Signed quantity (positive=long, negative=short)
            entry_price: Average entry price
            entry_time: Entry timestamp (defaults to now UTC)
            entry_vwap: VWAP at entry (for trade record)
            entry_cum_delta: Cumulative delta at entry
            entry_poc: Point of control at entry
            target_price: Target price for bracket order
            stop_price: Stop price for bracket order

        Returns:
            True if save succeeded, False if error

        Thread-Safe: Yes (session per call)
        """
        try:
            if entry_time is None:
                entry_time = datetime.now(timezone.utc)

            side = "LONG" if qty > 0 else "SHORT"

            with get_session() as session:
                # Check if position exists
                existing = session.query(OpenPosition).filter_by(
                    mode=mode,
                    account=account
                ).first()

                if existing:
                    # Update existing position
                    existing.symbol = symbol
                    existing.qty = qty
                    existing.side = side
                    existing.entry_price = entry_price
                    existing.entry_time = entry_time
                    existing.entry_vwap = entry_vwap
                    existing.entry_cum_delta = entry_cum_delta
                    existing.entry_poc = entry_poc
                    existing.target_price = target_price
                    existing.stop_price = stop_price
                    existing.updated_at = datetime.now(timezone.utc)

                    # Initialize trade extremes if not set
                    if existing.trade_min_price is None:
                        existing.trade_min_price = entry_price
                    if existing.trade_max_price is None:
                        existing.trade_max_price = entry_price

                    log.info(
                        f"[PositionRepo] Updated open position: {mode}/{account} {symbol} {qty}@{entry_price}"
                    )
                else:
                    # Insert new position
                    new_position = OpenPosition(
                        mode=mode,
                        account=account,
                        symbol=symbol,
                        qty=qty,
                        side=side,
                        entry_price=entry_price,
                        entry_time=entry_time,
                        entry_vwap=entry_vwap,
                        entry_cum_delta=entry_cum_delta,
                        entry_poc=entry_poc,
                        target_price=target_price,
                        stop_price=stop_price,
                        trade_min_price=entry_price,  # Initialize to entry
                        trade_max_price=entry_price,  # Initialize to entry
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(new_position)

                    log.info(
                        f"[PositionRepo] Created open position: {mode}/{account} {symbol} {qty}@{entry_price}"
                    )

                session.commit()
                return True

        except IntegrityError as e:
            log.error(f"[PositionRepo] Integrity error saving position: {e}")
            return False
        except Exception as e:
            log.error(f"[PositionRepo] Error saving open position: {e}")
            return False

    def get_open_position(self, mode: str, account: str) -> Optional[Dict[str, Any]]:
        """
        Get current open position for (mode, account).

        Args:
            mode: Trading mode
            account: Account identifier

        Returns:
            Dict with position data if exists, None otherwise

        Thread-Safe: Yes
        """
        try:
            with get_session() as session:
                position = session.query(OpenPosition).filter_by(
                    mode=mode,
                    account=account
                ).first()

                if not position:
                    return None

                # Convert to dict for easier consumption
                return {
                    "id": position.id,
                    "mode": position.mode,
                    "account": position.account,
                    "symbol": position.symbol,
                    "qty": position.qty,
                    "side": position.side,
                    "entry_price": position.entry_price,
                    "entry_time": position.entry_time,
                    "target_price": position.target_price,
                    "stop_price": position.stop_price,
                    "entry_vwap": position.entry_vwap,
                    "entry_cum_delta": position.entry_cum_delta,
                    "entry_poc": position.entry_poc,
                    "trade_min_price": position.trade_min_price,
                    "trade_max_price": position.trade_max_price,
                    "created_at": position.created_at,
                    "updated_at": position.updated_at,
                }

        except Exception as e:
            log.error(f"[PositionRepo] Error getting open position: {e}")
            return None

    def update_trade_extremes(
        self,
        mode: str,
        account: str,
        current_price: float
    ) -> bool:
        """
        Update trade min/max prices for MAE/MFE tracking.

        Called periodically (e.g., every 100ms) while position is open.

        Args:
            mode: Trading mode
            account: Account identifier
            current_price: Current market price

        Returns:
            True if update succeeded, False if error or position not found

        Thread-Safe: Yes
        """
        try:
            with get_session() as session:
                position = session.query(OpenPosition).filter_by(
                    mode=mode,
                    account=account
                ).first()

                if not position:
                    return False

                # Update extremes
                updated = False
                if position.trade_min_price is None or current_price < position.trade_min_price:
                    position.trade_min_price = current_price
                    updated = True

                if position.trade_max_price is None or current_price > position.trade_max_price:
                    position.trade_max_price = current_price
                    updated = True

                if updated:
                    position.updated_at = datetime.now(timezone.utc)
                    session.commit()

                return True

        except Exception as e:
            log.error(f"[PositionRepo] Error updating trade extremes: {e}")
            return False

    def close_position(
        self,
        mode: str,
        account: str,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        realized_pnl: Optional[float] = None,
        commissions: Optional[float] = None,
        exit_vwap: Optional[float] = None,
        exit_cum_delta: Optional[float] = None,
    ) -> Optional[int]:
        """
        Close open position and create TradeRecord.

        Atomic operation:
        1. Read OpenPosition
        2. Calculate MAE/MFE from trade extremes
        3. Create TradeRecord with full trade data
        4. Delete OpenPosition
        5. Commit transaction

        Args:
            mode: Trading mode
            account: Account identifier
            exit_price: Exit price
            exit_time: Exit timestamp (defaults to now UTC)
            realized_pnl: Realized P&L (will calculate if None)
            commissions: Total commissions
            exit_vwap: VWAP at exit
            exit_cum_delta: Cumulative delta at exit

        Returns:
            TradeRecord ID if successful, None if error or position not found

        Thread-Safe: Yes (transactional)
        """
        try:
            if exit_time is None:
                exit_time = datetime.now(timezone.utc)

            with get_session() as session:
                # 1. Read open position
                open_pos = session.query(OpenPosition).filter_by(
                    mode=mode,
                    account=account
                ).first()

                if not open_pos:
                    log.warning(f"[PositionRepo] No open position to close: {mode}/{account}")
                    return None

                # 2. Calculate P&L if not provided
                if realized_pnl is None:
                    # P&L = (exit - entry) * qty * dollars_per_point
                    # For futures, dollars_per_point depends on contract (e.g., MES = $5)
                    from services.trade_constants import DOLLARS_PER_POINT
                    price_diff = exit_price - open_pos.entry_price
                    realized_pnl = price_diff * abs(open_pos.qty) * DOLLARS_PER_POINT
                    # Adjust sign for short positions
                    if open_pos.qty < 0:
                        realized_pnl = -realized_pnl

                # 3. Calculate MAE/MFE from trade extremes
                mae, mfe, efficiency, r_multiple = self._calculate_trade_metrics(
                    open_pos=open_pos,
                    exit_price=exit_price,
                    realized_pnl=realized_pnl,
                )

                # 4. Create TradeRecord
                trade = TradeRecord(
                    symbol=open_pos.symbol,
                    side=open_pos.side,
                    qty=abs(open_pos.qty),
                    mode=open_pos.mode,
                    account=open_pos.account,
                    # Entry data
                    entry_time=open_pos.entry_time,
                    entry_price=open_pos.entry_price,
                    entry_vwap=open_pos.entry_vwap,
                    entry_cum_delta=open_pos.entry_cum_delta,
                    # Exit data
                    exit_time=exit_time,
                    exit_price=exit_price,
                    exit_vwap=exit_vwap,
                    exit_cum_delta=exit_cum_delta,
                    # P&L and metrics
                    realized_pnl=realized_pnl,
                    commissions=commissions,
                    mae=mae,
                    mfe=mfe,
                    efficiency=efficiency,
                    r_multiple=r_multiple,
                    is_closed=True,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(trade)

                # 5. Delete open position
                session.delete(open_pos)

                # 6. Commit transaction (atomic)
                session.commit()

                log.info(
                    f"[PositionRepo] Closed position: {mode}/{account} {open_pos.symbol} "
                    f"{open_pos.qty}@{open_pos.entry_price}→{exit_price} P&L={realized_pnl:+.2f}"
                )

                return trade.id

        except Exception as e:
            log.error(f"[PositionRepo] Error closing position: {e}")
            return None

    def _calculate_trade_metrics(
        self,
        open_pos: OpenPosition,
        exit_price: float,
        realized_pnl: float,
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Calculate MAE, MFE, efficiency, and R-multiple from trade data.

        MAE (Maximum Adverse Excursion): Worst unrealized loss during trade
        MFE (Maximum Favorable Excursion): Best unrealized profit during trade
        Efficiency: realized_pnl / MFE (how much of peak profit was captured)
        R-multiple: realized_pnl / risk (requires stop price)

        Returns:
            (mae, mfe, efficiency, r_multiple) tuple
        """
        from services.trade_constants import DOLLARS_PER_POINT

        mae = None
        mfe = None
        efficiency = None
        r_multiple = None

        if open_pos.trade_min_price is not None and open_pos.trade_max_price is not None:
            # For LONG: MAE = worst drawdown from entry, MFE = best run-up from entry
            # For SHORT: MAE = worst run-up from entry, MFE = best drawdown from entry

            if open_pos.side == "LONG":
                # MAE: entry - min_price (negative value)
                mae = (open_pos.trade_min_price - open_pos.entry_price) * DOLLARS_PER_POINT * abs(open_pos.qty)
                # MFE: max_price - entry (positive value)
                mfe = (open_pos.trade_max_price - open_pos.entry_price) * DOLLARS_PER_POINT * abs(open_pos.qty)
            else:  # SHORT
                # MAE: max_price - entry (negative value, because price went up)
                mae = (open_pos.entry_price - open_pos.trade_max_price) * DOLLARS_PER_POINT * abs(open_pos.qty)
                # MFE: entry - min_price (positive value, because price went down)
                mfe = (open_pos.entry_price - open_pos.trade_min_price) * DOLLARS_PER_POINT * abs(open_pos.qty)

            # Efficiency: What % of MFE was realized?
            if mfe and mfe > 0:
                efficiency = realized_pnl / mfe
                # Clamp to [0, 1] range (can exceed 1 if exit > MFE, but typically 0-1)
                efficiency = max(0.0, min(1.5, efficiency))  # Allow up to 150% efficiency

            # R-multiple: P&L / initial risk
            # Risk = distance from entry to stop (in dollars)
            if open_pos.stop_price is not None:
                stop_distance = abs(open_pos.entry_price - open_pos.stop_price)
                risk = stop_distance * DOLLARS_PER_POINT * abs(open_pos.qty)
                if risk > 0:
                    r_multiple = realized_pnl / risk

        return mae, mfe, efficiency, r_multiple

    def recover_all_open_positions(self) -> List[Dict[str, Any]]:
        """
        Recover all open positions from database (startup recovery).

        Called on app startup to restore position state after crash/restart.

        Returns:
            List of position dicts (one per (mode, account) with open position)

        Thread-Safe: Yes
        """
        try:
            with get_session() as session:
                positions = session.query(OpenPosition).all()

                result = []
                for pos in positions:
                    result.append({
                        "id": pos.id,
                        "mode": pos.mode,
                        "account": pos.account,
                        "symbol": pos.symbol,
                        "qty": pos.qty,
                        "side": pos.side,
                        "entry_price": pos.entry_price,
                        "entry_time": pos.entry_time,
                        "target_price": pos.target_price,
                        "stop_price": pos.stop_price,
                        "entry_vwap": pos.entry_vwap,
                        "entry_cum_delta": pos.entry_cum_delta,
                        "entry_poc": pos.entry_poc,
                        "trade_min_price": pos.trade_min_price,
                        "trade_max_price": pos.trade_max_price,
                        "created_at": pos.created_at,
                        "updated_at": pos.updated_at,
                    })

                if result:
                    log.info(f"[PositionRepo] Recovered {len(result)} open position(s) from database")
                else:
                    log.debug("[PositionRepo] No open positions to recover")

                return result

        except Exception as e:
            log.error(f"[PositionRepo] Error recovering open positions: {e}")
            return []

    def delete_open_position(self, mode: str, account: str) -> bool:
        """
        Delete open position without creating trade record.

        Use case: Manual cleanup, stale position removal.

        Args:
            mode: Trading mode
            account: Account identifier

        Returns:
            True if deleted, False if not found or error

        Thread-Safe: Yes
        """
        try:
            with get_session() as session:
                position = session.query(OpenPosition).filter_by(
                    mode=mode,
                    account=account
                ).first()

                if not position:
                    return False

                session.delete(position)
                session.commit()

                log.info(f"[PositionRepo] Deleted open position: {mode}/{account}")
                return True

        except Exception as e:
            log.error(f"[PositionRepo] Error deleting open position: {e}")
            return False


# Global repository instance (singleton pattern)
_position_repository: Optional[PositionRepository] = None


def get_position_repository() -> PositionRepository:
    """
    Get global PositionRepository instance (singleton).

    Returns:
        PositionRepository instance
    """
    global _position_repository
    if _position_repository is None:
        _position_repository = PositionRepository()
    return _position_repository
