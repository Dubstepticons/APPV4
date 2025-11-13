"""
panels/panel2/bracket_orders.py

Bracket order management module for Panel2.
Handles target and stop price display and management.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtWidgets

from config.theme import THEME
from widgets.metric_cell import MetricCell
from domain.position import Position
from utils.logger import get_logger

log = get_logger(__name__)


class BracketOrders:
    """
    Manages bracket order (target/stop) display cells.

    Displays: Target price, Stop price.
    Note: Risk is displayed in PnLDisplay module.
    """

    def __init__(self, grid_layout: QtWidgets.QGridLayout, row_offset: int = 0):
        """
        Initialize bracket order display cells.

        Args:
            grid_layout: Parent grid layout to add cells to
            row_offset: Starting row for bracket cells
        """
        self.grid_layout = grid_layout
        self.row_offset = row_offset

        # Create cells
        self._create_cells()

    def _create_cells(self):
        """Create and add bracket order display cells to grid."""
        # Target price
        self.c_target = MetricCell("Target", "--")
        self.grid_layout.addWidget(self.c_target, self.row_offset + 0, 0)

        # Stop price
        self.c_stop = MetricCell("Stop", "--")
        self.grid_layout.addWidget(self.c_stop, self.row_offset + 0, 1)

        log.info("bracket_orders.initialized", msg="Bracket order cells created")

    def update_from_position(self, position: Position):
        """
        Update bracket cells from Position domain object.

        Args:
            position: Position domain object
        """
        if position.is_flat:
            self.clear()
            return

        # Target price
        if position.target_price is not None and position.target_price > 0:
            self.c_target.set_value_text(f"{position.target_price:.2f}")
            self.c_target.set_value_color(THEME.get("pnl_pos_color", "#10B981"))  # Green
        else:
            self.c_target.set_value_text("--")
            self.c_target.set_value_color(THEME.get("text_dim", "#5B6C7A"))

        # Stop price
        if position.stop_price is not None and position.stop_price > 0:
            self.c_stop.set_value_text(f"{position.stop_price:.2f}")
            self.c_stop.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))  # Red
        else:
            self.c_stop.set_value_text("--")
            self.c_stop.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def set_targets(self, target: Optional[float], stop: Optional[float]):
        """
        Manually set target and stop prices.

        Args:
            target: Target price (or None)
            stop: Stop price (or None)
        """
        # Target
        if target is not None and target > 0:
            self.c_target.set_value_text(f"{target:.2f}")
            self.c_target.set_value_color(THEME.get("pnl_pos_color", "#10B981"))
        else:
            self.c_target.set_value_text("--")
            self.c_target.set_value_color(THEME.get("text_dim", "#5B6C7A"))

        # Stop
        if stop is not None and stop > 0:
            self.c_stop.set_value_text(f"{stop:.2f}")
            self.c_stop.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
        else:
            self.c_stop.set_value_text("--")
            self.c_stop.set_value_color(THEME.get("text_dim", "#5B6C7A"))

    def clear(self):
        """Clear all bracket order cells."""
        self.c_target.set_value_text("--")
        self.c_target.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        self.c_stop.set_value_text("--")
        self.c_stop.set_value_color(THEME.get("text_dim", "#5B6C7A"))
