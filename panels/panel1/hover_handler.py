"""
panels/panel1/hover_handler.py

Mouse hover and scrubbing interactions for Panel1 equity chart.

This module handles:
- Hover line rendering (vertical line following mouse)
- Timestamp text overlay
- Binary search for nearest data point
- PnL calculation for hovered point vs baseline
- Cursor leave detection

Architecture:
- Stateful (manages hover state, current position)
- Callback-based (calls update callbacks instead of emitting signals)
- Timeframe-aware (different baseline calculations per timeframe)

Usage:
    from panels.panel1.hover_handler import HoverHandler

    handler = HoverHandler(
        plot_widget=plot,
        view_box=vb,
        on_balance_update=lambda bal: ...,
        on_pnl_update=lambda pnl_text, color: ...
    )

    handler.init_hover_elements()

    # Handler automatically connects to mouse events
    # Callbacks are invoked when hover updates occur
"""

from __future__ import annotations

import bisect
from datetime import datetime
from typing import Any, Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from config.theme import THEME, ColorTheme
from panels.panel1.helpers import fmt_money, pnl_color
from utils.logger import get_logger
from utils.theme_helpers import normalize_color

log = get_logger(__name__)

# Try to import pyqtgraph (may not be available in all environments)
try:
    import pyqtgraph as pg  # type: ignore
    HAS_PYQTGRAPH = True
except ImportError:
    pg = None
    HAS_PYQTGRAPH = False
    log.warning("pyqtgraph not available - hover functionality disabled")


class HoverHandler(QtCore.QObject):
    """
    Handles mouse hover and scrubbing interactions for equity chart.

    Features:
    - Vertical hover line (85% height)
    - Timestamp text overlay
    - Binary search for nearest point
    - PnL calculation vs baseline
    - Cursor leave detection
    """

    def __init__(
        self,
        plot_widget: Any,  # PlotWidget
        view_box: Any,  # ViewBox
        on_balance_update: Callable[[str], None],
        on_pnl_update: Callable[[str, str], None],
        parent: Optional[QtCore.QObject] = None
    ):
        """
        Initialize hover handler.

        Args:
            plot_widget: PyQtGraph PlotWidget
            view_box: PyQtGraph ViewBox
            on_balance_update: Callback for balance updates (args: formatted_balance)
            on_pnl_update: Callback for PnL updates (args: pnl_text, color)
            parent: Parent QObject (optional)
        """
        super().__init__(parent)

        self._plot = plot_widget
        self._vb = view_box

        # Callbacks
        self._on_balance_update = on_balance_update
        self._on_pnl_update = on_pnl_update

        # Hover elements
        self._hover_seg: Optional[QtWidgets.QGraphicsLineItem] = None
        self._hover_text: Optional[Any] = None  # pg.TextItem

        # State
        self._hovering: bool = False
        self._scrub_x: Optional[float] = None

        # Data (set externally)
        self._current_points: list[tuple[float, float]] = []
        self._current_timeframe: str = "LIVE"

        # Timeframe configurations (for baseline calculations)
        self._tf_configs = {
            "LIVE": {"window_sec": 3600},
            "1D": {"window_sec": 86400},
            "1W": {"window_sec": 604800},
            "1M": {"window_sec": 2592000},
            "3M": {"window_sec": 7776000},
            "YTD": {"window_sec": None},
        }

    def init_hover_elements(self) -> None:
        """
        Create hover line and timestamp text.

        Called after plot widget is initialized and attached to layout.
        """
        if not HAS_PYQTGRAPH or self._plot is None:
            log.warning("Cannot init hover elements - pyqtgraph not available")
            return

        try:
            # Hover line (85% height, vertical)
            self._hover_seg = QtWidgets.QGraphicsLineItem()
            self._hover_seg.setPen(pg.mkPen(THEME.get("fg_muted", "#C8CDD3"), width=1))
            self._hover_seg.setZValue(100)
            self._hover_seg.setVisible(False)
            self._plot.getPlotItem().scene().addItem(self._hover_seg)

            # Timestamp text (centered above line)
            text_hex = normalize_color(THEME.get("ink", "#E5E7EB"))
            text_qcolor = QtGui.QColor(text_hex)
            self._hover_text = pg.TextItem("", color=text_qcolor, anchor=(0.5, 1.0))

            # Set font to match theme
            font = QtGui.QFont(THEME.get("font_family", "Inter, sans-serif"))
            font.setPixelSize(int(THEME.get("font_size", 16)))
            font.setWeight(int(THEME.get("font_weight", 500)))
            self._hover_text.setFont(font)
            self._hover_text.setZValue(101)
            self._hover_text.setVisible(False)
            self._plot.addItem(self._hover_text)

            # Connect mouse move signal
            self._plot.scene().sigMouseMoved.connect(self._on_mouse_move)

            # Install event filter for cursor leave detection
            self._plot.viewport().installEventFilter(self)

        except Exception as e:
            log.error(f"Error initializing hover elements: {e}")
            import traceback
            traceback.print_exc()
            self._hover_seg = None
            self._hover_text = None

    def set_data(self, points: list[tuple[float, float]], timeframe: str) -> None:
        """
        Update hover handler with new data.

        Args:
            points: List of (timestamp, balance) tuples (filtered for timeframe)
            timeframe: Current timeframe (LIVE, 1D, 1W, 1M, 3M, YTD)
        """
        self._current_points = list(points)
        self._current_timeframe = timeframe

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """
        Hide hover artifacts when cursor leaves plot viewport.

        Args:
            obj: Object that received event
            event: Event

        Returns:
            True if event handled, False otherwise
        """
        try:
            if (
                self._plot
                and obj == self._plot.viewport()
                and event.type() == QtCore.QEvent.Type.Leave
            ):
                # Hide hover elements
                if self._hover_seg:
                    self._hover_seg.setVisible(False)
                if self._hover_text:
                    self._hover_text.setVisible(False)

                # Reset state
                self._hovering = False
                self._scrub_x = None

                # Restore normal header (not hovering)
                # Callback will restore original balance/PnL display
                return True

        except Exception as e:
            log.debug(f"eventFilter error: {e}")

        return super().eventFilter(obj, event)

    def _on_mouse_move(self, pos: QtCore.QPointF) -> None:
        """
        Handle mouse movement over chart.

        Updates hover line position, timestamp text, and header display.

        Args:
            pos: Mouse position in scene coordinates
        """
        if self._plot is None or self._vb is None:
            return

        if not self._current_points:
            # No data - hide hover elements
            if self._hover_seg:
                self._hover_seg.setVisible(False)
            if self._hover_text:
                self._hover_text.setVisible(False)
            return

        # Check if mouse is within plot bounds
        scene_rect = self._plot.sceneBoundingRect()
        if not scene_rect.contains(pos):
            if self._hover_seg:
                self._hover_seg.setVisible(False)
            if self._hover_text:
                self._hover_text.setVisible(False)
            return

        # Map scene position to view coordinates
        vb = self._vb
        mp = vb.mapSceneToView(pos)
        x_mouse = float(mp.x())

        # Clamp to visible range
        xr, yr = vb.viewRange()
        if x_mouse < xr[0] or x_mouse > xr[1]:
            return

        # Extract x and y values
        xs = [p[0] for p in self._current_points]
        ys = [p[1] for p in self._current_points]

        # Find nearest actual data point (binary search)
        idx = self._find_nearest_index(xs, x_mouse)
        if idx is None:
            return

        x = float(xs[idx])
        y = float(ys[idx])

        # Update state
        self._hovering = True
        self._scrub_x = x

        # Update hover line (85% height, vertical)
        if self._hover_seg:
            y_min, y_max = yr[0], yr[1]
            y_span = y_max - y_min
            frac = 0.85
            y_top = y_min + y_span * frac

            p0 = vb.mapViewToScene(QtCore.QPointF(x, y_min))
            p1 = vb.mapViewToScene(QtCore.QPointF(x, y_top))
            self._hover_seg.setLine(p0.x(), p0.y(), p1.x(), p1.y())

            if not self._hover_seg.isVisible():
                self._hover_seg.setVisible(True)

        # Update timestamp text
        if self._hover_text:
            dt = datetime.fromtimestamp(x)

            # Format timestamp based on timeframe
            if self._current_timeframe in ("LIVE", "1D"):
                t = dt.strftime("%I:%M %p").lstrip("0")
            elif self._current_timeframe in ("1W", "1M"):
                t = dt.strftime("%b %d, %I:%M %p").replace(" 0", " ").lstrip("0")
            else:
                t = dt.strftime("%b %d, %Y").replace(" 0", " ")

            # Position timestamp at top of chart (92% height)
            y_min, y_max = yr[0], yr[1]
            y_span = y_max - y_min
            y_top = y_min + y_span * 0.92

            # Clamp x position to avoid text going off screen
            pad = (xr[1] - xr[0]) * 0.02
            x_clamped = max(xr[0] + pad, min(xr[1] - pad, x))

            self._hover_text.setText(t)
            self._hover_text.setPos(x_clamped, y_top)

            if not self._hover_text.isVisible():
                self._hover_text.setVisible(True)

        # Update header (balance and PnL)
        self._update_header_for_hover(x, y)

    def _update_header_for_hover(self, x: float, y: float) -> None:
        """
        Update balance and PnL display for hovered point.

        Calculates PnL vs baseline for current timeframe.

        Args:
            x: Timestamp of hovered point
            y: Balance of hovered point
        """
        # Update balance display
        self._on_balance_update(fmt_money(y))

        # Get baseline from full equity history (for PnL calculation)
        baseline = self._get_baseline_for_timeframe(x)
        if baseline is None:
            # No baseline - show placeholder
            self._on_pnl_update("--  --", THEME.get("fg_muted", "#C8CDD3"))
            return

        # Calculate PnL
        pnl = y - baseline
        if abs(pnl) < 0.01:
            # Neutral (essentially zero)
            self._on_pnl_update("$0.00 (0.00%)", THEME.get("fg_muted", "#C8CDD3"))
            return

        # Calculate percentage
        pct = 0.0 if baseline == 0 else (pnl / baseline) * 100.0
        up = pnl > 0

        # Format PnL text
        tri = "+" if up else "-"
        pnl_text = f"{tri} ${abs(pnl):,.2f} ({abs(pct):.2f}%)"

        # Get color
        col = pnl_color(up)

        # Update via callback
        self._on_pnl_update(pnl_text, col)

    def _get_baseline_for_timeframe(self, at_time: float) -> Optional[float]:
        """
        Get baseline balance for PnL calculation based on timeframe.

        Uses binary search to find balance at start of timeframe window.

        Args:
            at_time: Timestamp of hovered point

        Returns:
            Baseline balance, or None if no data
        """
        if not self._current_points:
            return None

        xs = [p[0] for p in self._current_points]
        ys = [p[1] for p in self._current_points]

        # Calculate baseline time based on timeframe
        if self._current_timeframe == "LIVE":
            baseline_time = at_time - 3600  # 1 hour ago

        elif self._current_timeframe == "1D":
            # Start of day (midnight)
            dt = datetime.fromtimestamp(at_time)
            baseline_time = datetime(dt.year, dt.month, dt.day).timestamp()

        elif self._current_timeframe == "1W":
            baseline_time = at_time - 604800  # 1 week ago

        elif self._current_timeframe == "1M":
            baseline_time = at_time - 2592000  # 30 days ago

        elif self._current_timeframe == "3M":
            baseline_time = at_time - 7776000  # 90 days ago

        else:  # YTD
            # Start of year (January 1)
            dt = datetime.fromtimestamp(at_time)
            baseline_time = datetime(dt.year, 1, 1).timestamp()

        # Binary search for point at or before baseline_time
        i = bisect.bisect_right(xs, baseline_time)

        if i == 0:
            # No points before baseline - use first point
            return ys[0]

        # Return balance at or before baseline_time
        return ys[i - 1]

    def _find_nearest_index(
        self,
        xs: list[float],
        target_x: float
    ) -> Optional[int]:
        """
        Find index of nearest x value using binary search.

        Args:
            xs: Sorted list of x values (timestamps)
            target_x: Target x value to find

        Returns:
            Index of nearest point, or None if list is empty
        """
        if not xs:
            return None

        # Binary search for insertion point
        i = bisect.bisect_right(xs, target_x)

        if i == 0:
            # Before first element
            return 0

        if i >= len(xs):
            # After last element
            return len(xs) - 1

        # Choose closest of i and i-1
        if abs(xs[i] - target_x) < abs(xs[i - 1] - target_x):
            return i
        else:
            return i - 1

    def is_hovering(self) -> bool:
        """
        Check if currently hovering over chart.

        Returns:
            True if hovering, False otherwise
        """
        return self._hovering

    def get_scrub_position(self) -> Optional[float]:
        """
        Get current scrub position (x coordinate).

        Returns:
            Scrub x position, or None if not hovering
        """
        return self._scrub_x
