"""
panels/panel2/pnl_display.py

P&L metrics display module for Panel2.
Handles unrealized P&L, MAE, MFE, efficiency, R-multiple, risk cells.
"""

from __future__ import annotations

from typing import Optional
from PyQt6 import QtWidgets

from config.theme import THEME
from widgets.metric_cell import MetricCell
from domain.position import Position
from services.trade_constants import COMM_PER_CONTRACT, DOLLARS_PER_POINT
from utils.logger import get_logger

log = get_logger(__name__)


class PnLDisplay:
    """
    Manages P&L and risk metrics display cells.

    Displays: Unrealized P&L, MAE, MFE, Efficiency, R-multiple, Planned Risk.
    """

    def __init__(self, grid_layout: QtWidgets.QGridLayout, row_offset: int = 0):
        """
        Initialize P&L display cells.

        Args:
            grid_layout: Parent grid layout to add cells to
            row_offset: Starting row for P&L cells
        """
        self.grid_layout = grid_layout
        self.row_offset = row_offset

        # Create cells
        self._create_cells()

    def _create_cells(self):
        """Create and add P&L display cells to grid."""
        # Unrealized P&L (gross)
        self.c_pnl = MetricCell("P&L", "$0.00")
        self.grid_layout.addWidget(self.c_pnl, self.row_offset + 0, 0)

        # Maximum Adverse Excursion
        self.c_mae = MetricCell("MAE", "--")
        self.grid_layout.addWidget(self.c_mae, self.row_offset + 0, 1)

        # Maximum Favorable Excursion
        self.c_mfe = MetricCell("MFE", "--")
        self.grid_layout.addWidget(self.c_mfe, self.row_offset + 0, 2)

        # Trade efficiency (capture ratio)
        self.c_efficiency = MetricCell("Efficiency", "--")
        self.grid_layout.addWidget(self.c_efficiency, self.row_offset + 1, 0)

        # R-multiple (risk-adjusted return)
        self.c_rmult = MetricCell("R-Multiple", "--")
        self.grid_layout.addWidget(self.c_rmult, self.row_offset + 1, 1)

        # Planned risk (stop distance + commission)
        self.c_risk = MetricCell("Risk", "--")
        self.grid_layout.addWidget(self.c_risk, self.row_offset + 1, 2)

        log.info("pnl_display.initialized", msg="P&L display cells created")

    def update_from_position(self, position: Position, last_price: Optional[float]):
        """
        Update all P&L cells from Position domain object and current price.

        Args:
            position: Position domain object
            last_price: Current market price
        """
        if position.is_flat or last_price is None:
            self.clear()
            return

        # Unrealized P&L (gross)
        gross_pnl = position.unrealized_pnl(last_price)
        self._update_pnl_cell(gross_pnl)

        # MAE/MFE
        mae = position.mae()
        mfe = position.mfe()
        if mae is not None:
            self.c_mae.set_value_text(f"${mae:,.2f}")
            self.c_mae.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))
        else:
            self.c_mae.set_value_text("--")

        if mfe is not None:
            self.c_mfe.set_value_text(f"${mfe:,.2f}")
            self.c_mfe.set_value_color(THEME.get("pnl_pos_color", "#10B981"))
        else:
            self.c_mfe.set_value_text("--")

        # Efficiency (capture ratio)
        efficiency = position.efficiency(last_price)
        if efficiency is not None:
            pct = efficiency * 100
            self.c_efficiency.set_value_text(f"{pct:.1f}%")
            # Color based on efficiency: >70% green, 40-70% yellow, <40% red
            if efficiency > 0.7:
                color = THEME.get("pnl_pos_color", "#10B981")
            elif efficiency > 0.4:
                color = THEME.get("text_normal", "#D1D5DB")
            else:
                color = THEME.get("pnl_neg_color", "#EF4444")
            self.c_efficiency.set_value_color(color)
        else:
            self.c_efficiency.set_value_text("--")
            self.c_efficiency.set_value_color(THEME.get("text_dim", "#5B6C7A"))

        # R-multiple
        r_multiple = position.r_multiple(last_price)
        if r_multiple is not None:
            self.c_rmult.set_value_text(f"{r_multiple:.2f}R")
            # Color: >0 green, <0 red
            color = THEME.get("pnl_pos_color", "#10B981") if r_multiple > 0 else THEME.get("pnl_neg_color", "#EF4444")
            self.c_rmult.set_value_color(color)
        else:
            self.c_rmult.set_value_text("--")
            self.c_rmult.set_value_color(THEME.get("text_dim", "#5B6C7A"))

        # Planned risk (from stop)
        self._update_risk_cell(position)

    def _update_pnl_cell(self, gross_pnl: float):
        """Update P&L cell with gross P&L value and color."""
        self.c_pnl.set_value_text(f"${gross_pnl:,.2f}")

        # Color based on P&L value
        if abs(gross_pnl) < 1:  # Essentially flat
            color = THEME.get("text_dim", "#5B6C7A")
        elif gross_pnl > 0:
            color = THEME.get("pnl_pos_color", "#10B981")
        else:
            color = THEME.get("pnl_neg_color", "#EF4444")

        self.c_pnl.set_value_color(color)

    def _update_risk_cell(self, position: Position):
        """Update planned risk cell (stop distance + commission)."""
        if position.stop_price is None:
            self.c_risk.set_value_text("--")
            self.c_risk.set_value_color(THEME.get("text_dim", "#5B6C7A"))
            return

        # Calculate planned risk: |entry - stop| * $50/point * qty + commission
        dist_pts = abs(position.entry_price - position.stop_price)
        dollars = dist_pts * DOLLARS_PER_POINT * position.qty_abs
        comm = COMM_PER_CONTRACT * position.qty_abs
        planned_risk = dollars + comm

        self.c_risk.set_value_text(f"${planned_risk:,.2f}")
        self.c_risk.set_value_color(THEME.get("pnl_neg_color", "#EF4444"))  # Always red (it's risk)

    def clear(self):
        """Clear all P&L display cells."""
        self.c_pnl.set_value_text("$0.00")
        self.c_pnl.set_value_color(THEME.get("text_dim", "#5B6C7A"))
        self.c_mae.set_value_text("--")
        self.c_mfe.set_value_text("--")
        self.c_efficiency.set_value_text("--")
        self.c_rmult.set_value_text("--")
        self.c_risk.set_value_text("--")
