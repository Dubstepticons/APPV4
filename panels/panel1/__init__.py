"""
panels/panel1/__init__.py

Panel1 module - Equity chart display with balance tracking.

This module provides the decomposed Panel1 implementation with clear
separation of concerns and focused submodules.

Status: Phase 1 Complete (Foundation modules)

Public API:
    Panel1: Main panel class (will be backwards compatible with original)

Submodules (Completed):
    helpers: Formatting and color utilities
    masked_frame: Custom QFrame with rounded clipping
    pnl_calculator: PnL calculation functions

Submodules (Planned):
    timeframe_manager: Timeframe filtering and window calculations
    equity_state: Thread-safe equity curve management
    equity_chart: PyQtGraph rendering with animation
    hover_handler: Mouse hover and scrubbing
    panel1_main: Thin orchestrator

Usage (when complete):
    from panels.panel1 import Panel1

    panel = Panel1()
    panel.set_trading_mode(mode="SIM", account="Test1")
    panel.set_timeframe("1D")
"""

from __future__ import annotations

# When fully implemented, this will import from panel1_main
# For now, maintain backwards compatibility with original
__all__ = ["Panel1"]

# Placeholder - will be replaced when panel1_main is complete
# from .panel1_main import Panel1
