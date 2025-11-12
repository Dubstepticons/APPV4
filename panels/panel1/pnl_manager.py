"""
PnL Manager Module

Handles PnL calculations, equity curve loading, timeframe management, and mode switching.
Extracted from panels/panel1.py for modularity.

Functions:
- set_timeframe(): Switch timeframe (LIVE/1D/1W/1M/3M/YTD)
- update_pnl_for_current_tf(): Calculate and display PnL for current timeframe
- load_equity_curve_from_database(): Rebuild equity curve from trade history
- get_equity_curve(): Get equity curve with async loading
- set_trading_mode(): Switch between DEBUG/SIM/LIVE modes
- set_account_balance(): Update balance display
- update_equity_series_from_balance(): Add balance point to equity curve
- set_pnl_for_timeframe(): Update PnL display
- set_equity_series(): Store equity curve and redraw
- get_baseline_for_tf(): Get baseline value for PnL calculation

Helper Functions:
- pnl_color(): Get color for PnL direction
- fmt_money(): Format money value
"""

from typing import Optional
from PyQt6 import QtCore, QtGui, QtWidgets
from config.theme import THEME, ColorTheme, switch_theme
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import QtConcurrent for async loading
try:
    from PyQt6.QtConcurrent import QtConcurrent
    HAS_QTCONCURRENT = True
except ImportError:
    QtConcurrent = None
    HAS_QTCONCURRENT = False

# Try to import pyqtgraph (may not be available)
try:
    import pyqtgraph as pg
except ImportError:
    pg = None


# ================================================================================
# Helper Functions
# ================================================================================

def pnl_color(up: Optional[bool]) -> str:
    """
    Return a direction color from theme (green/red/neutral).

    Args:
        up: True for positive, False for negative, None for neutral

    Returns:
        Hex color string
    """
    if up is None:
        return str(THEME.get("pnl_neu_color", "#C9CDD0"))
    return ColorTheme.pnl_color_from_direction(bool(up))


def fmt_money(v: Optional[float]) -> str:
    """
    Format money value as $X,XXX.XX.

    Args:
        v: Value to format

    Returns:
        Formatted string or "--" if None
    """
    if v is None:
        return "--"
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "--"


# ================================================================================
# Timeframe Management
# ================================================================================

def set_timeframe(panel, tf: str) -> None:
    """
    Public setter wired from pills.timeframeChanged.
    Enforces the active timeframe by replotting a windowed slice (if available).

    Args:
        panel: Panel1 instance
        tf: Timeframe string (LIVE/1D/1W/1M/3M/YTD)
    """
    if tf not in ("LIVE", "1D", "1W", "1M", "3M", "YTD"):
        log.warning(f"Ignoring invalid timeframe: {tf}")
        return

    panel._tf = tf
    log.info(f"Timeframe changed to {tf}")

    # Route to controller if present (non-fatal if missing)
    if hasattr(panel, "_on_investing_tf_changed"):
        try:
            panel._on_investing_tf_changed(tf)
        except Exception as e:
            log.error(f"_on_investing_tf_changed error: {e}")

    # Replot from cache so the graph reflects the TF window
    try:
        from panels.panel1 import equity_graph
        equity_graph.replot_from_cache(panel)
    except Exception as e:
        log.error(f"set_timeframe replot error: {e}")

    # Update LIVE pill pulse state
    from panels.panel1 import animations
    animations.ensure_live_pill_dot(panel, initial=False)

    # Update PnL display for the new timeframe
    update_pnl_for_current_tf(panel)


def update_pnl_for_current_tf(panel) -> None:
    """
    Calculate and display PnL for the current timeframe based on ACTUAL TRADES.

    Args:
        panel: Panel1 instance
    """
    try:
        from datetime import datetime, timedelta, timezone
        from services.repositories.trade_repository import TradeRepository

        UTC = timezone.utc
        now = datetime.now(UTC)
        mode = panel._current_display_mode

        # Define timeframe ranges
        timeframe_ranges = {
            "LIVE": (now - timedelta(hours=1), now),  # Last 1 hour
            "1D": (datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=UTC), now),  # Since midnight
            "1W": (now - timedelta(weeks=1), now),  # Last 7 days
            "1M": (now - timedelta(days=30), now),  # Last 30 days
            "3M": (now - timedelta(days=90), now),  # Last 90 days
            "YTD": (datetime(now.year, 1, 1, tzinfo=UTC), now),  # Jan 1 to now
        }

        if panel._tf not in timeframe_ranges:
            start_time, end_time = timeframe_ranges["LIVE"]
        else:
            start_time, end_time = timeframe_ranges[panel._tf]

        # Query trades for this timeframe using repository
        repo = TradeRepository()
        trades = repo.get_range(
            start_time,
            end_time,
            mode=mode,
            is_closed=True
        )
        # Filter out trades with None realized_pnl
        trades = [t for t in trades if t.realized_pnl is not None]

        if trades:
            # Calculate total PnL for timeframe
            total_pnl = sum(t.realized_pnl for t in trades if t.realized_pnl is not None)
            baseline = 10000.0  # Standard SIM starting balance
            pnl_pct = (total_pnl / baseline) * 100.0

            pnl_up = total_pnl > 0 if abs(total_pnl) > 0.01 else None
        else:
            total_pnl = 0.0
            pnl_pct = 0.0
            pnl_up = None

        # Update display
        set_pnl_for_timeframe(panel, pnl_value=total_pnl, pnl_pct=pnl_pct, up=pnl_up)
        log.debug(f"[panel1] PnL for {panel._tf}: ${total_pnl:+.2f} ({pnl_pct:+.2f}%)")

    except Exception as e:
        import traceback
        traceback.print_exc()
        log.error(f"[panel1] Could not calculate PnL for timeframe {panel._tf}: {e}")
        # Show zero on error
        set_pnl_for_timeframe(panel, pnl_value=0.0, pnl_pct=0.0, up=None)


def filtered_points_for_current_tf(panel) -> list[tuple[float, float]]:
    """
    Return a slice of the active mode's equity points that fits the active timeframe window.

    Args:
        panel: Panel1 instance

    Returns:
        List of (timestamp, balance) tuples filtered by timeframe
    """
    # Get the active curve for current scope
    pts = list(panel._equity_points or [])

    log.debug(f"[Panel1] Filtering points for {panel.current_mode}/{panel.current_account}: {len(pts)} total")

    if not pts:
        return []

    cfg = panel._tf_configs.get(panel._tf, {})
    window_sec = cfg.get("window_sec")

    if not window_sec:
        return pts  # None or 0 -> no trim

    last_x = float(pts[-1][0])
    x_min = last_x - float(window_sec)

    i0 = 0
    for i, (x, _) in enumerate(pts):
        if x >= x_min:
            i0 = i
            break

    filtered = pts[i0:]
    return filtered


def get_baseline_for_tf(panel, at_time: float) -> Optional[float]:
    """
    Get the baseline value for PnL calculation based on timeframe.

    Args:
        panel: Panel1 instance
        at_time: Timestamp to calculate baseline for

    Returns:
        Baseline balance value or None
    """
    if not panel._equity_points:
        return None

    import bisect
    from datetime import datetime

    xs = [p[0] for p in panel._equity_points]
    ys = [p[1] for p in panel._equity_points]

    if panel._tf == "LIVE":
        baseline_time = at_time - 3600
    elif panel._tf == "1D":
        dt = datetime.fromtimestamp(at_time)
        baseline_time = datetime(dt.year, dt.month, dt.day).timestamp()
    elif panel._tf == "1W":
        baseline_time = at_time - 604800
    elif panel._tf == "1M":
        baseline_time = at_time - 2592000
    elif panel._tf == "3M":
        baseline_time = at_time - 7776000
    else:  # YTD
        dt = datetime.fromtimestamp(at_time)
        baseline_time = datetime(dt.year, 1, 1).timestamp()

    i = bisect.bisect_right(xs, baseline_time)
    if i == 0:
        return ys[0]
    return ys[i - 1]


# ================================================================================
# Database Loading
# ================================================================================

def load_equity_curve_from_database(mode: str, account: str) -> list[tuple[float, float]]:
    """
    Rebuild equity curve from trade history in the database.

    Queries all closed trades for the given (mode, account) scope,
    sorts them by exit time, and builds a cumulative balance curve.

    Args:
        mode: Trading mode ("SIM", "LIVE", "DEBUG")
        account: Account identifier

    Returns:
        List of (timestamp, balance) points for the equity curve
    """
    try:
        from datetime import timezone
        from services.repositories.trade_repository import TradeRepository

        # Get starting balance (default 10k for SIM, 0 for LIVE)
        starting_balance = 10000.0 if mode == "SIM" else 0.0

        # Query all closed trades for this mode using repository
        repo = TradeRepository()
        trades = repo.get_closed_trades_by_mode(mode)

        # Filter trades with valid P&L and exit time, then sort by exit time
        trades = [t for t in trades if t.realized_pnl is not None and t.exit_time is not None]
        trades.sort(key=lambda t: t.exit_time)

        if not trades:
            # No trades yet, return empty curve
            return []

        # Build equity curve: cumulative sum of P&L
        equity_points = []
        cumulative_balance = starting_balance

        for trade in trades:
            cumulative_balance += trade.realized_pnl
            timestamp = trade.exit_time.replace(tzinfo=timezone.utc).timestamp()
            equity_points.append((timestamp, cumulative_balance))

        return equity_points

    except Exception as e:
        log.error(f"[Panel1] Error loading equity curve from database: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return []


def get_equity_curve(panel, mode: str, account: str) -> list[tuple[float, float]]:
    """
    Get equity curve for (mode, account) scope, loading from database if not cached.

    CRITICAL FIX: Thread-safe access with QMutex, async database loading on background thread.

    Args:
        panel: Panel1 instance
        mode: Trading mode ("SIM", "LIVE", "DEBUG")
        account: Account identifier

    Returns:
        List of (timestamp, balance) points (empty if not yet loaded)
    """
    scope = (mode, account)

    # Thread-safe check if curve exists
    panel._equity_mutex.lock()
    try:
        if scope in panel._equity_curves:
            # Already cached - return immediately
            return panel._equity_curves[scope].copy()  # Return copy to prevent external mutation

        # Check if already loading
        if scope in panel._pending_loads:
            # Load in progress - return empty for now
            return []

        # Mark as pending and trigger async load
        panel._pending_loads.add(scope)
    finally:
        panel._equity_mutex.unlock()

    # Start async database load on background thread
    log.debug(f"[Panel1] Starting async equity curve load for {scope}")

    if HAS_QTCONCURRENT:
        # Async loading with QtConcurrent (preferred)
        future = QtConcurrent.run(load_equity_curve_from_database, mode, account)

        # Connect callback for when load completes
        watcher = QtCore.QFutureWatcher()
        watcher.setFuture(future)
        watcher.finished.connect(lambda: on_equity_curve_loaded(panel, mode, account, watcher.result()))

        # Store watcher to prevent garbage collection
        if not hasattr(panel, '_future_watchers'):
            panel._future_watchers = []
        panel._future_watchers.append(watcher)
    else:
        # Fallback: Synchronous loading (may cause brief UI freeze)
        log.warning("[Panel1] QtConcurrent not available, loading equity curve synchronously")
        data = load_equity_curve_from_database(mode, account)
        on_equity_curve_loaded(panel, mode, account, data)

    return []  # Return empty until load completes


def on_equity_curve_loaded(panel, mode: str, account: str, equity_points: list[tuple[float, float]]) -> None:
    """
    Callback when async equity curve load completes.

    CRITICAL FIX: Thread-safe cache update and UI refresh.

    Args:
        panel: Panel1 instance
        mode: Trading mode
        account: Account identifier
        equity_points: Loaded equity curve points
    """
    scope = (mode, account)

    # Thread-safe cache update
    panel._equity_mutex.lock()
    try:
        panel._equity_curves[scope] = equity_points
        panel._pending_loads.discard(scope)

        # Update active curve if this is the current scope
        if panel._active_scope == scope:
            panel._equity_points = equity_points
            log.debug(f"[Panel1] Equity curve loaded for {scope}: {len(equity_points)} points")
    finally:
        panel._equity_mutex.unlock()

    # Trigger UI repaint if this is the active scope
    if panel._active_scope == scope:
        from panels.panel1 import equity_graph
        equity_graph.replot_from_cache(panel)
        log.debug(f"[Panel1] UI refreshed after equity curve load")


# ================================================================================
# Balance/Equity Updates
# ================================================================================

def set_account_balance(panel, balance: Optional[float]) -> None:
    """
    Update balance display.

    Args:
        panel: Panel1 instance
        balance: Balance value to display
    """
    panel.lbl_balance.setText(fmt_money(balance))


def update_equity_series_from_balance(panel, balance: Optional[float], mode: Optional[str] = None) -> None:
    """
    Add a balance point to the equity curve for graphing.

    This gets called when balance updates arrive from DTC,
    allowing us to build an equity curve over time.

    CRITICAL FIX: Uses strict (mode, account) scoping with thread-safe mutex protection.
    Balance updates are stored in the scoped curve for the current active scope.

    Args:
        panel: Panel1 instance
        balance: The balance value to add
        mode: Trading mode (optional, defaults to current_mode)
    """
    if balance is None:
        return

    try:
        import time

        now = time.time()
        balance_float = float(balance)

        # Use current active scope if mode not specified
        if mode is None:
            mode = panel.current_mode

        # Get the scoped curve for (mode, account)
        account = panel.current_account
        scope = (mode, account)

        # CRITICAL FIX: Thread-safe access to equity curve
        panel._equity_mutex.lock()
        try:
            # Get existing curve or create new one
            if scope in panel._equity_curves:
                curve = list(panel._equity_curves[scope])  # Work on copy
            else:
                curve = []

            # Append new point
            curve.append((now, balance_float))

            # Limit to last 2 hours to avoid memory bloat
            cutoff_time = now - 7200
            curve = [(x, y) for x, y in curve if x >= cutoff_time]

            # Update scoped dict (thread-safe)
            panel._equity_curves[scope] = curve

            # Update active points if this is the current scope
            if scope == panel._active_scope:
                panel._equity_points = list(curve)

        finally:
            panel._equity_mutex.unlock()

        # UI updates AFTER releasing mutex (prevent deadlock)
        if scope == panel._active_scope:
            # Redraw graph with new point (single repaint)
            from panels.panel1 import equity_graph
            equity_graph.replot_from_cache(panel)
            update_pnl_for_current_tf(panel)

        log.debug(f"[Panel1] Equity updated for {mode}/{account}: {len(curve)} points")

    except Exception as e:
        log.debug(f"[Panel1] update_equity_series_from_balance error: {e}")


def set_pnl_for_timeframe(
    panel,
    pnl_value: Optional[float],
    pnl_pct: Optional[float],
    up: Optional[bool],
) -> None:
    """
    Update PnL display for the current timeframe.

    Args:
        panel: Panel1 instance
        pnl_value: PnL dollar amount
        pnl_pct: PnL percentage
        up: True for positive, False for negative, None for neutral
    """
    panel._pnl_val = pnl_value
    panel._pnl_pct = pnl_pct
    panel._pnl_up = up

    apply_pnl_to_header(panel)
    apply_pnl_to_pills(panel, up)
    recolor_endpoint(panel)


def set_equity_series(panel, points: list[tuple[float, float]]) -> None:
    """
    Store full series in cache and draw only the slice matching the active TF.

    Args:
        panel: Panel1 instance
        points: List of (timestamp, balance) tuples
    """
    panel._equity_points = list(points or [])
    log.debug(f"Cached {len(panel._equity_points)} equity points")

    if not getattr(panel, "_line", None) or not getattr(panel, "_plot", None):
        log.warning("No graph or line available!")
        return

    from panels.panel1 import equity_graph
    equity_graph.replot_from_cache(panel)

    # Calculate and display PnL for the current timeframe
    update_pnl_for_current_tf(panel)


def update_equity_series(panel, xs: list[float], ys: list[float]) -> None:
    """
    Update equity series from separate x/y arrays.

    Args:
        panel: Panel1 instance
        xs: Timestamp array
        ys: Balance array
    """
    try:
        if xs and ys and len(xs) == len(ys):
            set_equity_series(panel, list(zip(xs, ys)))
        else:
            set_equity_series(panel, [])
    except Exception:
        pass


# ================================================================================
# PnL Display Formatting
# ================================================================================

def compose_pnl_header_text(panel) -> str:
    """
    Format PnL as: ICON $amount (percentage%)

    Args:
        panel: Panel1 instance

    Returns:
        Formatted PnL string

    Examples:
        + $50.00 (5.80%) for gains
        - $50.00 (5.80%) for losses
        - $0.00 (0.00%) for neutral/zero
    """
    if panel._pnl_val is None or panel._pnl_pct is None:
        # Panel 1 should show $0.00 (0.00%) in neutral color, not dashes
        return "- $0.00 (0.00%)"

    # Get absolute values (always display positive amounts with icon to show direction)
    pnl_abs = abs(panel._pnl_val)
    pct_abs = abs(panel._pnl_pct)

    # If PnL is essentially zero, show neutral icon
    if panel._pnl_up is None:
        icon = "-"
    else:
        # Choose icon based on direction
        icon = "+" if panel._pnl_up else "-"

    # Format: ICON $amount (percentage%)
    result = f"{icon} ${pnl_abs:,.2f} ({pct_abs:.2f}%)"
    return result


def apply_pnl_to_header(panel) -> None:
    """
    Update PnL label in header with current values.

    Args:
        panel: Panel1 instance
    """
    col = pnl_color(panel._pnl_up)
    text = compose_pnl_header_text(panel)
    panel.lbl_pnl.setText(text)
    panel.lbl_pnl.setStyleSheet(
        f"color:{col}; "
        f"{ColorTheme.font_css(int(THEME.get('pnl_font_weight', 500)), int(THEME.get('pnl_font_size', 12)))};"
    )


def apply_pnl_to_pills(panel, up: Optional[bool]) -> None:
    """
    Update pill colors based on PnL direction.

    Args:
        panel: Panel1 instance
        up: True for positive, False for negative, None for neutral
    """
    try:
        if hasattr(panel.pills, "set_active_color"):
            panel.pills.set_active_color(pnl_color(up))
        if hasattr(panel.pills, "set_live_dot_visible"):
            panel.pills.set_live_dot_visible(panel._tf == "LIVE")
        if hasattr(panel.pills, "set_live_dot_pulsing"):
            panel.pills.set_live_dot_pulsing(panel._tf == "LIVE")
    except Exception:
        pass


def recolor_endpoint(panel) -> None:
    """
    Update endpoint marker color based on PnL direction.

    Args:
        panel: Panel1 instance
    """
    if not panel.has_graph() or panel._endpoint is None:
        return
    try:
        if panel._pnl_up is None:
            brush = pg.mkBrush(150, 150, 150, 255) if pg else None
        else:
            hexcol = pnl_color(panel._pnl_up)
            brush = pg.mkBrush(QtGui.QColor(hexcol)) if pg else None
        if brush:
            panel._endpoint.setBrush(brush)
    except Exception:
        pass


# ================================================================================
# Mode Management
# ================================================================================

def set_trading_mode(panel, mode: str, account: Optional[str] = None) -> None:
    """
    Update the badge display for DEBUG/SIM/LIVE modes.
    Uses the unified nested pill styling system with THEME-based colors.

    CRITICAL: This implements the ModeChanged contract:
    1. Freeze current state (automatic via scope switch)
    2. Swap to new (mode, account) scope
    3. Reload equity curve from persistent storage
    4. Single repaint

    Args:
        panel: Panel1 instance
        mode: One of "DEBUG", "SIM", or "LIVE"
        account: Account identifier (optional, defaults to empty string)
    """
    mode = mode.upper()
    if mode not in ("DEBUG", "SIM", "LIVE"):
        log.warning(f"Invalid trading mode: {mode}")
        return

    # Use empty string if account not provided
    if account is None:
        account = ""

    # Check if mode/account actually changed
    new_scope = (mode, account)
    if new_scope == panel._active_scope:
        log.debug(f"[Panel1] Mode/account unchanged: {mode}, {account}")
        return

    old_scope = panel._active_scope
    log.info(f"[Panel1] Mode change: {old_scope} -> {new_scope}")

    # 1. Freeze: Current state automatically preserved in scoped dict

    # 2. Swap: Update active scope
    panel.current_mode = mode
    panel.current_account = account
    panel._active_scope = new_scope

    # 3. Reload: Get equity curve for new scope
    panel._equity_points = get_equity_curve(panel, mode, account)

    # Switch theme first to ensure THEME has correct colors for this mode
    switch_theme(mode.lower())

    # Update badge text
    panel.mode_badge.setText(f"{mode}")

    # Apply badge pill styling from THEME (now with correct colors)
    update_badge_style(panel, mode)

    # Update balance label for new scope
    try:
        from core.app_state import get_state_manager
        state = get_state_manager()
        if state:
            if mode == "SIM":
                # Get balance for this specific SIM account
                from core.sim_balance import get_sim_balance
                balance = get_sim_balance(account) if account else 10000.0
            else:
                balance = state.live_balance
            set_account_balance(panel, balance)
            # CRITICAL: Also add point to equity curve for new scope
            update_equity_series_from_balance(panel, balance, mode=mode)
            log.debug(f"[Panel1] Updated balance for {mode}/{account}: ${balance:,.2f}")
    except Exception as e:
        log.debug(f"[Panel1] Could not update balance on mode switch: {e}")

    # 4. Single repaint: Redraw graph with new scope's data
    from panels.panel1 import equity_graph
    equity_graph.replot_from_cache(panel)
    update_pnl_for_current_tf(panel)

    log.info(f"[Panel1] Switched to {mode}/{account} ({len(panel._equity_points)} points)")


def switch_equity_curve_for_mode(panel, mode: str) -> None:
    """
    DEPRECATED: Use set_trading_mode(mode, account) instead.

    Legacy method for backward compatibility. Calls set_trading_mode.

    Args:
        panel: Panel1 instance
        mode: Trading mode
    """
    log.warning("[Panel1] switch_equity_curve_for_mode is deprecated, use set_trading_mode()")
    set_trading_mode(panel, mode, panel.current_account)


def set_mode_live(panel, live: bool) -> None:
    """
    Legacy method for backward compatibility.
    Redirects to set_trading_mode() with appropriate mode.

    Args:
        panel: Panel1 instance
        live: True for LIVE mode, False for SIM mode
    """
    panel._mode_is_live = bool(live)
    panel.mode_badge.setText("LIVE" if live else "SIM")

    # Update neon color based on mode (using theme tokens)
    neon_color = THEME.get("mode_indicator_live", "#FF0000") if live else THEME.get("mode_indicator_sim", "#00FFFF")
    # Convert hex to RGB for rgba background
    hex_color = neon_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    text_color = THEME.get("badge_text_color", "#000000")
    panel.mode_badge.setStyleSheet(
        f"color: {text_color}; "
        f"background: rgba({r}, {g}, {b}, 0.2); "
        f"border: 2px solid {neon_color}; "
        f"border-radius: 6px; "  # Rectangular pill shape
        "padding: 0 10px; "
        f"{ColorTheme.font_css(700, 12)};"
    )

    # Update glow effect color
    neon_glow = QtWidgets.QGraphicsDropShadowEffect()
    neon_glow.setBlurRadius(12)
    neon_glow.setColor(QtGui.QColor(neon_color))
    neon_glow.setOffset(0, 0)
    panel.mode_badge.setGraphicsEffect(neon_glow)


def update_badge_style(panel, mode: str) -> None:
    """
    Apply badge pill styling based on trading mode.
    - Styles mode_badge QLabel (neon pill with background, border, radius, text color)
    - Conditionally applies glow effect (only SIM/LIVE, not DEBUG)

    Args:
        panel: Panel1 instance
        mode: One of "DEBUG", "SIM", or "LIVE"
    """
    mode = mode.upper()

    # Get structural constants from THEME
    badge_radius = int(THEME.get("badge_radius", 8))
    badge_font_size = int(THEME.get("badge_font_size", 8))
    badge_font_weight = int(THEME.get("badge_font_weight", 700))
    glow_blur = int(THEME.get("glow_blur_radius", 12))

    # Get mode-specific colors from THEME
    badge_bg = str(THEME.get("badge_bg_color", "#F5B342"))
    badge_border = str(THEME.get("badge_border_color", "#F5B342"))
    badge_text = str(THEME.get("badge_text_color", "#000000"))
    glow_color = str(THEME.get("glow_color", "none"))

    # Style badge with neon pill (background, border, radius)
    panel.mode_badge.setStyleSheet(
        f"color: {badge_text}; "
        f"background-color: {badge_bg}; "
        f"border: 2px solid {badge_border}; "
        f"border-radius: {badge_radius}px; "
        f"padding: 0px; "
        f"{ColorTheme.font_css(badge_font_weight, badge_font_size)};"
    )

    # Apply glow effect (only for SIM/LIVE, not DEBUG)
    if mode in ("SIM", "LIVE") and glow_color != "none":
        glow = QtWidgets.QGraphicsDropShadowEffect()
        glow.setBlurRadius(glow_blur)
        glow.setColor(QtGui.QColor(glow_color))
        glow.setOffset(0, 0)
        panel.mode_badge.setGraphicsEffect(glow)
    else:
        # Clear glow for DEBUG mode
        panel.mode_badge.setGraphicsEffect(None)
