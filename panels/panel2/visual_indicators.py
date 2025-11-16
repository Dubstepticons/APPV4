"""
panels/panel2/visual_indicators.py

Visual indicators handler for Panel2 - Heat timers and proximity alerts.

This module manages visual feedback for trading conditions:
- Heat tracking (time in drawdown)
- Proximity alerts (price near stop)
- Timeframe pill management
- LIVE dot pulsing

Architecture:
- Stateful tracking of heat and proximity states
- Emits Qt signals on state transitions
- No UI rendering (signals only)
- Focused on state detection, not display

Usage:
    from panels.panel2.visual_indicators import VisualIndicators
    from panels.panel2.position_state import PositionState

    indicators = VisualIndicators()
    indicators.heatEntered.connect(on_heat_entered)
    indicators.stopProximity.connect(on_stop_near)

    # Update from position state
    indicators.update(state, current_epoch=time.time())
"""

from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore

import structlog

from .position_state import PositionState

log = structlog.get_logger(__name__)


class VisualIndicators(QtCore.QObject):
    """
    Manages visual indicators for trading conditions.

    Tracks heat (time in drawdown) and proximity to stop loss.
    Emits signals on state transitions for UI updates.
    """

    # Heat thresholds (in seconds)
    HEAT_WARN_SEC = 180  # 3:00m - yellow warning
    HEAT_ALERT_FLASH_SEC = 270  # 4:30m - red + flashing
    HEAT_ALERT_SOLID_SEC = 300  # 5:00m - solid red

    # Proximity threshold (in points)
    STOP_PROXIMITY_POINTS = 1.0  # Within 1 point of stop

    # Signals
    heatEntered = QtCore.pyqtSignal()  # Entered drawdown (heat started)
    heatExited = QtCore.pyqtSignal()  # Exited drawdown (heat cleared)
    heatWarning = QtCore.pyqtSignal()  # Heat >= 3:00m
    heatAlert = QtCore.pyqtSignal()  # Heat >= 4:30m
    heatCritical = QtCore.pyqtSignal()  # Heat >= 5:00m

    stopProximity = QtCore.pyqtSignal()  # Price within 1pt of stop
    stopProximityClear = QtCore.pyqtSignal()  # Price cleared from stop

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """
        Initialize visual indicators.

        Args:
            parent: Parent QObject (optional)
        """
        super().__init__(parent)

        # State tracking
        self._prev_in_drawdown: Optional[bool] = None
        self._prev_stop_near: Optional[bool] = None
        self._prev_heat_level: Optional[str] = None  # None, "warn", "alert", "critical"

        log.info("[VisualIndicators] Initialized")

    def update(
        self,
        state: PositionState,
        current_epoch: Optional[int] = None
    ) -> None:
        """
        Update indicators from position state.

        Detects state transitions and emits appropriate signals.

        Args:
            state: Current position state
            current_epoch: Current Unix timestamp (optional, for heat calculation)
        """
        # Update heat tracking
        self._update_heat_tracking(state, current_epoch)

        # Update proximity alerts
        self._update_proximity_alerts(state)

    def _update_heat_tracking(
        self,
        state: PositionState,
        current_epoch: Optional[int]
    ) -> None:
        """
        Update heat tracking (time in drawdown).

        Detects:
        - Entry into drawdown (heat starts)
        - Exit from drawdown (heat clears)
        - Heat level transitions (warn → alert → critical)

        Args:
            state: Position state
            current_epoch: Current Unix timestamp
        """
        # Check if in drawdown
        in_drawdown = self._is_in_drawdown(state)

        # Detect drawdown transitions
        if self._prev_in_drawdown is not None and self._prev_in_drawdown != in_drawdown:
            if in_drawdown:
                log.info("[VisualIndicators] Heat state: drawdown entered")
                self.heatEntered.emit()
            else:
                log.info("[VisualIndicators] Heat state: drawdown exited")
                self.heatExited.emit()

        # Store current state
        self._prev_in_drawdown = in_drawdown

        # Check heat levels if in drawdown and have current time
        if in_drawdown and current_epoch is not None and state.heat_start_epoch is not None:
            heat_duration = current_epoch - state.heat_start_epoch
            self._update_heat_level(heat_duration)

    def _is_in_drawdown(self, state: PositionState) -> bool:
        """
        Check if currently in drawdown.

        Args:
            state: Position state

        Returns:
            True if in drawdown (price unfavorable), False otherwise
        """
        if state.is_flat():
            return False

        if state.entry_price == 0 or state.last_price == 0:
            return False

        # Long: drawdown when price < entry
        # Short: drawdown when price > entry
        if state.is_long:
            return state.last_price < state.entry_price
        else:
            return state.last_price > state.entry_price

    def _update_heat_level(self, heat_duration: int) -> None:
        """
        Update heat level based on duration.

        Emits appropriate signals on level transitions.

        Args:
            heat_duration: Heat duration in seconds
        """
        # Determine heat level
        if heat_duration >= self.HEAT_ALERT_SOLID_SEC:
            new_level = "critical"
        elif heat_duration >= self.HEAT_ALERT_FLASH_SEC:
            new_level = "alert"
        elif heat_duration >= self.HEAT_WARN_SEC:
            new_level = "warn"
        else:
            new_level = None

        # Detect level transitions
        if self._prev_heat_level != new_level:
            if new_level == "warn" and self._prev_heat_level is None:
                log.warning("[VisualIndicators] Heat WARNING: 3:00m threshold reached")
                self.heatWarning.emit()
            elif new_level == "alert" and self._prev_heat_level in [None, "warn"]:
                log.warning("[VisualIndicators] Heat ALERT: 4:30m threshold reached (flashing)")
                self.heatAlert.emit()
            elif new_level == "critical" and self._prev_heat_level in [None, "warn", "alert"]:
                log.error("[VisualIndicators] Heat CRITICAL: 5:00m threshold reached")
                self.heatCritical.emit()

            self._prev_heat_level = new_level

    def _update_proximity_alerts(self, state: PositionState) -> None:
        """
        Update proximity alerts (price near stop).

        Detects when price is within 1 point of stop loss.

        Args:
            state: Position state
        """
        if state.is_flat() or state.stop_price is None or state.last_price == 0:
            # Clear proximity if conditions not met
            if self._prev_stop_near is True:
                self._prev_stop_near = False
                self.stopProximityClear.emit()
            return

        # Calculate distance to stop
        distance = abs(state.last_price - state.stop_price)
        near = distance <= self.STOP_PROXIMITY_POINTS

        # Detect transitions
        if self._prev_stop_near is not None and self._prev_stop_near != near:
            if near:
                log.warning(
                    "[VisualIndicators] Stop proximity detected -- flashing active",
                    distance=distance,
                    stop_price=state.stop_price,
                    last_price=state.last_price
                )
                self.stopProximity.emit()
            else:
                log.info(
                    "[VisualIndicators] Stop proximity cleared -- flashing off",
                    distance=distance
                )
                self.stopProximityClear.emit()

        # Store current state
        self._prev_stop_near = near

    def reset(self) -> None:
        """
        Reset all indicator states.

        Called when position is closed or mode switched.
        """
        self._prev_in_drawdown = None
        self._prev_stop_near = None
        self._prev_heat_level = None

        log.debug("[VisualIndicators] State reset")

    def get_heat_level(self, heat_duration: Optional[int]) -> Optional[str]:
        """
        Get heat level for a given duration.

        Args:
            heat_duration: Heat duration in seconds

        Returns:
            Heat level: None, "warn", "alert", or "critical"
        """
        if heat_duration is None:
            return None

        if heat_duration >= self.HEAT_ALERT_SOLID_SEC:
            return "critical"
        elif heat_duration >= self.HEAT_ALERT_FLASH_SEC:
            return "alert"
        elif heat_duration >= self.HEAT_WARN_SEC:
            return "warn"
        else:
            return None

    def get_heat_color(self, heat_duration: Optional[int]) -> str:
        """
        Get color for heat cell based on duration.

        Args:
            heat_duration: Heat duration in seconds

        Returns:
            Color name: "white", "yellow", or "red"
        """
        level = self.get_heat_level(heat_duration)

        if level is None:
            return "white"
        elif level == "warn":
            return "yellow"
        else:  # alert or critical
            return "red"

    def should_flash_heat(self, heat_duration: Optional[int]) -> bool:
        """
        Check if heat cell should flash.

        Args:
            heat_duration: Heat duration in seconds

        Returns:
            True if should flash, False otherwise
        """
        level = self.get_heat_level(heat_duration)
        return level in ["alert", "critical"]

    def should_flash_stop(self, state: PositionState) -> bool:
        """
        Check if stop cell should flash (proximity alert).

        Args:
            state: Position state

        Returns:
            True if should flash, False otherwise
        """
        if state.is_flat() or state.stop_price is None or state.last_price == 0:
            return False

        distance = abs(state.last_price - state.stop_price)
        return distance <= self.STOP_PROXIMITY_POINTS


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_heat_time(heat_duration: Optional[int]) -> str:
    """
    Format heat duration for display.

    Args:
        heat_duration: Heat duration in seconds

    Returns:
        Formatted string (e.g., "3:05", "4:30", "20s")
    """
    if heat_duration is None:
        return "--"

    if heat_duration < 60:
        return f"{heat_duration}s"

    minutes, seconds = divmod(heat_duration, 60)
    return f"{minutes}:{seconds:02d}"


def get_stop_proximity_color(state: PositionState) -> str:
    """
    Get color for stop cell based on proximity.

    Args:
        state: Position state

    Returns:
        Color name: "white" or "red"
    """
    if state.is_flat() or state.stop_price is None or state.last_price == 0:
        return "white"

    distance = abs(state.last_price - state.stop_price)

    if distance <= VisualIndicators.STOP_PROXIMITY_POINTS:
        return "red"
    else:
        return "white"
