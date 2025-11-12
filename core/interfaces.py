"""
Core Interfaces - Dependency Inversion Layer

This module defines interfaces (protocols) for panels and components,
allowing core modules to depend on abstractions instead of concrete implementations.

This breaks the circular dependency: core → interfaces ← panels
"""

from typing import Protocol, runtime_checkable
from PyQt6.QtCore import QObject


@runtime_checkable
class BalancePanel(Protocol):
    """Interface for balance/equity display panel (Panel1)"""

    def set_account_balance(self, balance: float) -> None:
        """Update displayed account balance"""
        ...

    def set_account(self, account: str) -> None:
        """Update current account identifier"""
        ...

    def set_trading_mode(self, mode: str, account: str) -> None:
        """Update trading mode (SIM/LIVE/DEBUG) and account"""
        ...


@runtime_checkable
class TradingPanel(Protocol):
    """Interface for live trading panel (Panel2)"""

    def on_position_update(self, msg: dict) -> None:
        """Handle position update message from DTC"""
        ...

    def on_order_update(self, msg: dict) -> None:
        """Handle order update message from DTC"""
        ...

    def notify_trade_closed(self, symbol: str, pnl: float, mode: str) -> None:
        """Notify that a trade was closed"""
        ...


@runtime_checkable
class StatsPanel(Protocol):
    """Interface for statistics panel (Panel3)"""

    def refresh_stats(self) -> None:
        """Refresh displayed statistics"""
        ...

    def on_mode_changed(self, mode: str) -> None:
        """Handle trading mode change"""
        ...


@runtime_checkable
class DTCClient(Protocol):
    """Interface for DTC protocol client"""

    def submit_order(self, symbol: str, qty: int, order_type: str, price: float | None = None) -> bool:
        """Submit an order to the trading server"""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        ...

    def disconnect(self) -> None:
        """Disconnect from DTC server"""
        ...


# Type aliases for clarity
PanelRegistry = dict[str, QObject]  # Maps panel name to instance
