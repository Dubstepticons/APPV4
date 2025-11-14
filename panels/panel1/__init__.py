"""
panels/panel1/__init__.py

Panel1 module - Equity chart display with balance tracking.

This module provides the decomposed Panel1 implementation with clear
separation of concerns and focused submodules.

Status: Complete (All 8 modules)

Public API:
    Panel1: Main panel class

Submodules:
    helpers: Formatting and color utilities
    masked_frame: Custom QFrame with rounded clipping
    pnl_calculator: PnL calculation functions
    timeframe_manager: Timeframe filtering and window calculations
    equity_state: Thread-safe equity curve management (CRITICAL)
    equity_chart: PyQtGraph rendering with animation
    hover_handler: Mouse hover and scrubbing
    panel1_main: Thin orchestrator (wires all modules together)

Usage:
    from panels.panel1 import Panel1

    panel = Panel1()
    panel.set_trading_mode(mode="SIM", account="Test1")
    panel.set_timeframe("1D")
    panel.set_account_balance(10000.0)
"""

from __future__ import annotations

from .panel1_main import Panel1

__all__ = ["Panel1"]
