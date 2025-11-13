"""
Equity Graph Module

Handles graph initialization, plotting, and visual updates for Panel1.
Extracted from panels/panel1.py for modularity.

Functions:
- init_graph(): Create PyQtGraph widget with all components
- replot_from_cache(): Redraw graph from equity points
- update_trails_and_glow(): Animate trailing lines and glow
- auto_range(): Automatic axis scaling
- attach_plot_to_container(): Attach plot widget to container
- has_graph(): Check if graph is available
"""

import contextlib
from PyQt6 import QtCore, QtGui, QtWidgets
from config.theme import THEME, ColorTheme
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import pyqtgraph
try:
    import pyqtgraph as pg
except ImportError:
    pg = None


# ================================================================================
# Graph Availability Check
# ================================================================================

def has_graph(panel) -> bool:
    """
    Check if graph is available and fully initialized.

    Checks:
    - pyqtgraph is available
    - _plot exists
    - _vb (viewbox) exists
    - _line exists

    Args:
        panel: Panel1 instance

    Returns:
        True if graph is fully initialized, False otherwise
    """
    return (
        pg is not None
        and getattr(panel, "_plot", None) is not None
        and getattr(panel, "_vb", None) is not None
        and getattr(panel, "_line", None) is not None
    )


# ================================================================================
# Graph Initialization
# ================================================================================

def init_graph(panel) -> None:
    """
    Initialize PyQtGraph widget with equity curve, endpoint marker, trails, and glow.

    Creates:
    - PlotWidget with dark background
    - Main equity line (width 6, PnL-colored)
    - Trail lines (3 layers with decreasing opacity)
    - Glow halo effect
    - Endpoint marker (breathing animation)
    - Sonar rings (3 expanding circles)

    Args:
        panel: Panel1 instance
    """
    log.debug(f"_init_graph called, pg={pg}")
    if pg is None:
        log.error("ERROR: pyqtgraph (pg) is None!")
        panel._plot = None
        panel._vb = None
        panel._line = None
        panel._trail_lines = []
        panel._glow_line = None
        panel._endpoint = None
        return

    try:
        # State
        panel._perf_safe = bool(THEME.get("perf_safe", False))
        panel._pulse_phase = 0.0
        panel._hovering = bool(getattr(panel, "_hovering", False))
        panel._current_color = QtGui.QColor(THEME.get("ink", "#E5E7EB"))
        panel._target_color = QtGui.QColor(panel._current_color)

        # Plot widget
        pg.setConfigOptions(antialias=True)
        panel._plot = pg.PlotWidget()
        # Use dedicated graph_bg theme key for consistent dark background across all modes
        graph_bg = THEME.get("graph_bg", "#0F0F1A")  # Dark background for graph visibility
        panel._plot.setBackground(graph_bg)
        panel._plot.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        panel._plot.setStyleSheet("background: transparent; border: none;")
        panel._plot.useOpenGL(False)
        panel._plot.setMenuEnabled(False)
        # FIX: Disable mouse panning/zooming - graph should be fixed
        panel._plot.setMouseEnabled(x=False, y=False)
        panel._plot.hideButtons()
        panel._plot.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        panel._plot.setParent(panel.graph_container)
        panel._plot.setCursor(QtCore.Qt.CursorShape.CrossCursor)  # Crosshair cursor for hover

        # Plot item / viewbox
        plot_item = panel._plot.getPlotItem()
        plot_item.hideAxis("left")
        plot_item.hideAxis("bottom")
        # FIX: Show grid lines for debugging visibility
        plot_item.showGrid(x=True, y=True, alpha=0.15)
        plot_item.setContentsMargins(0, 0, 0, 0)
        plot_item.layout.setContentsMargins(0, 0, 0, 0)

        vb = plot_item.getViewBox()
        vb.setDefaultPadding(0.02)
        # FIX: Disable mouse interaction on viewbox - prevents panning
        vb.setMouseEnabled(x=False, y=False)
        vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=False)  # Disable auto-range
        vb.setLimits(xMin=None, xMax=None, yMin=None, yMax=None)
        # FIX: Ensure graph moves left to right (time on X axis, balance on Y axis)
        vb.invertY(False)  # Make sure Y axis goes bottom (low) to top (high)
        vb.invertX(False)  # Make sure X axis goes left (old) to right (new)
        panel._vb = vb

        # Main line (initialize once; color updates dynamically later)
        base_color = QtGui.QColor(ColorTheme.pnl_color_from_direction(getattr(panel, "_pnl_up", None)))
        # FIX: Increase line width from 3 to 6 for better visibility
        main_pen = pg.mkPen(base_color, width=6, join="round", cap="round")
        panel._line = panel._plot.plot([], [], pen=main_pen, antialias=True)
        panel._line.setZValue(10)

        # Trails
        panel._trail_lines = []
        trail_specs = (
            [
                {"width": 8, "alpha": 0.25, "take": 1.00},
                {"width": 6, "alpha": 0.35, "take": 0.66},
                {"width": 4, "alpha": 0.50, "take": 0.40},
            ]
            if not panel._perf_safe
            else [{"width": 6, "alpha": 0.35, "take": 0.60}]
        )
        for spec in trail_specs:
            c = QtGui.QColor(base_color)
            c.setAlphaF(spec["alpha"])
            pen = pg.mkPen(c, width=spec["width"], join="round", cap="round")
            item = panel._plot.plot([], [], pen=pen, antialias=True)
            item._trail_take = spec["take"]
            item.setZValue(5)
            panel._trail_lines.append(item)

        # Glow halo
        panel._glow_line = None
        if not panel._perf_safe:
            glow_c = QtGui.QColor(base_color)
            glow_c.setAlphaF(0.12)
            glow_pen = pg.mkPen(glow_c, width=16, join="round", cap="round")
            panel._glow_line = panel._plot.plot([], [], pen=glow_pen, antialias=True)
            panel._glow_line.setZValue(1)

        # Endpoint
        panel._endpoint = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(base_color), pen=None, symbol="o")
        panel._endpoint.setZValue(50)
        panel._plot.addItem(panel._endpoint)

        # Sonar rings
        panel._ripple_items = []
        for i in range(3):
            ripple = pg.ScatterPlotItem(size=8, pen=pg.mkPen(base_color, width=1.0), brush=None, symbol="o")
            ripple.setZValue(30)
            panel._plot.addItem(ripple)
            panel._ripple_items.append(ripple)

        # Hover hook
        try:
            panel._plot.scene().sigMouseMoved.connect(panel._on_mouse_move)
            panel._plot.viewport().installEventFilter(panel)
        except Exception:
            pass

        # Layout glue
        lay = panel.graph_container.layout()
        if lay:
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            # Remove any existing widgets
            while lay.count():
                lay.takeAt(0)
            # Add plot with stretch factor for centering/filling
            lay.addWidget(panel._plot, 1)  # stretch = 1
            panel._plot.setMinimumSize(0, 0)
            panel._plot.setMaximumSize(QtCore.QSize(16777215, 16777215))
            panel._plot.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
            with contextlib.suppress(Exception):
                lay.setStretchFactor(panel._plot, 1)

        panel._plot.show()
        panel._plot.updateGeometry()
        panel.graph_container.updateGeometry()

        # FIX: Force container visibility and ensure plot has minimum size
        if not panel.graph_container.isVisible():
            panel.graph_container.show()
        if panel._plot.size().width() < 100:
            panel._plot.setMinimumSize(400, 300)
        panel._plot.update()
        panel.graph_container.update()

        # Ensure viewbox has initial range even with no data
        import time

        now = time.time()
        try:
            # Set a reasonable default range (last hour, $0-$100k)
            panel._vb.setRange(xRange=[now - 3600, now], yRange=[0, 100000], padding=0.02)
        except Exception:
            with contextlib.suppress(Exception):
                panel._vb.autoRange(padding=0.05)

        panel.graph_container.installEventFilter(panel)
        log.info("Graph initialized successfully")

    except Exception as e:
        log.error(f"Graph init failed: {e}")
        import traceback

        traceback.print_exc()
        panel._plot = None
        panel._vb = None
        panel._line = None
        panel._trail_lines = []
        panel._glow_line = None
        panel._endpoint = None


# ================================================================================
# Graph Plotting and Updates
# ================================================================================

def replot_from_cache(panel) -> None:
    """
    Use the cached full series (panel._equity_points) and display only the
    windowed slice for the active timeframe. Updates line, endpoint, trails/glow,
    and auto-range.

    Args:
        panel: Panel1 instance
    """
    if not getattr(panel, "_line", None) or not getattr(panel, "_plot", None):
        return

    from panels.panel1 import pnl_manager
    pts = pnl_manager.filtered_points_for_current_tf(panel)

    if pts:
        xs, ys = zip(*pts)
        try:
            panel._line.setData(xs, ys)
            # Show endpoint only for LIVE and 1D
            if getattr(panel, "_endpoint", None):
                if panel._tf in ("LIVE", "1D"):
                    panel._endpoint.setData([xs[-1]], [ys[-1]])
                else:
                    panel._endpoint.setData([], [])
        except Exception as e:
            log.error(f"_replot_from_cache setData failed: {e}")
            return

        with contextlib.suppress(Exception):
            update_trails_and_glow(panel)

        try:
            auto_range(panel, xs, ys)
        except Exception:
            with contextlib.suppress(Exception):
                panel._plot.getPlotItem().enableAutoRange(x=True, y=True)
    else:
        try:
            panel._line.setData([], [])
            if getattr(panel, "_endpoint", None):
                panel._endpoint.setData([], [])
        except Exception:
            pass

    # Also enforce ripple visibility based on timeframe
    try:
        if panel._tf not in ("LIVE", "1D"):
            for ripple in getattr(panel, "_ripple_items", []) or []:
                ripple.setData([], [])
    except Exception:
        pass


def update_trails_and_glow(panel) -> None:
    """
    Update trailing lines and glow effect with current data.

    Args:
        panel: Panel1 instance
    """
    if not panel._equity_points or not getattr(panel, "_line", None):
        return
    try:
        from panels.panel1 import pnl_manager
        pts = pnl_manager.filtered_points_for_current_tf(panel)
        if pts:
            xs, ys = zip(*pts)
            # Update trail lines with fractional data
            for trail_item in getattr(panel, "_trail_lines", []) or []:
                if hasattr(trail_item, "_trail_take"):
                    take = trail_item._trail_take
                    start_idx = max(0, int(len(xs) * (1 - take)))
                    trail_item.setData(xs[start_idx:], ys[start_idx:])
            # Update glow line
            if getattr(panel, "_glow_line", None):
                panel._glow_line.setData(xs, ys)
    except Exception as e:
        log.debug(f"_update_trails_and_glow error: {e}")


def auto_range(panel, xs: tuple, ys: tuple) -> None:
    """
    Automatic axis scaling based on data and timeframe window.

    CRITICAL: Ensures stable graph zoom even with sparse data points.

    Args:
        panel: Panel1 instance
        xs: X data (timestamps)
        ys: Y data (balances)
    """
    if not has_graph(panel):
        return

    # Handle empty data gracefully
    if not xs or not ys:
        import time
        now = time.time()
        log.debug("[Panel1] auto_range: No data, using default range")
        try:
            panel._plot.setXRange(now - 3600, now, padding=0.02)
            panel._plot.setYRange(9000, 11000, padding=0.10)
            return
        except Exception as e:
            log.warning(f"[Panel1] auto_range fallback failed: {e}")
            return

    # FIX: Set X range based on timeframe window, not just data extent
    # This prevents over-zooming when there are few data points
    cfg = panel._tf_configs.get(panel._tf, {})
    window_sec = cfg.get("window_sec")

    if window_sec:
        # Use the timeframe window to set X range
        # Latest time on RIGHT, oldest time on LEFT
        x_max = max(xs)  # Latest data point (RIGHT side)
        x_min = x_max - window_sec  # Start of window (LEFT side)
    else:
        # YTD or no window - fit to data
        x_min, x_max = min(xs), max(xs)

    # Calculate Y range with better padding for visual clarity
    y_min, y_max = min(ys), max(ys)
    y_span = y_max - y_min

    # CRITICAL FIX: Ensure minimum Y span to prevent flat/narrow graphs
    if y_span < 0.01:
        # Nearly flat data - add ±0.5% padding around value
        center = (y_min + y_max) / 2
        pad = max(10.0, abs(center) * 0.005)
        y_min = center - pad
        y_max = center + pad
    else:
        # Normal data - add 10% padding top/bottom
        pad = y_span * 0.10
        y_min -= pad
        y_max += pad

    # Apply ranges with error handling
    try:
        panel._plot.setXRange(x_min, x_max, padding=0.0)  # No extra padding, we calculated it
        panel._plot.setYRange(y_min, y_max, padding=0.0)
        log.debug(f"[Panel1] auto_range: X=[{x_min:.0f}, {x_max:.0f}], Y=[${y_min:.2f}, ${y_max:.2f}]")
    except Exception as e:
        log.error(f"[Panel1] auto_range setRange failed: {e}")
        with contextlib.suppress(Exception):
            panel._plot.enableAutoRange(axis="xy")


# ================================================================================
# Graph Layout Management
# ================================================================================

def attach_plot_to_container(panel, plot) -> None:
    """
    Ensures PlotWidget fills graph_container via layout stretch instead of default 640x480.
    Place this block between UI BUILD (end) and Graph & Pulse (start).

    Args:
        panel: Panel1 instance
        plot: PyQtGraph PlotWidget to attach
    """
    lay = panel.graph_container.layout()
    if lay is None:
        lay = QtWidgets.QVBoxLayout(panel.graph_container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

    # Make the plot fully layout-driven (no fixed-size caps)
    plot.setParent(None)
    plot.setMinimumSize(QtCore.QSize(0, 0))
    plot.setMaximumSize(QtCore.QSize(16777215, 16777215))
    plot.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    # Add with stretch so it fills available space
    lay.addWidget(plot, 1)  # stretch = 1
    with contextlib.suppress(Exception):
        lay.setStretchFactor(plot, 1)

    # Immediate geometry sync to avoid a frame at 640x480
    plot.setGeometry(panel.graph_container.contentsRect())
