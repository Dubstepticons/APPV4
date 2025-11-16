"""
Main Window Module

MainWindow class that orchestrates all application components.
Delegates to specialized modules for UI building, theme management, DTC handling, and signal coordination.

This is the main entry point for the application window.
"""

from __future__ import annotations

import os
from PyQt6 import QtCore, QtWidgets

from config.settings import DEBUG_DATA
from config.theme import THEME, ColorTheme, switch_theme
from utils.logger import get_logger
from services.trade_constants import SIM_STARTING_BALANCE

# Import helper modules
from core.app_manager import ui_builder, theme_manager, dtc_manager, signal_coordinator

# Module logger
log = get_logger("AppManager")
if os.getenv("DEBUG_DTC", "0") == "1":
    print("DEBUG: app_manager.window module loaded, logger initialized")

try:
    if os.getenv("DEBUG_DTC", "0") == "1":
        log.debug("[Startup] app_manager module loaded")
except Exception as e:
    if os.getenv("DEBUG_DTC", "0") == "1":
        print(f"DEBUG: Logger TEST FAILED at module level: {e}")
        import traceback
        traceback.print_exc()


class MainWindow(QtWidgets.QMainWindow):
    """
    Main application window tying together all three panels, theme logic, and DTC wiring.

    Delegates implementation to specialized modules:
    - ui_builder: Panel creation and layout
    - theme_manager: Theme switching and visual updates
    - dtc_manager: DTC client initialization and signal handling
    - signal_coordinator: Cross-panel signal wiring and timeframe coordination
    """

    themeChanged = QtCore.pyqtSignal(str)  # emits "DEBUG" | "SIM" | "LIVE"

    def __init__(self) -> None:
        super().__init__()

        if os.getenv("DEBUG_DTC", "0") == "1":
            print("DEBUG: MainWindow.__init__ STARTING")

        try:
            log.info("[startup] Initializing MainWindow")
        except Exception as e:
            if os.getenv("DEBUG_DTC", "0") == "1":
                print(f"DEBUG: Logger FAILED: {e}")
                import traceback
                traceback.print_exc()

        # Initialize state and UI
        self._setup_window()
        self._setup_state_manager()
        self._setup_theme()
        self._build_ui()
        self._setup_theme_toolbar()
        self._setup_mode_selector()
        self._setup_reset_balance_hotkey()

        if os.getenv("DEBUG_DTC", "0") == "1":
            print("DEBUG: MainWindow.__init__ COMPLETE")

        try:
            log.info("[startup] MainWindow initialized")
        except Exception:
            pass

    # -------------------- Initialization Methods --------------------

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("APPSIERRA")
        self.setMinimumSize(1100, 720)

    def _setup_state_manager(self) -> None:
        """Initialize state manager with error handling."""
        try:
            # Initialize database tables first
            from data.db_engine import init_db
            init_db()

            from core.state_manager import StateManager
            from core.app_state import set_state_manager

            self._state = StateManager()

            # Register globally for access throughout the app
            set_state_manager(self._state)

            # Load SIM balance from database via UnifiedBalanceManager
            from services.balance_service import load_sim_balance_from_trades
            account = self._state.current_account or "Sim1"
            loaded_balance = load_sim_balance_from_trades(account)
        except Exception as e:
            error_msg = str(e).replace('\u2705', '[OK]').replace('\u2717', '[FAIL]')
            import traceback
            traceback.print_exc()
            self._state = None

    def _setup_theme(self) -> None:
        """Configure theme system and apply initial theme."""
        self.current_theme_mode: str = "LIVE"  # default to LIVE mode

        # Startup guards
        self._post_construct_invoked: bool = False
        self._dtc_started: bool = False

        # Connect theme change signal
        self.themeChanged.connect(lambda mode: theme_manager.on_theme_changed(self, mode))

        # Suppress timeframe handling during startup init
        self._startup_done: bool = False

        # Apply base theme BEFORE building widgets to avoid initial flicker
        try:
            switch_theme(self.current_theme_mode.lower())
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.setFont(
                    ColorTheme.qfont(
                        int(THEME.get("ui_font_weight", 500)),
                        int(THEME.get("ui_font_size", 14)),
                    )
                )
        except Exception:
            pass

    def _build_ui(self) -> None:
        """Build UI panels and initialize DTC connection (delegates to ui_builder)."""
        ui_builder.build_ui(self)

    def _setup_theme_toolbar(self) -> None:
        """Setup theme switcher toolbar (delegates to signal_coordinator)."""
        signal_coordinator.setup_theme_toolbar(self)

    def _setup_mode_selector(self) -> None:
        """Setup mode selector hotkey (delegates to signal_coordinator)."""
        signal_coordinator.setup_mode_selector(self)

    def _setup_reset_balance_hotkey(self) -> None:
        """Setup SIM balance reset hotkey (delegates to signal_coordinator)."""
        signal_coordinator.setup_reset_balance_hotkey(self)

    # -------------------- Theme Methods (delegate to theme_manager) --------------------

    def _set_theme_mode(self, mode: str) -> None:
        """Switch theme mode (delegates to theme_manager)."""
        theme_manager.set_theme_mode(self, mode)

    def on_theme_changed(self, mode: str) -> None:
        """Respond to theme mode changes (delegates to theme_manager)."""
        theme_manager.on_theme_changed(self, mode)

    # -------------------- Timeframe Methods (delegate to signal_coordinator) --------------------

    def _on_tf_changed(self, tf: str) -> None:
        """Central timeframe handler (delegates to signal_coordinator)."""
        signal_coordinator.on_tf_changed(self, tf)

    def _on_timeframe_changed(self, tf: str) -> None:
        """Back-compat delegate (delegates to signal_coordinator)."""
        signal_coordinator.on_live_pills_tf_changed(self, tf)

    def _on_live_pills_tf_changed(self, tf: str) -> None:
        """Panel 2 timeframe pills changed (delegates to signal_coordinator)."""
        signal_coordinator.on_live_pills_tf_changed(self, tf)

    def _on_stats_tf_changed(self, tf: str) -> None:
        """Stats (Panel 3) timeframe changed (delegates to signal_coordinator)."""
        signal_coordinator.on_stats_tf_changed(self, tf)

    # -------------------- DTC Methods (delegate to dtc_manager) --------------------

    def _init_dtc(self) -> None:
        """Initialize DTC client (delegates to dtc_manager)."""
        dtc_manager.init_dtc(self)

    def _connect_dtc_signals(self) -> None:
        """Wire DTC client signals (delegates to dtc_manager)."""
        dtc_manager.connect_dtc_signals(self)

    def _run_diagnostics_and_push(self) -> None:
        """Run optional startup diagnostics (delegates to dtc_manager)."""
        dtc_manager.run_diagnostics_and_push(self)

    # -------------------- Helper Methods --------------------

    def _pnl_color_from_direction(self, up: object) -> str:
        """Derive a HEX color for PnL direction (delegates to theme_manager)."""
        return theme_manager.pnl_color_from_direction(up)

    def _sync_pills_color_from_panel1(self) -> None:
        """Read Panel1's current PnL direction and apply it to the active pill color (delegates to theme_manager)."""
        theme_manager.sync_pills_color_from_panel1(self)

    def _optimize_archives_ui(self) -> None:
        """Manual trigger to VACUUM SQLite archive databases (delegates to theme_manager)."""
        theme_manager.optimize_archives_ui(self)

    def _on_reset_sim_balance_hotkey(self) -> None:
        """Handler for Ctrl+Shift+R (delegates to signal_coordinator)."""
        signal_coordinator.on_reset_sim_balance_hotkey(self)

    def _setup_cross_panel_linkage(self, outer: QtWidgets.QVBoxLayout) -> None:
        """Wire cross-panel communication (delegates to signal_coordinator)."""
        signal_coordinator.setup_cross_panel_linkage(self, outer)

    # -------------------- Qt Overrides --------------------

    def closeEvent(self, event) -> None:
        """Called when the app is closing. Log final balance state."""
        try:
            if self._state:
                final_balance = self._state.sim_balance
                print(f"\n{'='*80}")
                print(f"[APP CLOSING] Final Balance Check")
                print(f"{'='*80}")
                print(f"  Final SIM Balance: ${final_balance:,.2f}")
                print(f"  Starting Balance: $10,000.00")
                print(f"  Session P&L: ${final_balance - SIM_STARTING_BALANCE:+,.2f}")
                print(f"  Status: {'PERSISTENT [OK]' if final_balance != SIM_STARTING_BALANCE else 'Default (no trades)'}")
                print(f"{'='*80}\n")
                log.info(f"[Shutdown] App closing with SIM balance: ${final_balance:,.2f}")
        except Exception as e:
            print(f"[ERROR] Failed to log closing state: {e}")

        super().closeEvent(event)
