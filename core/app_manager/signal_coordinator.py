"""
Signal Coordinator Module

Handles cross-panel signal wiring, UI controls setup, and timeframe coordination.
Extracted from core/app_manager.py for modularity.

Functions:
- setup_cross_panel_linkage(): Wire all panel signals and add to layout
- setup_theme_toolbar(): Create theme switcher toolbar
- setup_mode_selector(): Setup mode hotkey (Ctrl+Shift+M)
- setup_reset_balance_hotkey(): Setup balance reset hotkey (Ctrl+Shift+R)
- on_reset_sim_balance_hotkey(): Handle SIM balance reset
- Timeframe change handlers: on_tf_changed, on_live_pills_tf_changed, on_stats_tf_changed
"""

import contextlib
import os
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QKeySequence, QShortcut
from utils.logger import get_logger

log = get_logger("SignalCoordinator")


def setup_cross_panel_linkage(main_window, outer: QtWidgets.QVBoxLayout) -> None:
    """
    Wire cross-panel communication and add panels to layout.

    Establishes signal connections between Panel1, Panel2, and Panel3,
    routes DTC signals, and stacks panels in the main layout.

    Args:
        main_window: MainWindow instance
        outer: QVBoxLayout to add panels to
    """
    # Single source of truth for timeframe
    main_window.current_tf = "LIVE"

    # Link Panel1 <-> Panel3 (existing)
    if hasattr(main_window.panel_balance, "set_stats_panel"):
        main_window.panel_balance.set_stats_panel(main_window.panel_stats)

    # Link Panel3 -> Panel2 for direct data access
    # Panel 3 grabs live trade data from Panel 2 for statistical analysis
    if hasattr(main_window.panel_stats, "set_live_panel"):
        main_window.panel_stats.set_live_panel(main_window.panel_live)
        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug("[Startup] Wired Panel3 -> Panel2 (direct data access)")

    # Stats panel timeframe -> central handler
    if hasattr(main_window.panel_stats, "timeframeChanged"):
        try:
            main_window.panel_stats.timeframeChanged.connect(
                lambda tf: on_stats_tf_changed(main_window, tf),
                type=QtCore.Qt.ConnectionType.UniqueConnection,
            )
            if os.getenv("DEBUG_DTC", "0") == "1":
                log.debug("[Startup] Wired Panel3 timeframe -> _on_stats_tf_changed")
        except Exception:
            pass

    # Panel2 pills timeframe -> central handler
    try:
        pills = getattr(main_window.panel_live, "pills", None)
        if pills is not None and hasattr(pills, "timeframeChanged"):
            pills.timeframeChanged.connect(
                lambda tf: on_live_pills_tf_changed(main_window, tf),
                type=QtCore.Qt.ConnectionType.UniqueConnection,
            )
            if os.getenv("DEBUG_DTC", "0") == "1":
                log.debug("[Startup] Wired Panel2 pills timeframe -> _on_live_pills_tf_changed")
    except Exception:
        pass

    # Refresh Panel 3 stats when Panel 2 reports a closed trade
    # Also trigger Panel 3 to grab data from Panel 2 for analysis
    try:
        if hasattr(main_window.panel_live, "tradesChanged"):

            def _on_trade_changed(payload):
                # Call Panel 3 trade closed handler
                if hasattr(main_window.panel_stats, "on_trade_closed"):
                    try:
                        main_window.panel_stats.on_trade_closed(payload)
                    except Exception:
                        pass

                # Refresh historical stats from database (redundant but safe)
                if hasattr(main_window.panel_stats, "_load_metrics_for_timeframe"):
                    try:
                        main_window.panel_stats._load_metrics_for_timeframe(main_window.panel_stats._tf)
                    except Exception:
                        pass

                # Grab live data from Panel 2 and analyze
                if hasattr(main_window.panel_stats, "analyze_and_store_trade_snapshot"):
                    try:
                        main_window.panel_stats.analyze_and_store_trade_snapshot()
                    except Exception:
                        pass

            main_window.panel_live.tradesChanged.connect(_on_trade_changed)
            log.debug("[Startup] Wired Panel2 tradesChanged -> Panel3 (metrics + live analysis)")
    except Exception:
        pass

    # -------------------- DTC Signal Routing (Removed) --------------------
    # NOTE: DTC signal routing (signal_order, signal_position, signal_balance) has been
    # moved to MessageRouter for centralized handling. MessageRouter auto-subscribes to
    # Blinker signals and handles:
    #   - Order routing to Panel2
    #   - Position routing to Panel2
    #   - Balance routing to Panel1
    #   - Auto-detection of trading mode (LIVE/SIM)
    #   - Balance refresh requests after order fills
    #   - Qt thread marshaling for UI updates
    #
    # See: core/message_router.py::_subscribe_to_signals() and signal handlers
    # Benefits: Single source of truth, uses helper modules (qt_bridge, trade_mode),
    #           eliminates duplicate code and reduces complexity.
    # -----------------------------------------------------------------------

    # Layout stacking and relative stretch (make all panels equal height)
    outer.addWidget(main_window.panel_balance, 1)
    outer.addWidget(main_window.panel_live, 1)
    outer.addWidget(main_window.panel_stats, 1)


def setup_theme_toolbar(main_window) -> None:
    """
    Setup theme switcher toolbar (ENV-gated).

    Args:
        main_window: MainWindow instance
    """
    try:
        show_toolbar = str(os.getenv("APPSIERRA_SHOW_THEME_TOOLBAR", "0")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        if show_toolbar:
            tb = QtWidgets.QToolBar("Mode", main_window)
            tb.setMovable(False)
            main_window.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, tb)

            act_debug = QtWidgets.QAction("DEBUG", main_window)
            act_sim = QtWidgets.QAction("SIM", main_window)
            act_live = QtWidgets.QAction("LIVE", main_window)

            # Import theme_manager for callbacks
            from core.app_manager import theme_manager

            act_debug.triggered.connect(lambda: theme_manager.set_theme_mode(main_window, "DEBUG"))
            act_sim.triggered.connect(lambda: theme_manager.set_theme_mode(main_window, "SIM"))
            act_live.triggered.connect(lambda: theme_manager.set_theme_mode(main_window, "LIVE"))

            tb.addAction(act_debug)
            tb.addAction(act_sim)
            tb.addAction(act_live)

            # Optional: Optimize Archives action (manual trigger for SQLite VACUUM)
            try:
                act_opt = QtWidgets.QAction("Optimize Archives", main_window)
                act_opt.triggered.connect(lambda: theme_manager.optimize_archives_ui(main_window))
                tb.addSeparator()
                tb.addAction(act_opt)
            except Exception:
                pass
    except Exception:
        pass


def setup_mode_selector(main_window) -> None:
    """
    Setup mode selector hotkey (Ctrl+Shift+M).

    Args:
        main_window: MainWindow instance
    """
    try:
        from utils.mode_selector import setup_mode_hotkey

        setup_mode_hotkey(main_window)
        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug("[Startup] Mode selector hotkey (Ctrl+Shift+M) enabled")
    except Exception as e:
        if os.getenv("DEBUG_DTC", "0") == "1":
            log.warning(f"[Startup] Could not setup mode hotkey: {e}")


def setup_reset_balance_hotkey(main_window) -> None:
    """
    Setup SIM balance reset hotkey (Ctrl+Shift+R).

    Args:
        main_window: MainWindow instance
    """
    try:
        shortcut = QShortcut(QKeySequence("Ctrl+Shift+R"), main_window)
        shortcut.activated.connect(lambda: on_reset_sim_balance_hotkey(main_window))
        if os.getenv("DEBUG_DTC", "0") == "1":
            log.debug("[Startup] Reset balance hotkey (Ctrl+Shift+R) enabled")
    except Exception as e:
        if os.getenv("DEBUG_DTC", "0") == "1":
            log.warning(f"[Startup] Could not setup reset balance hotkey: {e}")


def on_reset_sim_balance_hotkey(main_window) -> None:
    """
    Handler for Ctrl+Shift+R - Reset SIM balance to $10K.
    Called when user presses the hotkey.

    Args:
        main_window: MainWindow instance
    """
    try:
        from core.sim_balance import get_sim_balance_manager

        # Reset SIM balance in both places
        if main_window._state:
            new_balance = main_window._state.reset_sim_balance_to_10k()
        else:
            # Fallback to sim_balance manager
            mgr = get_sim_balance_manager()
            new_balance = mgr.reset_balance()

        # Update Panel1 display
        if main_window.panel_balance:
            main_window.panel_balance.set_account_balance(new_balance)
            main_window.panel_balance.update_equity_series_from_balance(new_balance, mode="SIM")

        log.info(f"[Hotkey] SIM balance reset to ${new_balance:,.2f}")

        # Show user feedback
        try:
            QMessageBox.information(
                main_window,
                "SIM Balance Reset",
                f"SIM balance has been reset to ${new_balance:,.2f}"
            )
        except Exception:
            pass

    except Exception as e:
        log.error(f"[Hotkey] Error resetting SIM balance: {e}", exc_info=True)


# -------------------- Timeframe Change Handlers --------------------

def on_tf_changed(main_window, tf: str) -> None:
    """
    Central timeframe handler: called by Panel2 pills and Panel3 stats.
    Validates TF, persists state, and fans out updates to panels.

    Args:
        main_window: MainWindow instance
        tf: Timeframe string ("LIVE", "1D", "1W", "1M", "3M", "YTD")
    """
    try:
        if tf not in ("LIVE", "1D", "1W", "1M", "3M", "YTD"):
            return

        main_window.current_tf = tf

        # Panel1 drives the graph windowing & endpoint recolor
        if hasattr(main_window, "panel_balance"):
            main_window.panel_balance.set_timeframe(tf)

        # Optional: if Panel2 needs to react locally to TF, forward it
        if hasattr(main_window, "panel_live") and hasattr(main_window.panel_live, "set_timeframe"):
            with contextlib.suppress(Exception):
                main_window.panel_live.set_timeframe(tf)  # harmless if no-op

        # Keep LIVE-dot visibility/pulsing correct in Panel2
        try:
            if hasattr(main_window.panel_live, "set_live_dot_visible"):
                main_window.panel_live.set_live_dot_visible(tf == "LIVE")
            if hasattr(main_window.panel_live, "set_live_dot_pulsing"):
                main_window.panel_live.set_live_dot_pulsing(tf == "LIVE")
        except Exception:
            pass

        # Also refresh the pill highlight color from current PnL direction
        from core.app_manager import theme_manager
        theme_manager.sync_pills_color_from_panel1(main_window)

    except Exception:
        pass


def on_live_pills_tf_changed(main_window, tf: str) -> None:
    """
    Panel 2 timeframe pills changed: update ONLY Panel 1 timeframe.

    Args:
        main_window: MainWindow instance
        tf: Timeframe string
    """
    try:
        if not getattr(main_window, "_startup_done", False):
            return

        if tf not in ("LIVE", "1D", "1W", "1M", "3M", "YTD"):
            return

        main_window.current_tf = tf

        if hasattr(main_window, "panel_balance"):
            main_window.panel_balance.set_timeframe(tf)

        # Visual sync for pills color based on Panel1 PnL direction
        from core.app_manager import theme_manager
        theme_manager.sync_pills_color_from_panel1(main_window)

    except Exception:
        pass


def on_stats_tf_changed(main_window, tf: str) -> None:
    """
    Stats (Panel 3) timeframe changed: do not propagate globally.

    Args:
        main_window: MainWindow instance
        tf: Timeframe string
    """
    try:
        if not getattr(main_window, "_startup_done", False):
            return

        if tf not in ("1D", "1W", "1M", "3M", "YTD"):
            return

        # Panel 3 handles its own cells; no global actions here.
        return

    except Exception:
        pass
