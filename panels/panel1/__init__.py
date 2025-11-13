"""
panels/panel1/__init__.py

Panel1 - Balance & Equity with modular architecture.

Modular structure:
- balance_display.py - Account balance, connection status, mode badge
- equity_graph.py - Equity curve graph with PyQtGraph
- header_display.py - P&L header display
- timeframe_pills.py - Timeframe pill buttons
- database_integration.py - Equity curve loading from database

This file (__init__.py) contains the main Panel1 class that orchestrates the modules.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtCore, QtWidgets

from utils.logger import get_logger
from utils.theme_mixin import ThemeAwareMixin

log = get_logger(__name__)


class Panel1(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Panel 1 -- Balance & Equity with modular architecture.

    Template structure ready for future extraction from panels/panel1.py
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        log.info("panel1.module_template", msg="Panel1 modular template initialized (extraction pending)")

    def set_account_balance(self, balance: Optional[float]) -> None:
        """Update account balance display."""
        pass

    def update_equity_series_from_balance(self, balance: Optional[float], mode: Optional[str] = None) -> None:
        """Add equity point from balance update."""
        pass

    def set_trading_mode(self, mode: str, account: Optional[str] = None) -> None:
        """Switch trading mode (SIM/LIVE/DEBUG)."""
        pass

    def set_timeframe(self, tf: str) -> None:
        """Set active timeframe for equity graph."""
        pass

    def refresh(self) -> None:
        """Force refresh of all displays."""
        pass
