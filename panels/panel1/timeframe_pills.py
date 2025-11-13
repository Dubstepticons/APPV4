"""
panels/panel1/timeframe_pills.py

Timeframe pills module for Panel1.
Handles timeframe pill buttons and LIVE dot indicator.
"""

from __future__ import annotations

from PyQt6 import QtCore
from utils.logger import get_logger

log = get_logger(__name__)


class TimeframePills(QtCore.QObject):
    """
    Manages timeframe pill buttons.

    Displays: LIVE, 1D, 1W, 1M, 3M, YTD pills with active state.
    """

    timeframeChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize timeframe pills."""
        super().__init__(parent)

        log.info("timeframe_pills.template", msg="TimeframePills template ready (extraction pending)")

    def set_timeframe(self, tf: str) -> None:
        """Set active timeframe pill."""
        pass

    def update_live_dot(self, pulsing: bool) -> None:
        """Update LIVE dot pulsing state."""
        pass
