"""
panels/panel1/header_display.py

P&L header display module for Panel1.
Handles P&L value, percentage, timeframe display in header.
"""

from __future__ import annotations

from typing import Optional
from utils.logger import get_logger

log = get_logger(__name__)


class HeaderDisplay:
    """
    Manages P&L header display.

    Displays: P&L value, P&L percentage, timeframe label.
    """

    def __init__(self, header_widget):
        """Initialize P&L header display."""
        self.header_widget = header_widget

        log.info("header_display.template", msg="HeaderDisplay template ready (extraction pending)")

    def set_pnl_for_timeframe(self, pnl_value: float, pnl_pct: float, up: Optional[bool]) -> None:
        """Update P&L display for current timeframe."""
        pass

    def update_for_hover(self, x: float, y: float) -> None:
        """Update header for crosshair hover."""
        pass
