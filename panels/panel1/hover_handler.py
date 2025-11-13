"""
Hover Handler Module

Handles mouse hover interactions, crosshair, and tooltip for Panel1 equity graph.
Extracted from panels/panel1.py for modularity.

Functions:
- init_hover_elements(): Initialize crosshair lines and hover state
- event_filter(): Hide hover artifacts when cursor leaves
- on_mouse_move(): Handle mouse movement over graph
- update_header_for_hover(): Update header during hover
- find_nearest_index(): Find nearest data point to mouse
- on_investing_tf_changed(): Handle pills timeframe change

Features:
- Crosshair follows mouse over graph
- Header shows balance/PnL at hover position
- Tooltip displays timestamp and value
- Smooth crosshair animations
"""

from typing import Optional
from PyQt6 import QtCore, QtGui, QtWidgets
from config.theme import THEME, ColorTheme
from utils.theme_helpers import normalize_color
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import pyqtgraph
try:
    import pyqtgraph as pg
except ImportError:
    pg = None


# ================================================================================
# Hover Element Initialization
# ================================================================================

def init_hover_elements(panel) -> None:
    """
    Create a taller solid hover line with timestamp restored to its original placement.

    Creates:
    - Vertical hover line (85% height)
    - Timestamp text label with theme font

    Args:
        panel: Panel1 instance
    """
    from panels.panel1 import equity_graph
    if not equity_graph.has_graph(panel):
        return
    try:
        # Hover line (85% height, as current)
        panel._hover_seg = QtWidgets.QGraphicsLineItem()
        panel._hover_seg.setPen(pg.mkPen(THEME.get("fg_muted", "#C8CDD3"), width=1))
        panel._hover_seg.setZValue(100)
        panel._hover_seg.setVisible(False)
        panel._plot.getPlotItem().scene().addItem(panel._hover_seg)

        # Timestamp text (restored original Y position) - universal skeleton font
        # Convert OKLCH to hex for PyQtGraph, then create QColor for proper PyQtGraph handling
        text_hex = normalize_color(THEME.get("ink", "#E5E7EB"))
        text_qcolor = QtGui.QColor(text_hex)
        panel._hover_text = pg.TextItem("", color=text_qcolor, anchor=(0.5, 1.0))
        # Set font to match universal skeleton (16px weight 500)
        font = QtGui.QFont(THEME.get("font_family", "Inter, sans-serif"))
        font.setPixelSize(int(THEME.get("font_size", 16)))
        font.setWeight(int(THEME.get("font_weight", 500)))
        panel._hover_text.setFont(font)
        panel._hover_text.setZValue(101)
        panel._hover_text.setVisible(False)
        panel._plot.addItem(panel._hover_text)

        # Mouse move connection
        panel._plot.scene().sigMouseMoved.connect(lambda pos: on_mouse_move(panel, pos))
        panel._plot.viewport().installEventFilter(panel)
    except Exception:
        panel._hover_seg = None
        panel._hover_text = None


# ================================================================================
# Event Filtering
# ================================================================================

def event_filter(panel, obj, event) -> bool:
    """
    Hide hover artifacts when cursor leaves the plot viewport.

    Args:
        panel: Panel1 instance
        obj: Event object
        event: Qt event

    Returns:
        True if event was handled, False otherwise
    """
    try:
        if panel._plot and obj == panel._plot.viewport() and event.type() == QtCore.QEvent.Type.Leave:
            if panel._hover_seg:
                panel._hover_seg.setVisible(False)
            if panel._hover_text:
                panel._hover_text.setVisible(False)
            panel._hovering = False
            panel._scrub_x = None
            from panels.panel1 import pnl_manager
            pnl_manager.apply_pnl_to_header(panel)
            return True
    except Exception:
        pass
    return False


# ================================================================================
# Mouse Movement Handling
# ================================================================================

def on_mouse_move(panel, pos) -> None:
    """
    Keep hover bar tall but restore timestamp height; clamp inside left/right borders.

    Updates:
    - Vertical crosshair line
    - Timestamp tooltip
    - Balance/PnL header values

    Args:
        panel: Panel1 instance
        pos: Mouse position in scene coordinates
    """
    if not panel._plot or panel._vb is None:
        return

    # Use filtered points for the current timeframe instead of full history
    from panels.panel1 import pnl_manager
    pts = pnl_manager.filtered_points_for_current_tf(panel)
    if not pts:
        if panel._hover_seg:
            panel._hover_seg.setVisible(False)
        if panel._hover_text:
            panel._hover_text.setVisible(False)
        return

    scene_rect = panel._plot.sceneBoundingRect()
    if not scene_rect.contains(pos):
        if panel._hover_seg:
            panel._hover_seg.setVisible(False)
        if panel._hover_text:
            panel._hover_text.setVisible(False)
        return

    vb = panel._vb
    mp = vb.mapSceneToView(pos)
    x_mouse = float(mp.x())

    # Clamp to visible range
    xr, yr = vb.viewRange()
    if x_mouse < xr[0] or x_mouse > xr[1]:
        return

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    # FIX: Find nearest actual data point instead of snapping to arbitrary intervals
    # The old logic created timestamps outside the data range
    idx = find_nearest_index(xs, x_mouse)
    if idx is None:
        return

    x = float(xs[idx])
    y = float(ys[idx])
    panel._hovering = True
    panel._scrub_x = x

    # Hover line -- keep current (85% height)
    if panel._hover_seg:
        y_min, y_max = yr[0], yr[1]
        y_span = y_max - y_min
        frac = 0.85
        y_top = y_min + y_span * frac

        p0 = vb.mapViewToScene(QtCore.QPointF(x, y_min))
        p1 = vb.mapViewToScene(QtCore.QPointF(x, y_top))
        panel._hover_seg.setLine(p0.x(), p0.y(), p1.x(), p1.y())
        if not panel._hover_seg.isVisible():
            panel._hover_seg.setVisible(True)

    # Timestamp -- restore original higher placement
    if panel._hover_text:
        from datetime import datetime

        dt = datetime.fromtimestamp(x)
        if panel._tf in ("LIVE", "1D"):
            t = dt.strftime("%I:%M %p").lstrip("0")
        elif panel._tf in ("1W", "1M"):
            t = dt.strftime("%b %d, %I:%M %p").replace(" 0", " ").lstrip("0")
        else:
            t = dt.strftime("%b %d, %Y").replace(" 0", " ")

        y_min, y_max = yr[0], yr[1]
        y_span = y_max - y_min
        y_top = y_min + y_span * 0.92  # raise timestamp higher again

        pad = (xr[1] - xr[0]) * 0.02
        x_clamped = max(xr[0] + pad, min(xr[1] - pad, x))

        panel._hover_text.setText(t)
        panel._hover_text.setPos(x_clamped, y_top)
        if not panel._hover_text.isVisible():
            panel._hover_text.setVisible(True)

    # Header update
    update_header_for_hover(panel, x, y)


# ================================================================================
# Hover Calculations
# ================================================================================

def update_header_for_hover(panel, x: float, y: float) -> None:
    """
    Update balance/PnL display for hovered point.

    Args:
        panel: Panel1 instance
        x: Hovered timestamp
        y: Hovered balance value
    """
    from panels.panel1 import pnl_manager
    panel.lbl_balance.setText(pnl_manager.fmt_money(y))

    # Get baseline from start of timeframe window (not relative to hover position)
    baseline = pnl_manager.get_baseline_for_tf(panel)
    if baseline is None:
        # If no baseline found, show just the balance
        panel.lbl_pnl.setText("--  --")
        return

    pnl = y - baseline
    if abs(pnl) < 0.01:
        panel.lbl_pnl.setText("$0.00 (0.00%)")
        return

    pct = 0.0 if baseline == 0 else (pnl / baseline) * 100.0
    up = pnl > 0
    tri = "+" if up else "-"
    col = pnl_manager.pnl_color(up)
    panel.lbl_pnl.setText(f"{tri} ${abs(pnl):,.2f} ({abs(pct):.2f}%)")
    panel.lbl_pnl.setStyleSheet(
        f"color:{col}; "
        f"{ColorTheme.font_css(int(THEME.get('pnl_font_weight', 500)), int(THEME.get('pnl_font_size', 12)))};"
    )


def find_nearest_index(xs: list, target_x: float) -> Optional[int]:
    """
    Find index of nearest x (snap-aware).

    Args:
        xs: List of x values (timestamps)
        target_x: Target x value to find nearest neighbor

    Returns:
        Index of nearest point or None if empty
    """
    if not xs:
        return None
    import bisect

    i = bisect.bisect_right(xs, target_x)

    if i == 0:
        return 0
    if i >= len(xs):
        return len(xs) - 1

    result = i if abs(xs[i] - target_x) < abs(xs[i - 1] - target_x) else i - 1
    return result


# ================================================================================
# Timeframe Change Handling
# ================================================================================

def on_investing_tf_changed(panel, tf: str) -> None:
    """
    Handle timeframe selection from pills or external calls.

    Updates:
    - Timeframe state
    - Pill visuals and pulsing
    - Endpoint marker color

    Args:
        panel: Panel1 instance
        tf: Timeframe string (LIVE/1D/1W/1M/3M/YTD)
    """
    if tf not in ("LIVE", "1D", "1W", "1M", "3M", "YTD"):
        return
    panel._tf = tf
    panel.timeframeChanged.emit(tf)

    # Update pill visuals & pulsing
    from panels.panel1 import animations, pnl_manager
    animations.update_live_pill_dot(panel, pulsing=(tf == "LIVE"))
    pnl_manager.recolor_endpoint(panel)

    # Keep pill color aligned with current PnL direction
    try:
        if hasattr(panel.pills, "set_active_color"):
            panel.pills.set_active_color(pnl_manager.pnl_color(panel._pnl_up))
    except Exception:
        pass
