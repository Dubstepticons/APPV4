"""
Panel2 Package

Live trading metrics panel with 3x5 grid layout.
Decomposed from monolithic panel2.py for modularity.

Architecture:
- helpers: Utility functions (fmt_time_human, sign_from_side, extract_symbol_display)
- state_manager: State persistence and mode management
- trade_handlers: Trade notifications and DTC message handling
- metrics_updater: Cell calculation engine
- live_panel: Main Panel2 class with UI and delegation

Usage:
    from panels.panel2 import Panel2

    panel = Panel2()
    panel.set_position(qty=2, entry_price=5800.25, is_long=True)
    panel.set_targets(target_price=5850.00, stop_price=5775.00)
"""

from panels.panel2.live_panel import Panel2

__all__ = ["Panel2"]
