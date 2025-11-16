"""
panels/panel1/equity_chart.py

PyQtGraph equity chart rendering with animation.

This module handles:
- PlotWidget creation and styling
- Line, trails, and glow rendering
- Animated endpoint with breathing effect
- Sonar ripple rings (expanding)
- 25 FPS pulse animation
- Auto-ranging based on timeframe
- PnL-driven color updates

Architecture:
- Encapsulates all PyQtGraph rendering
- Stateful (manages plot items, animation state)
- Signal-free (pure rendering, no business logic)

Usage:
    from panels.panel1.equity_chart import EquityChart

    chart = EquityChart(parent=widget)
    plot_widget = chart.create_plot_widget()

    # Add to layout
    layout.addWidget(plot_widget)

    # Start animation
    chart.start_animation()

    # Update data
    chart.replot(points=[(ts, bal), ...], timeframe="1D")

    # Update color
    chart.update_endpoint_color(is_positive=True)
"""

from __future__ import annotations

import contextlib
import math
from typing import Any, Optional

from PyQt6 import QtCore, QtGui

from config.theme import THEME, ColorTheme
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import pyqtgraph (may not be available in all environments)
try:
    import pyqtgraph as pg  # type: ignore
    HAS_PYQTGRAPH = True
except ImportError:
    pg = None
    HAS_PYQTGRAPH = False
    log.warning("pyqtgraph not available - chart rendering disabled")


class EquityChart(QtCore.QObject):
    """
    PyQtGraph equity chart renderer with animation.

    Features:
    - Main equity line with trails and glow
    - Animated endpoint (breathing effect)
    - Sonar ripple rings (3 expanding circles)
    - 25 FPS pulse timer
    - PnL-driven color updates
    - Timeframe-based auto-ranging
    """

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """
        Initialize equity chart renderer.

        Args:
            parent: Parent QObject (optional)
        """
        super().__init__(parent)

        # Plot widget and items
        self._plot: Optional[Any] = None  # PlotWidget
        self._vb: Optional[Any] = None  # ViewBox
        self._line: Optional[Any] = None  # Main equity line
        self._trail_lines: list[Any] = []  # Trailing lines
        self._glow_line: Optional[Any] = None  # Glow halo
        self._endpoint: Optional[Any] = None  # Endpoint dot
        self._ripple_items: list[Any] = []  # Sonar ripple rings

        # Animation state
        self._pulse_timer: Optional[QtCore.QTimer] = None
        self._pulse_phase: float = 0.0

        # Configuration
        self._perf_safe: bool = bool(THEME.get("perf_safe", False))

        # Current data and state
        self._current_points: list[tuple[float, float]] = []
        self._current_timeframe: str = "LIVE"
        self._current_pnl_direction: Optional[bool] = None  # True=up, False=down, None=neutral

        # Timeframe configurations (for auto-range)
        self._tf_configs = {
            "LIVE": {"window_sec": 3600, "snap_sec": 1},
            "1D": {"window_sec": 86400, "snap_sec": 300},
            "1W": {"window_sec": 604800, "snap_sec": 3600},
            "1M": {"window_sec": 2592000, "snap_sec": 3600},
            "3M": {"window_sec": 7776000, "snap_sec": 86400},
            "YTD": {"window_sec": None, "snap_sec": 604800},
            "ALL": {"window_sec": None, "snap_sec": 604800},
        }

    def create_plot_widget(self) -> Optional[Any]:
        """
        Create and configure PlotWidget.

        Returns:
            PlotWidget instance, or None if pyqtgraph unavailable
        """
        if not HAS_PYQTGRAPH or pg is None:
            log.error("Cannot create plot widget - pyqtgraph not available")
            return None

        try:
            # Create PlotWidget
            self._plot = pg.PlotWidget()
            self._vb = self._plot.getPlotItem().getViewBox()

            # Styling
            bg_color = THEME.get("bg_secondary", "#000000")
            self._plot.setBackground(bg_color)

            # Hide axes
            self._plot.getPlotItem().hideAxis("left")
            self._plot.getPlotItem().hideAxis("bottom")

            # Disable mouse interactions (read-only chart)
            self._vb.setMouseEnabled(x=False, y=False)
            self._plot.setMenuEnabled(False)

            # Initialize plot items (line, trails, endpoint, ripples)
            self._init_plot_items()

            return self._plot

        except Exception as e:
            log.error(f"Error creating plot widget: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _init_plot_items(self) -> None:
        """
        Initialize plot items (line, trails, glow, endpoint, ripples).

        Called internally by create_plot_widget().
        """
        if self._plot is None:
            return

        try:
            # Base color (will be updated dynamically based on PnL)
            base_color = QtGui.QColor(THEME.get("ink", "#E5E7EB"))

            # Main equity line
            main_pen = pg.mkPen(base_color, width=6, join="round", cap="round")
            self._line = self._plot.plot([], [], pen=main_pen, antialias=True)
            self._line.setZValue(10)

            # Trail lines (multiple layers with decreasing alpha)
            self._trail_lines = []
            trail_specs = (
                [
                    {"width": 8, "alpha": 0.25, "take": 1.00},  # Full line
                    {"width": 6, "alpha": 0.35, "take": 0.66},  # Last 66%
                    {"width": 4, "alpha": 0.50, "take": 0.40},  # Last 40%
                ]
                if not self._perf_safe
                else [{"width": 6, "alpha": 0.35, "take": 0.60}]  # Single trail
            )

            for spec in trail_specs:
                c = QtGui.QColor(base_color)
                c.setAlphaF(spec["alpha"])
                pen = pg.mkPen(c, width=spec["width"], join="round", cap="round")
                item = self._plot.plot([], [], pen=pen, antialias=True)
                item._trail_take = spec["take"]  # Custom attribute
                item.setZValue(5)
                self._trail_lines.append(item)

            # Glow halo (only if not perf_safe)
            self._glow_line = None
            if not self._perf_safe:
                glow_c = QtGui.QColor(base_color)
                glow_c.setAlphaF(0.12)
                self._glow_line = self._plot.plot(
                    [], [],
                    pen=pg.mkPen(glow_c, width=16, join="round", cap="round"),
                    antialias=True
                )
                self._glow_line.setZValue(3)

            # Endpoint dot (breathing effect)
            self._endpoint = pg.ScatterPlotItem(
                size=8,
                brush=pg.mkBrush(base_color),
                pen=pg.mkPen(None)
            )
            self._endpoint.setZValue(15)
            self._plot.addItem(self._endpoint)

            # Sonar ripple rings (3 expanding circles)
            self._ripple_items = []
            for _ in range(3):
                ripple = pg.ScatterPlotItem(
                    size=8,
                    brush=pg.mkBrush(None),
                    pen=pg.mkPen(base_color, width=1.0)
                )
                ripple.setZValue(12)
                self._plot.addItem(ripple)
                self._ripple_items.append(ripple)

        except Exception as e:
            log.error(f"Error initializing plot items: {e}")
            import traceback
            traceback.print_exc()

    def start_animation(self) -> None:
        """
        Start pulse animation (25 FPS).

        Creates timer and connects to _on_pulse_tick().
        """
        if self._pulse_timer is not None:
            return  # Already started

        self._pulse_timer = QtCore.QTimer(self)
        self._pulse_timer.setInterval(40)  # ~25 FPS
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_timer.start()
        self._pulse_phase = 0.0

    def stop_animation(self) -> None:
        """
        Stop pulse animation.
        """
        if self._pulse_timer is not None:
            self._pulse_timer.stop()
            self._pulse_timer = None

    def replot(
        self,
        points: list[tuple[float, float]],
        timeframe: str = "LIVE"
    ) -> None:
        """
        Update chart with new data points.

        Args:
            points: List of (timestamp, balance) tuples
            timeframe: Current timeframe (affects endpoint visibility)
        """
        if self._line is None or self._plot is None:
            return

        self._current_points = list(points)
        self._current_timeframe = timeframe

        if points:
            xs, ys = zip(*points)

            try:
                # Update main line
                self._line.setData(xs, ys)

                # Update endpoint (only visible for LIVE and 1D)
                if self._endpoint is not None:
                    if timeframe in ("LIVE", "1D"):
                        self._endpoint.setData([xs[-1]], [ys[-1]])
                    else:
                        self._endpoint.setData([], [])

            except Exception as e:
                log.error(f"replot setData failed: {e}")
                return

            # Update trails and glow
            with contextlib.suppress(Exception):
                self._update_trails_and_glow()

            # Auto-range
            try:
                self._auto_range(xs, ys)
            except Exception:
                with contextlib.suppress(Exception):
                    self._plot.getPlotItem().enableAutoRange(x=True, y=True)
        else:
            # No data - clear all
            with contextlib.suppress(Exception):
                self._line.setData([], [])
                if self._endpoint is not None:
                    self._endpoint.setData([], [])

        # Enforce ripple visibility based on timeframe
        with contextlib.suppress(Exception):
            if timeframe not in ("LIVE", "1D"):
                for ripple in self._ripple_items:
                    ripple.setData([], [])

    def update_endpoint_color(self, is_positive: Optional[bool]) -> None:
        """
        Update endpoint and line color based on PnL direction.

        Args:
            is_positive: True for gains, False for losses, None for neutral
        """
        self._current_pnl_direction = is_positive

        # Color will be applied in next pulse tick
        # (pulse tick reads _current_pnl_direction to set colors)

    def _on_pulse_tick(self) -> None:
        """
        Animation loop - called every 40ms (~25 FPS).

        Updates:
        - Endpoint breathing effect
        - Sonar ripple rings
        - Glow halo pulsing
        - Line color based on PnL
        """
        if self._plot is None or self._vb is None:
            return

        if not self._current_points:
            return

        # Limit endpoint pulse to LIVE and 1D timeframes
        if self._current_timeframe not in ("LIVE", "1D"):
            with contextlib.suppress(Exception):
                if self._endpoint is not None:
                    self._endpoint.setData([], [])
                for ripple in self._ripple_items:
                    ripple.setData([], [])
            return

        # Advance pulse phase
        self._pulse_phase = (self._pulse_phase + 0.035) % (2 * math.pi)
        x, y = self._current_points[-1]

        # Get PnL color
        pnl_color = ColorTheme.pnl_color_from_direction(self._current_pnl_direction)
        base_color = QtGui.QColor(pnl_color)

        # Update main line pen dynamically (keeps graph color tied to PnL)
        self._line.setPen(pg.mkPen(base_color, width=6, join="round", cap="round"))

        # Endpoint breathing effect
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
        base_size = 8
        size = base_size + 1.5 * pulse
        dot_color = QtGui.QColor(base_color)
        dot_color.setAlphaF(0.85 - 0.25 * pulse)
        self._endpoint.setSize(size)
        self._endpoint.setBrush(pg.mkBrush(dot_color))
        self._endpoint.setData([x], [y])

        # Sonar ripple rings (brighter inner edge, expanding)
        for i, ripple in enumerate(self._ripple_items):
            phase = (self._pulse_phase + (i * 2 * math.pi / len(self._ripple_items))) % (2 * math.pi)
            frac = (1 + math.sin(phase)) / 2.0
            radius = 8 + frac * 18.0  # Smaller radius (half of previous)
            luminance_boost = 1.0 - frac * 0.6
            alpha = max(0.0, 0.42 * (1.0 - frac)) * luminance_boost
            ring_color = QtGui.QColor(base_color)
            ring_color.setAlphaF(alpha)
            pen = pg.mkPen(ring_color, width=1.0)
            ripple.setPen(pen)
            ripple.setSize(radius)
            ripple.setData([x], [y])

        # Soft glow synced to pulse (only if not perf_safe)
        if self._glow_line is not None and not self._perf_safe:
            g = QtGui.QColor(base_color)
            alpha = 0.06 + 0.03 * (0.5 + 0.5 * math.sin(self._pulse_phase))
            g.setAlphaF(min(0.25, max(0.0, alpha)))
            self._glow_line.setPen(pg.mkPen(g, width=16, join="round", cap="round"))

    def _update_trails_and_glow(self) -> None:
        """
        Update trailing lines and glow effect with current data.

        Trail lines render fractional portions of the data:
        - Trail 1: Full line (100%)
        - Trail 2: Last 66%
        - Trail 3: Last 40%
        """
        if not self._current_points or self._line is None:
            return

        try:
            xs, ys = zip(*self._current_points)

            # Update trail lines with fractional data
            for trail_item in self._trail_lines:
                if hasattr(trail_item, "_trail_take"):
                    take = trail_item._trail_take
                    start_idx = max(0, int(len(xs) * (1 - take)))
                    trail_item.setData(xs[start_idx:], ys[start_idx:])

            # Update glow line (full data)
            if self._glow_line is not None:
                self._glow_line.setData(xs, ys)

        except Exception as e:
            log.debug(f"_update_trails_and_glow error: {e}")

    def _auto_range(self, xs: tuple, ys: tuple) -> None:
        """
        Auto-range X and Y axes based on timeframe window.

        Uses timeframe window to set X range, not just data extent.
        This prevents over-zooming when there are few data points.

        Args:
            xs: X values (timestamps)
            ys: Y values (balances)
        """
        if self._plot is None or not xs or not ys:
            return

        # Get timeframe configuration
        cfg = self._tf_configs.get(self._current_timeframe, {})
        window_sec = cfg.get("window_sec")

        if window_sec:
            # Use timeframe window to set X range
            # Latest time on RIGHT, oldest time on LEFT
            x_max = max(xs)  # Latest data point (RIGHT side)
            x_min = x_max - window_sec  # Start of window (LEFT side)
        else:
            # YTD or no window - fit to data
            x_min, x_max = min(xs), max(xs)

        # Y range with padding
        y_min, y_max = min(ys), max(ys)
        if y_min == y_max:
            pad = max(1.0, abs(y_min) * 0.01)
            y_min -= pad
            y_max += pad

        try:
            self._plot.setXRange(x_min, x_max, padding=0.02)
            self._plot.setYRange(y_min, y_max, padding=0.10)
        except Exception:
            with contextlib.suppress(Exception):
                self._plot.getPlotItem().enableAutoRange(x=True, y=True)

    def get_plot_widget(self) -> Optional[Any]:
        """
        Get PlotWidget for layout attachment.

        Returns:
            PlotWidget instance, or None if not created
        """
        return self._plot

    def has_plot(self) -> bool:
        """
        Check if plot widget is available.

        Returns:
            True if plot widget created, False otherwise
        """
        return self._plot is not None
