"""
panels/panel1/equity_graph.py

Equity graph module for Panel1.
Handles PyQtGraph equity curve plotting, timeframe windowing, hover crosshairs.
"""

from __future__ import annotations

from typing import Sequence, Iterable
from utils.logger import get_logger

log = get_logger(__name__)


class EquityGraph:
    """
    Manages equity curve graph with PyQtGraph.

    Responsibilities:
    - Equity curve plotting
    - Timeframe windowing (LIVE, 1D, 1W, 1M, 3M, YTD)
    - Auto-ranging
    - Hover crosshairs
    - LIVE pulse animation
    """

    def __init__(self, container_widget):
        """Initialize equity graph."""
        self.container_widget = container_widget

        log.info("equity_graph.template", msg="EquityGraph template ready (extraction pending)")

    def set_equity_series(self, points: Iterable[tuple[float, float]]) -> None:
        """Set equity data points."""
        pass

    def update_equity_series(self, xs: Sequence[float], ys: Sequence[float]) -> None:
        """Update equity graph data."""
        pass

    def set_timeframe(self, tf: str) -> None:
        """Set active timeframe for graph windowing."""
        pass
