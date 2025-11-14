"""
services/position_service.py

Thin position service wrapper around PositionRepository for UI callers.

Architecture:
- Panels should not talk to repositories or the database directly.
- This service provides a minimal facade that Panel2 can use for:
  - Saving open positions (write-through)
  - Updating trade extremes for MAE/MFE tracking
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from data.position_repository import get_position_repository
from utils.logger import get_logger


log = get_logger(__name__)


class PositionService:
    """Service façade over PositionRepository for open position writes."""

    def __init__(self):
        self._repo = get_position_repository()

    def save_open_position(
        self,
        mode: str,
        account: str,
        symbol: str,
        qty: int,
        entry_price: float,
        entry_time_epoch: Optional[int],
        entry_vwap: Optional[float],
        entry_cum_delta: Optional[float],
        entry_poc: Optional[float],
        target_price: Optional[float],
        stop_price: Optional[float],
    ) -> bool:
        """
        Persist open position snapshot to the database for the given scope.

        Args mirror Panel2's current state; entry_time_epoch is converted to UTC.
        """
        try:
            if qty == 0 or entry_price is None:
                return False

            # Convert epoch to aware datetime (UTC)
            if entry_time_epoch:
                entry_time = datetime.fromtimestamp(entry_time_epoch, tz=timezone.utc)
            else:
                entry_time = datetime.now(timezone.utc)

            success = self._repo.save_open_position(
                mode=mode,
                account=account,
                symbol=symbol,
                qty=qty,
                entry_price=entry_price,
                entry_time=entry_time,
                entry_vwap=entry_vwap,
                entry_cum_delta=entry_cum_delta,
                entry_poc=entry_poc,
                target_price=target_price,
                stop_price=stop_price,
            )

            if success:
                log.info(
                    "[PositionService] Open position saved",
                    mode=mode,
                    account=account,
                    symbol=symbol,
                    qty=qty,
                    entry_price=entry_price,
                )
            else:
                log.error(
                    "[PositionService] Failed to save open position",
                    mode=mode,
                    account=account,
                    symbol=symbol,
                )

            return success
        except Exception as e:  # pragma: no cover - defensive logging
            log.error(f"[PositionService] Error saving open position: {e}", exc_info=True)
            return False

    def update_trade_extremes(self, mode: str, account: str, current_price: float) -> bool:
        """
        Update MAE/MFE extremes for the active open position.
        """
        try:
            return self._repo.update_trade_extremes(
                mode=mode,
                account=account,
                current_price=current_price,
            )
        except Exception as e:  # pragma: no cover - defensive logging
            log.debug(f"[PositionService] Trade extremes update failed: {e}")
            return False


_position_service: Optional[PositionService] = None


def get_position_service() -> PositionService:
    """Singleton accessor for PositionService."""
    global _position_service
    if _position_service is None:
        _position_service = PositionService()
    return _position_service

