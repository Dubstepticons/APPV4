"""
UI Builder Module

Handles UI construction: panels, layout, DTC initialization, and initial state setup.
Extracted from core/app_manager.py for modularity.

Functions:
- build_ui(): Create panels, initialize DTC, setup cross-panel linkage
- initialize_panel1_balance(): Load equity curve and set starting balance
"""

import contextlib
import os
from PyQt6 import QtWidgets
from config.theme import THEME
from panels.panel1 import Panel1, pnl_manager
from panels.panel2 import Panel2
from panels.panel3 import Panel3
from utils.logger import get_logger

log = get_logger("UIBuilder")


def build_ui(main_window) -> None:
    """
    Build UI panels and initialize DTC connection.

    Creates central widget, instantiates all three panels,
    initializes DTC connection, sets up cross-panel signals,
    and loads initial balance state.

    Args:
        main_window: MainWindow instance to populate with UI
    """
    # Vertical stacking: Panel1 (balance/investing), Panel2 (live), Panel3 (stats)
    central = QtWidgets.QWidget(main_window)
    central.setObjectName("CentralWidget")

    # Set main background color from theme
    central.setStyleSheet(
        f"QWidget#CentralWidget {{ background: {THEME.get('bg_primary', '#000000')}; }}"
    )
    main_window.setCentralWidget(central)

    outer = QtWidgets.QVBoxLayout(central)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # Create panels
    if os.getenv("DEBUG_DTC", "0") == "1":
        print("DEBUG: About to create panels (Panel1, Panel2, Panel3)...")

    main_window.panel_balance = Panel1()
    if os.getenv("DEBUG_DTC", "0") == "1":
        print("DEBUG: Panel1 created")

    main_window.panel_live = Panel2()
    if os.getenv("DEBUG_DTC", "0") == "1":
        print("DEBUG: Panel2 created")

    main_window.panel_stats = Panel3()
    if os.getenv("DEBUG_DTC", "0") == "1":
        print("DEBUG: Panel3 created")
        log.debug("[Startup] Panels created: Panel1/Panel2/Panel3")

    # Start DTC and diagnostics immediately
    if os.getenv("DEBUG_DTC", "0") == "1":
        print("DEBUG: About to initialize DTC and run diagnostics...")

    try:
        if not getattr(main_window, "_dtc_started", False):
            if os.getenv("DEBUG_DTC", "0") == "1":
                log.debug("[Startup] Direct DTC init + diagnostics (panel-init path)")
                print("DEBUG: Calling _init_dtc()...")

            # Import dtc_manager here to avoid circular imports
            from core.app_manager import dtc_manager

            dtc_manager.init_dtc(main_window)

            if os.getenv("DEBUG_DTC", "0") == "1":
                print("DEBUG: Calling _run_diagnostics_and_push()...")

            dtc_manager.run_diagnostics_and_push(main_window)

            if os.getenv("DEBUG_DTC", "0") == "1":
                print("DEBUG: DTC init and diagnostics completed")

    except Exception as e:
        log.exception(f"[Startup] Direct init after panel build failed: {e}")
        if os.getenv("DEBUG_DTC", "0") == "1":
            print(f"DEBUG: DTC init FAILED: {e}")
            import traceback
            traceback.print_exc()
    finally:
        # Enable timeframe signals after startup work completes
        main_window._startup_done = True
        if os.getenv("DEBUG_DTC", "0") == "1":
            print("DEBUG: Startup done flag set to True")

    # Initialize timeframe pill color to current PnL direction
    with contextlib.suppress(Exception):
        from core.app_manager import theme_manager
        theme_manager.sync_pills_color_from_panel1(main_window)

    # Setup cross-panel communication and layout stacking
    from core.app_manager import signal_coordinator
    signal_coordinator.setup_cross_panel_linkage(main_window, outer)

    # Reassert intended theme after panel construction, in case any panel
    # applied its own global theme during __init__.
    try:
        from core.app_manager import theme_manager
        theme_manager.on_theme_changed(main_window, main_window.current_theme_mode)
    except Exception:
        pass

    # Initialize Panel1's session start balance and equity curve
    initialize_panel1_balance(main_window)


def initialize_panel1_balance(main_window) -> None:
    """
    Initialize Panel1's session start balance and equity curve.

    Loads historical equity curve from database and sets up session baseline.
    This ensures PnL calculates from the session start, not from the first balance update.

    Args:
        main_window: MainWindow instance with panel_balance and _state
    """
    try:
        if not main_window.panel_balance or not main_window._state:
            return

        starting_balance = main_window._state.sim_balance

        # CRITICAL: Load equity curve from database FIRST (before adding any new points)
        # This ensures we don't lose historical data
        main_window.panel_balance._equity_points = pnl_manager.get_equity_curve(main_window.panel_balance, "SIM", "")

        # If we loaded historical data, don't add a new starting point (use the last balance from history)
        # Only add initial point if this is a fresh start with no trades
        if not main_window.panel_balance._equity_points:
            # Store the session start balance for PnL baseline calculation
            main_window.panel_balance._session_start_balance_sim = starting_balance
            main_window.panel_balance._session_start_balance_live = 0.0  # No LIVE balance at startup

            # Also add it to equity curve so graph has initial point
            main_window.panel_balance.update_equity_series_from_balance(starting_balance, mode="SIM")
        else:
            # Use the last point from historical data as session start baseline
            last_balance = main_window.panel_balance._equity_points[-1][1]
            main_window.panel_balance._session_start_balance_sim = last_balance
            main_window.panel_balance._session_start_balance_live = 0.0  # No LIVE balance at startup

        # Display SIM balance by emitting balance signal
        try:
            # Emit the balance signal directly to trigger display
            main_window._state.balanceChanged.emit(starting_balance)
        except Exception:
            pass

        # Redraw graph with loaded equity curve
        if hasattr(main_window.panel_balance, "_replot_from_cache"):
            main_window.panel_balance._replot_from_cache()

        # Concise session start notification
        print(
            f"[SESSION START] SIM Balance: ${starting_balance:,.2f} | "
            f"Equity Points: {len(main_window.panel_balance._equity_points)}"
        )
        log.debug(f"[Startup] Panel1 initialized with SIM balance: ${starting_balance:,.2f}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        log.debug(f"[Startup] Failed to initialize Panel1: {e}")
