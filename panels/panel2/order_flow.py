"""
panels/panel2/order_flow.py

DTC order and position update handler for Panel2.

This module processes DTC (Data and Trading Communications) protocol messages
for order and position updates, managing the position lifecycle and detecting
trade closures.

Architecture:
- Event-driven (emits Qt signals on state changes)
- Handles Sierra Chart DTC quirks (SIM mode seeding, dual closure paths)
- Auto-detects stop/target from order prices
- Builds trade dicts with full P&L calculations
- No UI dependencies (signals only)

Usage:
    from panels.panel2.order_flow import OrderFlow
    from panels.panel2.position_state import PositionState

    order_flow = OrderFlow()

    # Connect signals
    order_flow.positionOpened.connect(on_position_opened)
    order_flow.positionClosed.connect(on_position_closed)
    order_flow.tradeCloseRequested.connect(on_trade_close)

    # Set current state
    order_flow.set_state(position_state)

    # Process DTC messages
    order_flow.on_order_update(payload)
    order_flow.on_position_update(payload)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from PyQt6 import QtCore

import structlog

from services.trade_constants import COMM_PER_CONTRACT, DOLLARS_PER_POINT
from utils.trade_mode import detect_mode_from_account

from .position_state import PositionState

log = structlog.get_logger(__name__)

# UTC timezone for timestamps
UTC = timezone.utc


class OrderFlow(QtCore.QObject):
    """
    Handles DTC order and position updates for Panel2.

    Processes DTC messages to detect position changes, stop/target orders,
    and trade closures. Emits signals for upstream handling.

    DTC Protocol Quirks Handled:
    - SIM mode: Never sends non-zero PositionUpdate (must seed from fills)
    - Order detection: Infer stop/target from sell order prices
    - Closure detection: Two paths (OrderUpdate qty decrease, PositionUpdate qty → 0)
    - Missing data: Fallback chain for exit price
    """

    # Signals
    positionOpened = QtCore.pyqtSignal(object)  # PositionState
    positionClosed = QtCore.pyqtSignal(dict)  # Trade dict
    tradeCloseRequested = QtCore.pyqtSignal(dict)  # Trade dict to TradeCloseService

    # State update signals
    stateUpdated = QtCore.pyqtSignal(object)  # PositionState (for any state change)

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """
        Initialize order flow handler.

        Args:
            parent: Parent QObject (optional)
        """
        super().__init__(parent)

        # Current position state
        self._state: PositionState = PositionState.flat()

        log.info("[OrderFlow] Initialized")

    def set_state(self, state: PositionState) -> None:
        """
        Set current position state.

        Called by Panel2Main to update state from other sources
        (e.g., persistence, manual position entry).

        Args:
            state: New position state
        """
        self._state = state
        log.debug(
            "[OrderFlow] State updated",
            has_position=state.has_position(),
            qty=state.entry_qty,
            price=state.entry_price
        )

    def get_state(self) -> PositionState:
        """
        Get current position state.

        Returns:
            Current PositionState
        """
        return self._state

    # =========================================================================
    # DTC MESSAGE HANDLERS
    # =========================================================================

    def on_order_update(self, payload: dict) -> None:
        """
        Handle normalized OrderUpdate from DTC (via data_bridge).

        Responsibilities:
        - Auto-detect stop/target from sell orders
        - Seed position in SIM mode (Sierra Chart quirk)
        - Detect trade closure (quantity decrease)
        - Build trade dict with P&L calculations
        - Emit tradeCloseRequested signal

        DTC Protocol Notes:
        - Status 3 or 7 = Filled
        - BuySell: 1=Buy, 2=Sell
        - SIM mode: Must seed position from fills (no PositionUpdate)

        Args:
            payload: Normalized order update dict from data_bridge
        """
        try:
            account = payload.get("TradeAccount") or self._state.current_account or ""
            mode = detect_mode_from_account(account) if account else self._state.current_mode
            self._state = self._state.with_scope(
                mode=mode,
                account=account or self._state.current_account or "",
            )

            order_status = payload.get("OrderStatus")
            side = payload.get("BuySell")  # 1=Buy, 2=Sell
            price1 = payload.get("Price1")

            # ----------------------------------------------------------------
            # Auto-detect stop/target from sell orders
            # ----------------------------------------------------------------
            # Infer stop/target from sell order prices relative to entry
            # (DTC doesn't explicitly mark stop vs target orders)
            if side == 2 and self._state.entry_price is not None and self._state.entry_price > 0 and price1 is not None:
                price1_float = float(price1)

                # Lower than entry = Stop loss
                if price1_float < self._state.entry_price:
                    self._state = self._state.with_stop(price1_float)
                    log.info(
                        "[OrderFlow] Stop order detected",
                        stop_price=price1_float,
                        entry_price=self._state.entry_price
                    )
                    self.stateUpdated.emit(self._state)

                # Higher than entry = Target
                elif price1_float > self._state.entry_price:
                    self._state = self._state.with_target(price1_float)
                    log.info(
                        "[OrderFlow] Target order detected",
                        target_price=price1_float,
                        entry_price=self._state.entry_price
                    )
                    self.stateUpdated.emit(self._state)

            # ----------------------------------------------------------------
            # Process fills (Status 3=Filled, 7=Filled)
            # ----------------------------------------------------------------
            if order_status not in (3, 7):
                return

            # Extract fill data
            qty = payload.get("FilledQuantity") or 0
            price = payload.get("AverageFillPrice") or payload.get("Price1")
            is_long = side == 1

            # ----------------------------------------------------------------
            # SIM mode workaround: Seed position from fill
            # ----------------------------------------------------------------
            # Sierra Chart in SIM mode never sends non-zero PositionUpdate,
            # only qty=0. Must seed position from OrderUpdate fills.
            if qty > 0 and price is not None:
                # Only seed if currently flat (no existing position)
                if self._state.is_flat():
                    # Seed position from fill
                    self._state = self._open_position_from_fill(
                        qty=qty,
                        price=float(price),
                        is_long=is_long,
                        payload=payload
                    )

                    log.info(
                        "[OrderFlow] Position seeded from fill (SIM mode)",
                        qty=qty,
                        price=price,
                        is_long=is_long
                    )

                    # Emit position opened signal
                    self.positionOpened.emit(self._state)
                    self.stateUpdated.emit(self._state)

                    return  # Early exit - don't process as close

            # ----------------------------------------------------------------
            # Detect trade closure (qty decrease)
            # ----------------------------------------------------------------
            # CRITICAL: Only process as CLOSE if quantity is DECREASING
            # If qty stayed same or increased, this is NOT a close
            if not self._state.has_position():
                return

            current_qty = self._state.entry_qty

            # If incoming qty >= current qty, this is NOT a close
            if qty >= current_qty:
                return

            # ----------------------------------------------------------------
            # Build trade dict and emit closure signal
            # ----------------------------------------------------------------
            log.info(
                "[OrderFlow] Trade closure detected",
                prev_qty=current_qty,
                new_qty=qty
            )

            # Extract exit price from payload (fallback chain)
            exit_price = (
                payload.get("LastFillPrice")
                or payload.get("AverageFillPrice")
                or payload.get("Price1")
                or self._state.last_price
            )

            if exit_price is None:
                log.warning("[OrderFlow] Fill detected but no exit price available")
                return

            exit_price = float(exit_price)

            # Build trade dict
            trade = self._build_trade_dict(
                exit_price=exit_price,
                payload=payload
            )

            log.info("[OrderFlow] Trade dict created", trade=trade)

            # Emit signals
            self.tradeCloseRequested.emit(trade)
            self.positionClosed.emit(trade)

            # Clear position state
            mode = trade.get("mode", self._state.current_mode)
            account = trade.get("account", self._state.current_account)
            self._state = PositionState.flat(mode=mode, account=account)
            self.stateUpdated.emit(self._state)

        except Exception as e:
            log.error("[OrderFlow] Error in on_order_update", error=str(e), exc_info=True)

    def on_position_update(self, payload: dict) -> None:
        """
        Handle normalized PositionUpdate from DTC.

        Responsibilities:
        - Update position state from DTC
        - Extract symbol from position (not quote feed)
        - Detect trade closure (qty → 0)
        - Emit positionOpened/positionClosed signals

        DTC Protocol Notes:
        - qty=0 indicates flat position
        - avg_entry is average entry price
        - Symbol must be extracted from payload (not quote feed)

        Args:
            payload: Normalized position update dict from MessageRouter
        """
        try:
            # Extract from normalized payload (lowercase keys)
            qty = int(payload.get("qty", 0))
            avg_price = payload.get("avg_entry")

            # CRITICAL: Extract symbol from PositionUpdate payload
            # (NOT from quote feed - position symbol is authoritative)
            symbol = payload.get("symbol") or payload.get("Symbol") or ""

            # Convert to float if not None
            if avg_price is not None:
                avg_price = float(avg_price)

            log.debug(
                "[OrderFlow] Position update received",
                qty=qty,
                avg_entry=avg_price,
                symbol=symbol,
                account=payload.get("TradeAccount", "unknown")
            )

            # ----------------------------------------------------------------
            # Validate position data
            # ----------------------------------------------------------------
            # CRITICAL: Reject positions without valid price (avoid stale data)
            if qty != 0 and avg_price is None:
                log.warning(
                    "[OrderFlow] Rejecting position with qty but missing price",
                    qty=qty
                )
                return

            # Determine direction
            is_long = None if qty == 0 else (qty > 0)

            account = payload.get("TradeAccount") or self._state.current_account or ""
            mode = detect_mode_from_account(account) if account else self._state.current_mode
            self._state = self._state.with_scope(
                mode=mode,
                account=account or self._state.current_account or "",
            )

            # ----------------------------------------------------------------
            # Detect trade closure (qty → 0)
            # ----------------------------------------------------------------
            if qty == 0 and self._state.has_position():
                log.info(
                    "[OrderFlow] Trade closure detected (qty → 0)",
                    prev_qty=self._state.entry_qty,
                    prev_price=self._state.entry_price
                )

                # Use last price as exit price (position already closed)
                exit_price = self._state.last_price if self._state.last_price else self._state.entry_price

                # Build trade dict
                trade = self._build_trade_dict(
                    exit_price=exit_price,
                    payload=payload
                )

                log.info("[OrderFlow] Trade dict created from position closure", trade=trade)

                # Emit signals
                self.tradeCloseRequested.emit(trade)
                self.positionClosed.emit(trade)

                # Clear position state
                mode = trade.get("mode", self._state.current_mode)
                account = trade.get("account", self._state.current_account)
                self._state = PositionState.flat(mode=mode, account=account)
                self.stateUpdated.emit(self._state)

                return

            # ----------------------------------------------------------------
            # Update position state
            # ----------------------------------------------------------------
            # Only update if we have valid data (qty=0 OR avg_price valid)
            if qty == 0 or avg_price is not None:
                # Update symbol if provided
                if symbol:
                    self._state = self._state.with_symbol(symbol)

                # If opening position (qty > 0 and was flat)
                was_flat = self._state.is_flat()

                if qty > 0 and avg_price is not None:
                    # Opening or updating position
                    self._state = self._state.with_position(
                        entry_qty=abs(qty),
                        entry_price=avg_price,
                        is_long=is_long
                    )

                    log.info(
                        "[OrderFlow] Position updated",
                        symbol=symbol,
                        qty=qty,
                        avg_entry=avg_price,
                        is_long=is_long
                    )

                    # Emit position opened if transitioning from flat
                    if was_flat:
                        self.positionOpened.emit(self._state)

                    self.stateUpdated.emit(self._state)

                elif qty == 0:
                    # Already handled closure above, just update state
                    pass
            else:
                log.warning(
                    "[OrderFlow] Invalid position data - skipping",
                    qty=qty,
                    avg_price=avg_price
                )

        except Exception as e:
            log.error("[OrderFlow] Error in on_position_update", error=str(e), exc_info=True)

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _open_position_from_fill(
        self,
        qty: int,
        price: float,
        is_long: bool,
        payload: dict
    ) -> PositionState:
        """
        Create new position state from fill data.

        Used for SIM mode seeding (Sierra Chart doesn't send PositionUpdate).

        Args:
            qty: Fill quantity
            price: Fill price
            is_long: True if long, False if short
            payload: DTC payload (for symbol extraction)

        Returns:
            New PositionState with position opened
        """
        import time

        # Extract symbol from payload
        symbol = payload.get("Symbol") or self._state.symbol
        account = payload.get("TradeAccount") or self._state.current_account or ""
        mode = detect_mode_from_account(account) if account else self._state.current_mode

        # Create new state with position
        state = self._state.with_position(
            entry_qty=abs(qty),
            entry_price=price,
            is_long=is_long
        )

        # Update symbol
        state = state.with_symbol(symbol)

        # Set entry time
        state = state.with_entry_time(int(time.time()))

        # Update mode/account scope
        state = state.with_scope(
            mode=mode,
            account=account or self._state.current_account or "",
        )

        return state

    def _build_trade_dict(
        self,
        exit_price: float,
        payload: dict
    ) -> dict:
        """
        Build trade dict for closure with full P&L calculations.

        Args:
            exit_price: Exit price
            payload: DTC payload (for account/timestamp)

        Returns:
            Trade dict with all metrics
        """
        # Basic trade data
        qty = int(abs(self._state.entry_qty))
        side = "long" if self._state.is_long else "short"
        entry_price = float(self._state.entry_price)

        # P&L calculation
        price_diff = exit_price - entry_price
        if not self._state.is_long:
            price_diff = -price_diff  # Invert for short positions

        realized_pnl = price_diff * qty * DOLLARS_PER_POINT

        # Commissions
        commissions = COMM_PER_CONTRACT * qty

        # R-multiple
        r_multiple = self._calculate_r_multiple(exit_price)

        # MAE/MFE
        mae = self._calculate_mae()
        mfe = self._calculate_mfe()

        # Efficiency
        efficiency = self._calculate_efficiency(exit_price)

        # Timestamps
        entry_time = None
        if self._state.entry_time_epoch:
            entry_time = datetime.fromtimestamp(self._state.entry_time_epoch, tz=UTC)

        # Use DTC timestamp from payload if available
        exit_ts = payload.get("DateTime")
        if exit_ts:
            exit_time = datetime.fromtimestamp(float(exit_ts), tz=UTC)
        else:
            exit_time = datetime.now(tz=UTC)

        # Get account and mode
        account = payload.get("TradeAccount") or self._state.current_account or ""
        mode = detect_mode_from_account(account) if account else self._state.current_mode

        # Build trade dict
        trade = {
            "symbol": self._state.symbol or "",
            "side": side,
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "commissions": commissions,
            "r_multiple": r_multiple,
            "mae": mae,
            "mfe": mfe,
            "efficiency": efficiency,
            "account": account or self._state.current_account or "",
            "mode": mode,
        }

        return trade

    def _calculate_r_multiple(self, exit_price: float) -> Optional[float]:
        """
        Calculate R-multiple for trade.

        R-multiple = Gain / Risk
        where Risk = |entry - stop|

        Args:
            exit_price: Exit price

        Returns:
            R-multiple, or None if no stop set
        """
        if self._state.stop_price is None or self._state.stop_price == 0:
            return None

        # Calculate risk (distance from entry to stop)
        risk = abs(self._state.entry_price - self._state.stop_price)

        if risk == 0:
            return None

        # Calculate gain (signed for direction)
        if self._state.is_long:
            gain = exit_price - self._state.entry_price
        else:
            gain = self._state.entry_price - exit_price

        # R-multiple = Gain / Risk
        r_multiple = gain / risk

        return r_multiple

    def _calculate_mae(self) -> Optional[float]:
        """
        Calculate Maximum Adverse Excursion (MAE).

        MAE = worst price movement against position during trade

        Returns:
            MAE in dollars, or None if no extremes tracked
        """
        if self._state.trade_min_price == 0 or self._state.trade_max_price == 0:
            return None

        # For long: MAE is entry - min
        # For short: MAE is max - entry
        if self._state.is_long:
            mae_points = self._state.entry_price - self._state.trade_min_price
        else:
            mae_points = self._state.trade_max_price - self._state.entry_price

        # Convert to dollars (always positive)
        mae = abs(mae_points) * DOLLARS_PER_POINT * abs(self._state.entry_qty)

        return mae

    def _calculate_mfe(self) -> Optional[float]:
        """
        Calculate Maximum Favorable Excursion (MFE).

        MFE = best price movement in favor of position during trade

        Returns:
            MFE in dollars, or None if no extremes tracked
        """
        if self._state.trade_min_price == 0 or self._state.trade_max_price == 0:
            return None

        # For long: MFE is max - entry
        # For short: MFE is entry - min
        if self._state.is_long:
            mfe_points = self._state.trade_max_price - self._state.entry_price
        else:
            mfe_points = self._state.entry_price - self._state.trade_min_price

        # Convert to dollars (always positive)
        mfe = abs(mfe_points) * DOLLARS_PER_POINT * abs(self._state.entry_qty)

        return mfe

    def _calculate_efficiency(self, exit_price: float) -> Optional[float]:
        """
        Calculate trade efficiency.

        Efficiency = (Realized Gain / MFE) * 100

        Measures how much of the potential profit was captured.
        100% = exited at peak, 0% = gave back all gains

        Args:
            exit_price: Exit price

        Returns:
            Efficiency percentage, or None if MFE is 0
        """
        mfe = self._calculate_mfe()

        if mfe is None or mfe == 0:
            return None

        # Calculate realized gain
        if self._state.is_long:
            gain_points = exit_price - self._state.entry_price
        else:
            gain_points = self._state.entry_price - exit_price

        realized_gain = gain_points * DOLLARS_PER_POINT * abs(self._state.entry_qty)

        # Efficiency = (Realized / MFE) * 100
        efficiency = (realized_gain / mfe) * 100

        # Clamp to 0-100 range
        efficiency = max(0, min(100, efficiency))

        return efficiency


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_symbol_display(full_symbol: str) -> str:
    """
    Extract 3-letter display symbol from full DTC symbol.

    Example: 'F.US.MESZ25' -> 'MES'

    Args:
        full_symbol: Full DTC symbol string

    Returns:
        3-letter display symbol, or full symbol if format doesn't match
    """
    try:
        # Look for pattern: *.US.XXX* where XXX are the 3 letters we want
        parts = full_symbol.split(".")
        for i, part in enumerate(parts):
            if part == "US" and i + 1 < len(parts):
                # Get the next part after 'US'
                next_part = parts[i + 1]
                if len(next_part) >= 3:
                    # Extract first 3 letters
                    return next_part[:3].upper()

        # Fallback: return as-is
        return full_symbol.strip().upper()

    except Exception:
        return full_symbol.strip().upper()
