"""
Animations Module

Handles pulse effects, glow animations, and periodic update timers for Panel1.
Extracted from panels/panel1.py for modularity.

Functions:
- init_pulse(): Initialize pulse timer and animation state
- on_pulse_tick(): Pulse animation frame update (endpoint breathing, sonar rings)
- on_equity_update_tick(): Periodic equity curve updates
- ensure_live_pill_dot(): Ensure live indicator dot exists
- update_live_pill_dot(): Update pulsing live dot
- debug_sizes(): Debug widget sizes (diagnostic)
"""

import math
from PyQt6 import QtCore, QtGui
from config.theme import ColorTheme
from utils.logger import get_logger

log = get_logger(__name__)

# Import pyqtgraph with fallback
try:
    import pyqtgraph as pg
except ImportError:
    pg = None


def init_pulse(panel) -> None:
    """
    Initialize pulse timer and animation state.

    Creates two timers:
    1. Pulse timer (40ms, ~25 FPS) for endpoint breathing and sonar rings
    2. Equity update timer (1000ms) for continuous timeline

    Args:
        panel: Panel1 instance
    """
    if getattr(panel, "_pulse_timer", None):
        return

    panel._pulse_timer = QtCore.QTimer(panel)
    panel._pulse_timer.setInterval(40)  # ~25 FPS
    panel._pulse_timer.timeout.connect(lambda: on_pulse_tick(panel))
    panel._pulse_timer.start()
    panel._pulse_phase = 0.0

    # Start periodic equity point timer for continuous hover timeline
    if not getattr(panel, "_equity_update_timer", None):
        panel._equity_update_timer = QtCore.QTimer(panel)
        panel._equity_update_timer.setInterval(1000)  # Every 1 second
        panel._equity_update_timer.timeout.connect(lambda: on_equity_update_tick(panel))
        panel._equity_update_timer.start()


def on_pulse_tick(panel) -> None:
    """
    Pulse animation frame update.

    Updates:
    - Endpoint marker: Breathing effect (size and opacity pulse)
    - Sonar rings: Gradient expanding circles
    - Glow effect: Soft glow synced to pulse phase
    - Line color: Dynamic color based on current PnL direction

    Only active for LIVE and 1D timeframes to reduce visual clutter.

    Args:
        panel: Panel1 instance
    """
    if getattr(panel, "_plot", None) is None or getattr(panel, "_vb", None) is None:
        return
    if not panel._equity_points:
        return

    # Limit endpoint pulse to LIVE and 1D timeframes
    if panel._tf not in ("LIVE", "1D"):
        try:
            if getattr(panel, "_endpoint", None):
                panel._endpoint.setData([], [])
            for ripple in getattr(panel, "_ripple_items", []) or []:
                ripple.setData([], [])
            # Clear glow line to prevent ghost glow on non-LIVE/1D timeframes
            if getattr(panel, "_glow_line", None):
                panel._glow_line.setData([], [])
        except Exception:
            pass
        return

    if not pg:
        return  # No pyqtgraph available

    panel._pulse_phase = (panel._pulse_phase + 0.035) % (2 * math.pi)
    x, y = panel._equity_points[-1]

    # Color directly from current PnL each tick
    pnl_color = ColorTheme.pnl_color_from_direction(getattr(panel, "_pnl_up", None))
    base_color = QtGui.QColor(pnl_color)

    # Update line pen dynamically (keeps graph color tied to timeframe PnL)
    panel._line.setPen(pg.mkPen(base_color, width=3, join="round", cap="round"))

    # Endpoint breathing effect
    pulse = 0.5 + 0.5 * math.sin(panel._pulse_phase)
    base_size = 8
    size = base_size + 1.5 * pulse
    dot_color = QtGui.QColor(base_color)
    dot_color.setAlphaF(0.85 - 0.25 * pulse)
    panel._endpoint.setSize(size)
    panel._endpoint.setBrush(pg.mkBrush(dot_color))
    panel._endpoint.setData([x], [y])

    # Sonar rings (brighter inner edge; half-distance travel feel)
    for i, ripple in enumerate(panel._ripple_items):
        phase = (panel._pulse_phase + (i * 2 * math.pi / len(panel._ripple_items))) % (2 * math.pi)
        frac = (1 + math.sin(phase)) / 2.0
        radius = 8 + frac * 18.0  # ~half the previous travel distance
        luminance_boost = 1.0 - frac * 0.6
        alpha = max(0.0, 0.42 * (1.0 - frac)) * luminance_boost  # a bit brighter
        ring_color = QtGui.QColor(base_color)
        ring_color.setAlphaF(alpha)
        pen = pg.mkPen(ring_color, width=1.0)
        ripple.setPen(pen)
        ripple.setSize(radius)
        ripple.setData([x], [y])

    # Soft glow synced to pulse
    if panel._glow_line is not None and not panel._perf_safe:
        g = QtGui.QColor(base_color)
        alpha = 0.06 + 0.03 * (0.5 + 0.5 * math.sin(panel._pulse_phase))
        g.setAlphaF(min(0.25, max(0.0, alpha)))
        panel._glow_line.setPen(pg.mkPen(g, width=16, join="round", cap="round"))


def on_equity_update_tick(panel) -> None:
    """
    Periodically add current balance to equity curve (every 1 second).

    This ensures continuous timeline for hover even when balance doesn't change.
    Uses current mode (SIM/LIVE) to get the appropriate balance.

    Args:
        panel: Panel1 instance
    """
    try:
        from core.app_state import get_state_manager
        state = get_state_manager()
        if not state:
            return

        # Get current balance for active mode
        current_mode = state.current_mode
        current_balance = state.get_balance_for_mode(current_mode)

        # Add point to equity curve (will be deduplicated by time cutoff)
        panel.update_equity_series_from_balance(current_balance, mode=current_mode)

    except Exception as e:
        log.debug(f"[Panel1] Equity update tick error: {e}")


def ensure_live_pill_dot(panel, initial: bool = False) -> None:
    """
    Ensure the LIVE dot exists and set a sane initial pulsing state.

    Args:
        panel: Panel1 instance
        initial: If True, set pulsing to False initially (for startup)
    """
    try:
        if hasattr(panel, "pills") and panel.pills:
            if hasattr(panel.pills, "set_live_dot_visible"):
                panel.pills.set_live_dot_visible(True)
            if hasattr(panel.pills, "set_live_dot_pulsing"):
                panel.pills.set_live_dot_pulsing(False if initial else (panel._tf == "LIVE"))
    except Exception:
        pass


def update_live_pill_dot(panel, pulsing: bool) -> None:
    """
    Show the LIVE dot and toggle pulsing.

    Safe if widget lacks these hooks - will silently ignore if not available.

    Args:
        panel: Panel1 instance
        pulsing: True to enable pulsing animation, False to disable
    """
    try:
        if hasattr(panel, "pills") and panel.pills:
            if hasattr(panel.pills, "set_live_dot_visible"):
                panel.pills.set_live_dot_visible(True)
            if hasattr(panel.pills, "set_live_dot_pulsing"):
                panel.pills.set_live_dot_pulsing(bool(pulsing))
    except Exception:
        pass


def debug_sizes(panel) -> None:
    """
    Debug method to check widget sizes after layout.

    Logs:
    - Panel1 visibility and size
    - Graph container visibility and size
    - Plot widget visibility and size (if exists)

    Args:
        panel: Panel1 instance
    """
    log.debug("=== SIZE DEBUG ===")
    log.debug(f"Panel1 visible: {panel.isVisible()}")
    log.debug(f"Panel1 size: {panel.size().width()}x{panel.size().height()}")
    log.debug(f"Graph container visible: {panel.graph_container.isVisible()}")
    log.debug(f"Graph container size: {panel.graph_container.size().width()}x{panel.graph_container.size().height()}")
    if panel._plot:
        log.debug(f"Plot visible: {panel._plot.isVisible()}")
        log.debug(f"Plot size: {panel._plot.size().width()}x{panel._plot.size().height()}")
    log.debug("=== END SIZE DEBUG ===")
