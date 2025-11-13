"""
panels/panel2/position_display.py

Position information display module for Panel2.
Handles entry qty, price, time, duration, heat timer cells.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtWidgets

from config.theme import THEME
from widgets.metric_cell import MetricCell
from domain.position import Position
from utils.logger import get_logger

log = get_logger(__name__)


class PositionDisplay:
    """
    Manages position information display cells.

    Displays: Entry qty, entry price, entry time, duration, heat timer.
    """

    def __init__(self, grid_layout: QtWidgets.QGridLayout, row_offset: int = 0):
        """
        Initialize position display cells.

        Args:
            grid_layout: Parent grid layout to add cells to
            row_offset: Starting row for position cells
        """
        self.grid_layout = grid_layout
        self.row_offset = row_offset

        # Heat timer state (UI-specific, separate from Position)
        self.heat_start_epoch: Optional[int] = None

        # Create cells
        self._create_cells()

    def _create_cells(self):
        """Create and add position display cells to grid."""
        # Entry quantity with pill
        self.c_entry_qty = MetricCell("Entry Qty", "--")
        self.grid_layout.addWidget(self.c_entry_qty, self.row_offset + 0, 0)

        # Entry price
        self.c_entry_price = MetricCell("Entry Price", "--")
        self.grid_layout.addWidget(self.c_entry_price, self.row_offset + 0, 1)

        # Entry time
        self.c_entry_time = MetricCell("Entry Time", "--")
        self.grid_layout.addWidget(self.c_entry_time, self.row_offset + 0, 2)

        # Duration in position
        self.c_duration = MetricCell("Duration", "--")
        self.grid_layout.addWidget(self.c_duration, self.row_offset + 1, 0)

        # Heat timer
        self.c_heat = MetricCell("Heat", "--")
        self.grid_layout.addWidget(self.c_heat, self.row_offset + 1, 1)

        log.info("position_display.initialized", msg="Position display cells created")

    def update_from_position(self, position: Position):
        """
        Update all position cells from Position domain object.

        Args:
            position: Position domain object
        """
        if position.is_flat:
            self.clear()
            return

        # Entry qty with side pill
        side_text = "L" if position.is_long else "S"
        qty_display = f"{position.qty_abs} {side_text}"
        self.c_entry_qty.set_value_text(qty_display)

        # Entry price
        self.c_entry_price.set_value_text(f"{position.entry_price:.2f}")

        # Entry time
        entry_time_str = position.entry_time.strftime("%H:%M:%S")
        self.c_entry_time.set_value_text(entry_time_str)

        # Side pill color
        self.refresh_pill_colors(position.is_long)

    def update_time_and_heat(self, position: Position, current_epoch: int):
        """
        Update duration and heat timer cells.

        Args:
            position: Position domain object
            current_epoch: Current time as epoch seconds
        """
        if position.is_flat:
            self.c_duration.set_value_text("--")
            self.c_heat.set_value_text("--")
            return

        # Duration (from Position domain object)
        duration_sec = position.duration_seconds
        if duration_sec is not None:
            self.c_duration.set_value_text(self._fmt_time_human(int(duration_sec)))
        else:
            self.c_duration.set_value_text("--")

        # Heat timer (UI-specific state)
        if self.heat_start_epoch is not None:
            heat_sec = current_epoch - self.heat_start_epoch
            self.c_heat.set_value_text(self._fmt_time_human(heat_sec))
            # TODO: Add heat warning colors (3min yellow, 4:30 flash, 5min red)
        else:
            self.c_heat.set_value_text("--")

    def refresh_pill_colors(self, is_long: Optional[bool]):
        """
        Update entry qty pill color based on position side.

        Args:
            is_long: True=long, False=short, None=flat
        """
        if is_long is True:
            pill_color = THEME.get("pnl_pos_color", "#10B981")  # Green for long
        elif is_long is False:
            pill_color = THEME.get("pnl_neg_color", "#EF4444")  # Red for short
        else:
            pill_color = THEME.get("text_dim", "#5B6C7A")  # Dim for flat

        self.c_entry_qty.set_pill_color(pill_color)

    def has_active_position(self, position: Position) -> bool:
        """
        Check if there's an active position.

        Args:
            position: Position domain object

        Returns:
            True if position is not flat
        """
        return not position.is_flat

    def clear(self):
        """Clear all position display cells."""
        self.c_entry_qty.set_value_text("--")
        self.c_entry_price.set_value_text("--")
        self.c_entry_time.set_value_text("--")
        self.c_duration.set_value_text("--")
        self.c_heat.set_value_text("--")
        self.refresh_pill_colors(None)

    @staticmethod
    def _fmt_time_human(seconds: int) -> str:
        """Format time like '20s', '1:20', '10:00' (no 's' suffix for minutes)."""
        if seconds < 60:
            return f"{seconds}s"
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"
