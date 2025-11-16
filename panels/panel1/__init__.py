"""
Panel1 Package

Balance/Investing panel with equity curve graph and PnL display.

Decomposed from monolithic panels/panel1.py (1784 lines) into modular components.

Structure:
- masked_frame.py: Rounded frame widget for graph container
- balance_panel.py: Main Panel1 class
- equity_graph.py: Graph initialization and plotting
- pnl_manager.py: PnL calculations and equity loading
- hover_handler.py: Mouse hover and crosshair interactions
- animations.py: Pulse effects and glow animations

Usage:
    from panels.panel1 import Panel1, MaskedFrame

    panel = Panel1()
    panel.set_account_balance(10500.00)
"""

from panels.panel1.balance_panel import Panel1
from panels.panel1.masked_frame import MaskedFrame

__all__ = ["Panel1", "MaskedFrame"]
