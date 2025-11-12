"""
Balance Panel Module

Main Panel1 class with UI construction and coordination.
Delegates to specialized helper modules for graph, PnL, hover, and animations.

Extracted from panels/panel1.py (1784 lines) → 7 focused modules.

Class:
- Panel1: Main balance/investing panel widget

Methods:
- __init__(): Initialize panel and delegate to helpers
- _build_ui(): Construct UI layout
- _build_header(): Create header with balance, badges, and connection icon
- set_stats_panel(): Wire cooperating stats panel
- set_panel_references(): Set panel references for theme sync
- resizeEvent(): Handle window resizing
- Signal handlers: _wire_balance_signal(), _on_balance_changed(), _on_mode_changed()
- ThemeAwareMixin implementation: _build_theme_stylesheet(), _get_theme_children(), _on_theme_refresh()
"""

import contextlib
from typing import Any, Optional
from PyQt6 import QtCore, QtGui, QtWidgets
from config.theme import THEME, ColorTheme, switch_theme
from utils.theme_mixin import ThemeAwareMixin
from utils.logger import get_logger
from widgets.connection_icon import ConnectionIcon

log = get_logger(__name__)

# Try to import pyqtgraph
try:
    import pyqtgraph as pg
except ImportError:
    pg = None


# ================================================================================
# Panel1 Main Class
# ================================================================================

class Panel1(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Panel 1 -- header, graph, timeframe controls, and live readouts.
    Inherits ThemeAwareMixin for standardized theme refresh.

    Delegates to helper modules:
    - masked_frame: Rounded graph container
    - equity_graph: Graph initialization and plotting
    - pnl_manager: PnL calculations and equity loading
    - hover_handler: Mouse hover and crosshair
    - animations: Pulse effects and timers
    """

    timeframeChanged = QtCore.pyqtSignal(str)

    def has_graph(self) -> bool:
        """
        Check if graph is available.

        Returns:
            True if pyqtgraph and plot widget are available
        """
        return (pg is not None) and (getattr(self, "_plot", None) is not None)

    def __init__(self) -> None:
        """
        Initialize Panel1 with all components.

        Creates:
        - UI layout (header, balance/PnL, graph container)
        - Equity graph with PyQtGraph
        - Hover interaction elements
        - Pulse animation timers
        - StateManager signal connections
        """
        log.debug("Init starting")
        super().__init__()

        # Timeframe and mode state
        self._tf: str = "LIVE"
        self._mode_is_live: bool = False
        self._connected: bool = False

        # PnL state
        self._pnl_up: Optional[bool] = None
        self._pnl_val: Optional[float] = None
        self._pnl_pct: Optional[float] = None

        # CRITICAL: Strict (mode, account) scoping for equity curves
        # Key: (mode, account) tuple, Value: list of (timestamp, balance) points
        self._equity_curves: dict[tuple[str, str], list[tuple[float, float]]] = {}

        # Thread safety: QMutex for equity curve access (CRITICAL FIX for race conditions)
        self._equity_mutex = QtCore.QMutex()

        # Current active scope
        self.current_mode: str = "SIM"
        self.current_account: str = ""
        self._active_scope: tuple[str, str] = ("SIM", "")

        # Display mode tracking (initialized to SIM, updated via _on_mode_changed)
        self._current_display_mode: str = "SIM"

        # Legacy compatibility - points to active curve
        self._equity_points: list[tuple[float, float]] = []

        # Track pending async loads to avoid duplicate requests
        self._pending_loads: set[tuple[str, str]] = set()

        # Session start baselines - scoped by (mode, account)
        self._session_start_balances: dict[tuple[str, str], float] = {}
        self._session_start_time: Optional[float] = None

        # Graph items
        self._plot: Optional[Any] = None
        self._vb: Optional[Any] = None  # viewbox reference
        self._line: Optional[Any] = None
        self._endpoint: Optional[Any] = None
        self._pulse_timer: Optional[QtCore.QTimer] = None
        self._equity_update_timer: Optional[QtCore.QTimer] = None  # Periodic equity point timer
        self._pulse_phase: float = 0.0
        self._trail_lines: list[Any] = []
        self._glow_line: Optional[Any] = None
        self._perf_safe: bool = bool(THEME.get("perf_safe", False))
        self._current_color: QtGui.QColor = QtGui.QColor(THEME.get("ink", "#E5E7EB"))
        self._target_color: QtGui.QColor = QtGui.QColor(self._current_color)
        self._ripple_items: list[Any] = []  # Sonar ring items

        # Hover/scrubbing state
        self._hovering: bool = False
        self._scrub_x: Optional[float] = None
        self._hover_seg: Optional[QtWidgets.QGraphicsLineItem] = None
        self._hover_text: Optional[Any] = None  # pg.TextItem

        # Timeframe configs
        self._tf_configs: dict[str, dict[str, Optional[int]]] = {
            "LIVE": {"window_sec": 3600, "snap_sec": 60},
            "1D": {"window_sec": 86400, "snap_sec": 300},
            "1W": {"window_sec": 604800, "snap_sec": 3600},
            "1M": {"window_sec": 2592000, "snap_sec": 14400},
            "3M": {"window_sec": 7776000, "snap_sec": 43200},
            "YTD": {"window_sec": None, "snap_sec": 86400},
        }

        # External references (wired by the app)
        self._peer_panel: Optional[QtWidgets.QWidget] = None  # Panel3 reference
        self._panel2: Optional[QtWidgets.QWidget] = None  # Panel2 reference for theme refresh
        self._panel3: Optional[QtWidgets.QWidget] = None  # Panel3 reference for theme refresh

        # Build & init
        self._build_ui()

        # Delegate to equity_graph module
        from panels.panel1 import equity_graph
        equity_graph.init_graph(self)

        # CRITICAL FIX: Attach plot to container BEFORE initializing hover and pulse
        # This ensures the plot is in the layout and has proper geometry
        if hasattr(self, "_plot") and self._plot is not None:
            equity_graph.attach_plot_to_container(self, self._plot)

        # Delegate to animations module
        from panels.panel1 import animations
        animations.init_pulse(self)

        # Delegate to hover_handler module
        from panels.panel1 import hover_handler
        hover_handler.init_hover_elements(self)

        # Ensure live pill dot is initialized
        animations.ensure_live_pill_dot(self, initial=True)

        # Initialize theme based on default mode
        switch_theme("live" if self._mode_is_live else "sim")
        self._setup_theme()  # Initialize theme (ThemeAwareMixin)

        # Wire balance signal from StateManager
        self._wire_balance_signal()

        # Initialize PnL display to $0.00 (0.00%) in neutral color instead of dashes
        # This happens after wiring so signals are ready
        from panels.panel1 import pnl_manager
        pnl_manager.set_pnl_for_timeframe(self, pnl_value=0.0, pnl_pct=0.0, up=None)

        # Initialize session start time (used for PnL baseline calculation)
        import time
        self._session_start_time = time.time()

        # Schedule size check after UI is fully rendered
        from panels.panel1 import animations
        QtCore.QTimer.singleShot(500, lambda: animations.debug_sizes(self))

    # ================================================================================
    # UI Construction
    # ================================================================================

    def _build_ui(self) -> None:
        """
        Build the main UI layout.

        Creates:
        - Root layout with margins and spacing
        - Header row (INVESTING label, mode badge, connection icon)
        - Balance and PnL labels
        - Graph container (MaskedFrame)
        """
        self.setObjectName("Panel1")
        self.setStyleSheet(f"QWidget#Panel1 {{ background:{THEME.get('bg_panel', '#000000')}; }}")

        # Root layout
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- Unified header (connection + mode + account) ---
        header = self._build_header()
        root.addWidget(header)

        # --- Balance + PnL column (aligned left with INVESTING) ---
        vals_container = QtWidgets.QHBoxLayout()
        vals_container.setContentsMargins(0, 0, 0, 0)
        vals_container.setSpacing(0)

        # Vertical layout for balance and PnL
        vals_col = QtWidgets.QVBoxLayout()
        vals_col.setContentsMargins(0, 0, 0, 0)
        vals_col.setSpacing(12)  # 12px between balance and PnL

        self.lbl_balance = QtWidgets.QLabel("--")
        self.lbl_balance.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lbl_balance.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        # Balance label uses brightest white from skeleton framework
        self.lbl_balance.setStyleSheet(
            f"color:{THEME.get('ink', '#E5E7EB')}; "
            f"{ColorTheme.font_css(int(THEME.get('balance_font_weight', 500)), int(THEME.get('balance_font_size', 18)))};"
        )

        self.lbl_pnl = QtWidgets.QLabel("--  --")
        self.lbl_pnl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lbl_pnl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        # PnL label uses color coordination from start (neutral until data arrives)
        self.lbl_pnl.setStyleSheet(
            f"color:{THEME.get('fg_muted', '#C8CDD3')}; "
            f"{ColorTheme.font_css(int(THEME.get('pnl_font_weight', 500)), int(THEME.get('pnl_font_size', 12)))};"
        )

        vals_col.addWidget(self.lbl_balance)
        vals_col.addWidget(self.lbl_pnl)
        vals_col.addStretch(1)

        vals_container.addLayout(vals_col)
        vals_container.addStretch(1)
        root.addLayout(vals_container)

        # --- Graph container (MaskedFrame handles its own paint) ---
        from panels.panel1.masked_frame import MaskedFrame
        self.graph_container = MaskedFrame()
        # FIX: Set minimum height to prevent container from collapsing to 0
        self.graph_container.setMinimumHeight(200)
        self.graph_container.setMinimumWidth(200)
        self.graph_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )

        graph_layout = QtWidgets.QVBoxLayout(self.graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(0)

        # Make the graph container consume all available vertical space
        root.addWidget(self.graph_container, 1)

    def _build_header(self) -> QtWidgets.QWidget:
        """
        Create the header row with INVESTING label and badge.

        Returns:
            QWidget containing header layout

        Components:
        - INVESTING label (plain text, no pill background)
        - Mode badge (DEBUG/SIM/LIVE) positioned at top right
        - Connection icon (far right)
        """
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        # "INVESTING" label (NO pill background)
        self.lbl_title = QtWidgets.QLabel("INVESTING")
        self.lbl_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lbl_title.setStyleSheet(
            f"color: {THEME.get('investing_text_color', '#C0C0C0')}; "
            f"{ColorTheme.font_css(int(THEME.get('investing_font_weight', 700)), int(THEME.get('investing_font_size', 22)))}; "
            "letter-spacing: 0.6px; "
            "background: transparent; "
            "border: none; "
            "padding: 0px;"
        )
        header.addWidget(self.lbl_title, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        # Small gap between INVESTING and badge
        header.addSpacing(int(THEME.get("badge_gap", 4)))

        # Badge (neon pill) - positioned at top right of INVESTING
        self.mode_badge = QtWidgets.QLabel("DEBUG")  # Default to DEBUG
        self.mode_badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.mode_badge.setFixedHeight(int(THEME.get("badge_height", 16)))
        self.mode_badge.setFixedWidth(int(THEME.get("badge_width", 50)))
        # Align badge to top instead of center to position it at top right of INVESTING
        header.addWidget(self.mode_badge, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        # Style badge (will be updated by set_trading_mode)
        from panels.panel1 import pnl_manager
        pnl_manager.update_badge_style(self, "DEBUG")

        # Add stretch to push connection icon to the right
        header.addStretch(1)

        # Connection icon
        self.conn_icon = ConnectionIcon()
        self.conn_icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        header.addWidget(self.conn_icon, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        container = QtWidgets.QWidget()
        container.setLayout(header)
        return container

    # ================================================================================
    # Panel Linkage
    # ================================================================================

    def set_stats_panel(self, peer_panel: QtWidgets.QWidget) -> None:
        """
        Wire a cooperating stats panel (Panel3) for cross-panel use.

        Args:
            peer_panel: Panel3 widget
        """
        self._peer_panel = peer_panel
        self._panel3 = peer_panel  # Also store for theme refresh

    def set_panel_references(self, panel2=None, panel3=None) -> None:
        """
        Set references to Panel2 and Panel3 for theme synchronization.

        Args:
            panel2: Panel2 widget (optional)
            panel3: Panel3 widget (optional)
        """
        if panel2:
            self._panel2 = panel2
        if panel3:
            self._panel3 = panel3

    def set_connection_status(self, connected: bool) -> None:
        """
        Update connection status.

        Args:
            connected: True if connected, False otherwise
        """
        self._connected = bool(connected)
        with contextlib.suppress(Exception):
            pass

    # ================================================================================
    # Public API - Delegated Methods
    # ================================================================================

    def set_timeframe(self, tf: str) -> None:
        """
        Set timeframe (LIVE/1D/1W/1M/3M/YTD).

        Args:
            tf: Timeframe string
        """
        from panels.panel1 import pnl_manager
        pnl_manager.set_timeframe(self, tf)

    def set_account_balance(self, balance: Optional[float]) -> None:
        """
        Update balance display.

        Args:
            balance: Balance value
        """
        from panels.panel1 import pnl_manager
        pnl_manager.set_account_balance(self, balance)

    def update_equity_series_from_balance(self, balance: Optional[float], mode: Optional[str] = None) -> None:
        """
        Add balance point to equity curve.

        Args:
            balance: Balance value
            mode: Trading mode (optional)
        """
        from panels.panel1 import pnl_manager
        pnl_manager.update_equity_series_from_balance(self, balance, mode)

    def set_pnl_for_timeframe(
        self,
        pnl_value: Optional[float],
        pnl_pct: Optional[float],
        up: Optional[bool],
    ) -> None:
        """
        Update PnL display.

        Args:
            pnl_value: PnL dollar amount
            pnl_pct: PnL percentage
            up: True for positive, False for negative, None for neutral
        """
        from panels.panel1 import pnl_manager
        pnl_manager.set_pnl_for_timeframe(self, pnl_value, pnl_pct, up)

    def set_trading_mode(self, mode: str, account: Optional[str] = None) -> None:
        """
        Switch trading mode (DEBUG/SIM/LIVE).

        Args:
            mode: Trading mode
            account: Account identifier (optional)
        """
        from panels.panel1 import pnl_manager
        pnl_manager.set_trading_mode(self, mode, account)

    def set_mode_live(self, live: bool) -> None:
        """
        Legacy method for backward compatibility.

        Args:
            live: True for LIVE, False for SIM
        """
        from panels.panel1 import pnl_manager
        pnl_manager.set_mode_live(self, live)

    def switch_equity_curve_for_mode(self, mode: str) -> None:
        """
        DEPRECATED: Use set_trading_mode() instead.

        Args:
            mode: Trading mode
        """
        from panels.panel1 import pnl_manager
        pnl_manager.switch_equity_curve_for_mode(self, mode)

    def set_equity_series(self, points: list[tuple[float, float]]) -> None:
        """
        Store equity curve and redraw.

        Args:
            points: List of (timestamp, balance) tuples
        """
        from panels.panel1 import pnl_manager
        pnl_manager.set_equity_series(self, points)

    def update_equity_series(self, xs: list[float], ys: list[float]) -> None:
        """
        Update equity series from x/y arrays.

        Args:
            xs: Timestamp array
            ys: Balance array
        """
        from panels.panel1 import pnl_manager
        pnl_manager.update_equity_series(self, xs, ys)

    def refresh(self) -> None:
        """Refresh the panel display."""
        with contextlib.suppress(Exception):
            self.update()

    # ================================================================================
    # Event Handlers
    # ================================================================================

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        """
        Keep the plot synced with the container's inner rect.

        Args:
            e: Resize event
        """
        try:
            if getattr(self, "_plot", None) and self.graph_container:
                self._plot.setGeometry(self.graph_container.contentsRect())
        except Exception:
            pass
        super().resizeEvent(e)

    def eventFilter(self, obj, event) -> bool:
        """
        Event filter for hover interactions.

        Args:
            obj: Event object
            event: Qt event

        Returns:
            True if event was handled, False otherwise
        """
        from panels.panel1 import hover_handler
        if hover_handler.event_filter(self, obj, event):
            return True
        return super().eventFilter(obj, event)

    def _on_mouse_move(self, pos) -> None:
        """
        Handle mouse movement over graph.

        Args:
            pos: Mouse position in scene coordinates
        """
        from panels.panel1 import hover_handler
        hover_handler.on_mouse_move(self, pos)

    def _on_investing_tf_changed(self, tf: str) -> None:
        """
        Handle timeframe change from pills.

        Args:
            tf: New timeframe
        """
        from panels.panel1 import hover_handler
        hover_handler.on_investing_tf_changed(self, tf)

    # ================================================================================
    # Signal Wiring
    # ================================================================================

    def _wire_balance_signal(self) -> None:
        """Connect StateManager balance and mode signals to update display."""
        try:
            from core.app_state import get_state_manager

            state = get_state_manager()
            if state:
                # Connect balance signal
                if hasattr(state, "balanceChanged"):
                    state.balanceChanged.connect(self._on_balance_changed)
                    log.info("[Panel1] Connected balance signal")

                # Connect mode change signal
                if hasattr(state, "modeChanged"):
                    state.modeChanged.connect(self._on_mode_changed)
                    log.info("[Panel1] Connected mode change signal")
        except Exception as e:
            log.error(f"[Panel1] Failed to wire signals: {e}")

    def _on_balance_changed(self, balance: float) -> None:
        """
        Called when StateManager emits balanceChanged signal.
        CRITICAL: Only display balance for the current trading mode.

        Args:
            balance: New balance value
        """
        try:
            # Get current mode from state manager to know which balance to display
            from core.app_state import get_state_manager
            from panels.panel1 import pnl_manager

            state = get_state_manager()
            current_mode = state.current_mode if state else "SIM"

            # Get the balance for the current mode
            if state:
                display_balance = state.get_balance_for_mode(current_mode)
            else:
                display_balance = balance

            # CRITICAL: Only update display if this balance is for the current mode
            # The balance parameter is ignored - we use get_balance_for_mode to get the right value

            if hasattr(self, "lbl_balance") and self.lbl_balance:
                self.lbl_balance.setText(pnl_manager.fmt_money(display_balance))
                # Force Qt repaint to display the change immediately
                self.lbl_balance.update()
                self.lbl_balance.repaint()
                log.debug(f"[Panel1] Balance updated to: ${display_balance:.2f}")

                # CRITICAL: Also update the equity curve and PnL display for the current timeframe
                self.update_equity_series_from_balance(display_balance, mode=current_mode)

        except Exception as e:
            log.error(f"[Panel1] Error updating balance display: {e}")

    def _on_mode_changed(self, new_mode: str) -> None:
        """
        Called when mode switches (SIM <-> LIVE).

        Args:
            new_mode: New trading mode
        """
        # Update Panel1's display mode to match StateManager
        self._current_display_mode = new_mode

        # CRITICAL: Update balance display for the new mode
        try:
            from core.app_state import get_state_manager
            from panels.panel1 import pnl_manager

            state = get_state_manager()
            if state:
                new_balance = state.get_balance_for_mode(new_mode)
                if hasattr(self, "lbl_balance") and self.lbl_balance:
                    self.lbl_balance.setText(pnl_manager.fmt_money(new_balance))
                    self.lbl_balance.update()
                    self.lbl_balance.repaint()
        except Exception as e:
            pass

        # Refresh the PnL display with the new mode's data
        with contextlib.suppress(Exception):
            from panels.panel1 import pnl_manager
            pnl_manager.update_pnl_for_current_tf(self)

    # ================================================================================
    # ThemeAwareMixin Implementation
    # ================================================================================

    def _build_theme_stylesheet(self) -> str:
        """
        Build Panel1 stylesheet using current THEME (ThemeAwareMixin).

        Returns:
            Stylesheet string
        """
        bg_color = THEME.get("bg_panel", "#000000")
        return f"QWidget#Panel1 {{ background: {bg_color}; }}"

    def _get_theme_children(self) -> list:
        """
        Return child panels that need theme refresh (ThemeAwareMixin).

        Returns:
            List of child widgets
        """
        children = []
        if self._panel2:
            children.append(self._panel2)
        if self._panel3:
            children.append(self._panel3)
        return children

    def _on_theme_refresh(self) -> None:
        """
        Custom theme refresh logic for Panel1 (ThemeAwareMixin).

        Updates:
        - Graph container background
        - Balance label colors
        - PnL label colors
        """
        # Update graph container background
        if hasattr(self, "graph_container") and self.graph_container:
            self.graph_container.set_background_color(THEME.get("bg_secondary", "#000000"))

        # Note: mode_badge is NOT updated here - it's managed by set_trading_mode() or set_mode_live()

        # Update balance label
        if hasattr(self, "lbl_balance") and self.lbl_balance:
            self.lbl_balance.setStyleSheet(
                f"color: {THEME.get('ink', '#E5E7EB')}; "
                f"{ColorTheme.font_css(int(THEME.get('balance_font_weight', 500)), int(THEME.get('balance_font_size', 18)))};"
            )

        # Update PnL label
        from panels.panel1 import pnl_manager
        if hasattr(self, "lbl_pnl") and self.lbl_pnl:
            pnl_color = pnl_manager.pnl_color(self._pnl_up)
            self.lbl_pnl.setStyleSheet(
                f"color: {pnl_color}; "
                f"{ColorTheme.font_css(int(THEME.get('pnl_font_weight', 500)), int(THEME.get('pnl_font_size', 12)))};"
            )

    def _refresh_theme_colors(self) -> None:
        """
        Legacy method for backward compatibility.
        Calls refresh_theme() from ThemeAwareMixin.
        """
        self.refresh_theme()
