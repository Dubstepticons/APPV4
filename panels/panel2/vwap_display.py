"""
panels/panel2/vwap_display.py

VWAP entry snapshot display module for Panel2.
Handles VWAP, POC, Cumulative Delta entry snapshots.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtWidgets

from config.theme import THEME
from widgets.metric_cell import MetricCell
from domain.position import Position
from utils.logger import get_logger

log = get_logger(__name__)


class VWAPDisplay:
    """
    Manages VWAP/POC/CumDelta entry snapshot display cells.

    Displays: Entry VWAP, Entry POC, Entry Cumulative Delta.
    """

    def __init__(self, grid_layout: QtWidgets.QGridLayout, row_offset: int = 0):
        """
        Initialize VWAP display cells.

        Args:
            grid_layout: Parent grid layout to add cells to
            row_offset: Starting row for VWAP cells
        """
        self.grid_layout = grid_layout
        self.row_offset = row_offset

        # Create cells
        self._create_cells()

    def _create_cells(self):
        """Create and add VWAP display cells to grid."""
        # Entry VWAP snapshot
        self.c_entry_vwap = MetricCell("Entry VWAP", "--")
        self.grid_layout.addWidget(self.c_entry_vwap, self.row_offset + 0, 0)

        # Entry POC (Point of Control) snapshot
        self.c_entry_poc = MetricCell("Entry POC", "--")
        self.grid_layout.addWidget(self.c_entry_poc, self.row_offset + 0, 1)

        # Entry Cumulative Delta snapshot
        self.c_entry_delta = MetricCell("Entry Delta", "--")
        self.grid_layout.addWidget(self.c_entry_delta, self.row_offset + 0, 2)

        log.info("VWAP display cells created")

    def update_entry_snapshots(self, position: Position):
        """
        Update entry snapshot cells from Position domain object.

        Args:
            position: Position domain object
        """
        if position.is_flat:
            self.clear()
            return

        # Entry VWAP
        if position.entry_vwap is not None:
            self.c_entry_vwap.set_value_text(f"{position.entry_vwap:.2f}")
        else:
            self.c_entry_vwap.set_value_text("--")

        # Entry POC
        if position.entry_poc is not None:
            self.c_entry_poc.set_value_text(f"{position.entry_poc:.2f}")
        else:
            self.c_entry_poc.set_value_text("--")

        # Entry Cumulative Delta
        if position.entry_cum_delta is not None:
            delta_display = self._format_delta(position.entry_cum_delta)
            self.c_entry_delta.set_value_text(delta_display)
        else:
            self.c_entry_delta.set_value_text("--")

    def update_live_values(self, vwap: Optional[float], poc: Optional[float], cum_delta: Optional[float]):
        """
        Update live VWAP/POC/Delta values (shown when no position).

        Args:
            vwap: Current VWAP
            poc: Current POC
            cum_delta: Current cumulative delta
        """
        # VWAP
        if vwap is not None:
            self.c_entry_vwap.set_value_text(f"{vwap:.2f}")
        else:
            self.c_entry_vwap.set_value_text("--")

        # POC
        if poc is not None:
            self.c_entry_poc.set_value_text(f"{poc:.2f}")
        else:
            self.c_entry_poc.set_value_text("--")

        # Cumulative Delta
        if cum_delta is not None:
            delta_display = self._format_delta(cum_delta)
            self.c_entry_delta.set_value_text(delta_display)
        else:
            self.c_entry_delta.set_value_text("--")

    def clear(self):
        """Clear all VWAP display cells."""
        self.c_entry_vwap.set_value_text("--")
        self.c_entry_poc.set_value_text("--")
        self.c_entry_delta.set_value_text("--")

    @staticmethod
    def _format_delta(delta: float) -> str:
        """Format cumulative delta with thousands separator and sign."""
        if delta >= 0:
            return f"+{delta:,.0f}"
        else:
            return f"{delta:,.0f}"
