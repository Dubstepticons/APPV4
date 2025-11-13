"""
panels/panel1/balance_display.py

Balance display module for Panel1.
Handles account balance, connection status, mode badge display.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtWidgets

from config.theme import THEME
from utils.logger import get_logger

log = get_logger(__name__)


class BalanceDisplay:
    """
    Manages balance, connection status, and mode badge display.

    Displays: Account balance, connection icon, mode badge (SIM/LIVE/DEBUG).
    """

    def __init__(self, header_widget: QtWidgets.QWidget):
        """
        Initialize balance display.

        Args:
            header_widget: Parent header widget to add displays to
        """
        self.header_widget = header_widget

        log.info("balance_display.template", msg="BalanceDisplay template ready (extraction pending)")

    def set_account_balance(self, balance: Optional[float]) -> None:
        """Update account balance display."""
        pass

    def set_connection_status(self, connected: bool) -> None:
        """Update connection icon."""
        pass

    def update_badge_style(self, mode: str) -> None:
        """Update mode badge styling (SIM/LIVE/DEBUG)."""
        pass
