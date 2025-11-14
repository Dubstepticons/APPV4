"""
panels/panel2/__init__.py

Panel2 module - Live trading metrics and position display.

This module provides the decomposed Panel2 implementation with clear
separation of concerns and focused submodules.

Public API:
    Panel2: Main panel class (backwards compatible with original)

Submodules:
    position_state: Immutable position state snapshots
    metrics_calculator: Pure P&L calculation functions
    csv_feed_handler: Market data CSV polling
    state_persistence: JSON/DB serialization
    visual_indicators: Heat timers and proximity alerts
    position_display: 3x5 grid rendering
    order_flow: DTC order handling
    panel2_main: Thin orchestrator

Usage:
    from panels.panel2 import Panel2

    panel = Panel2()
    panel.on_order_update(order_payload)
"""

from __future__ import annotations

# When fully implemented, this will import from panel2_main
# For now, maintain backwards compatibility
__all__ = ["Panel2"]

# Placeholder - will be replaced when implementation is complete
# from .panel2_main import Panel2
