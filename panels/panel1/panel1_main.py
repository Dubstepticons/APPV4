"""
panels/panel1/panel1_main.py

Panel1 orchestrator - Wires all decomposed modules together.

This module is the thin orchestrator that:
- Creates UI widgets (balance, PnL, graph container)
- Instantiates all submodules
- Wires signal connections
- Provides backwards-compatible API

Architecture:
- Thin orchestration layer (minimal logic)
- Delegates to specialized modules
- Clean separation of concerns

Usage:
    from panels.panel1.panel1_main import Panel1

    panel = Panel1()
    panel.set_trading_mode(mode="SIM", account="Test1")
    panel.set_timeframe("1D")
    panel.set_account_balance(10000.0)
"""

from __future__ import annotations

import contextlib
from typing import Optional

from PyQt6 import QtCore, QtWidgets, QtGui

from config.theme import THEME, ColorTheme
from panels.panel1.equity_chart import EquityChart
from panels.panel1.equity_state import EquityStateManager
from panels.panel1.helpers import fmt_money, fmt_pct, pnl_color
from panels.panel1.hover_handler import HoverHandler
from panels.panel1.masked_frame import MaskedFrame
from panels.panel1.pnl_calculator import PnLCalculator
from panels.panel1.timeframe_manager import TimeframeManager
from utils.logger import get_logger
from utils.theme_mixin import ThemeAwareMixin
from widgets.connection_icon import ConnectionIcon

log = get_logger(__name__)


class Panel1(ThemeAwareMixin, QtWidgets.QWidget):
    """
    Panel1 - Equity chart with balance tracking.

    Decomposed architecture with 7 focused modules:
    - helpers: Formatting utilities
    - masked_frame: Rounded container
    - pnl_calculator: PnL calculations
    - timeframe_manager: Timeframe filtering
    - equity_state: Thread-safe state management (CRITICAL)
    - equity_chart: PyQtGraph rendering with animation
    - hover_handler: Mouse interactions

    Public API:
    - set_trading_mode(mode, account)
    - set_timeframe(tf)
    - set_account_balance(balance)
    - update_equity_series_from_balance(balance, mode)
    - set_connection_status(connected)
    - refresh()
    """

    # Signals
    timeframeChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """
        Initialize Panel1.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        # Current state
        self._current_timeframe: str = "LIVE"
        self._current_mode: str = "SIM"
        self._current_account: str = ""
        self._current_balance: Optional[float] = None

        # PnL state
        self._pnl_up: Optional[bool] = None
        self._pnl_val: Optional[float] = None
        self._pnl_pct: Optional[float] = None

        # Module instances
        self._equity_state: EquityStateManager = EquityStateManager(parent=self)
        self._equity_chart: EquityChart = EquityChart(parent=self)
        self._hover_handler: Optional[HoverHandler] = None  # Created after plot

        # UI widgets (created in _build_ui)
        self.lbl_balance: QtWidgets.QLabel = None
        self.lbl_pnl: QtWidgets.QLabel = None
        self.lbl_title: QtWidgets.QLabel = None
        self.mode_badge: QtWidgets.QLabel = None
        self.conn_icon: ConnectionIcon = None
        self.graph_container: MaskedFrame = None

        # External references (set by MainWindow)
        self.pills = None  # Timeframe pills (set externally)

        # Build UI
        self._build_ui()

        # Initialize modules
        self._init_modules()

        # Wire signals
        self._wire_signals()

        # Initialize display
        self.set_pnl_for_timeframe(pnl_value=0.0, pnl_pct=0.0, up=None)

    def _build_ui(self) -> None:
        """
        Build UI layout.

        Creates:
        - Header (INVESTING label + mode badge + connection icon)
        - Balance and PnL labels
        - Graph container (MaskedFrame)
        """
        self.setObjectName("Panel1")
        self.setStyleSheet(f"QWidget#Panel1 {{ background:{THEME.get('bg_panel', '#000000')}; }}")

        # Root layout
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header (INVESTING + badge + connection icon)
        header = self._build_header()
        root.addWidget(header)

        # Balance + PnL labels
        vals_container = QtWidgets.QHBoxLayout()
        vals_container.setContentsMargins(0, 0, 0, 0)
        vals_container.setSpacing(0)

        vals_col = QtWidgets.QVBoxLayout()
        vals_col.setContentsMargins(0, 0, 0, 0)
        vals_col.setSpacing(12)

        self.lbl_balance = QtWidgets.QLabel("--")
        self.lbl_balance.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lbl_balance.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.lbl_balance.setStyleSheet(
            f"color:{THEME.get('ink', '#E5E7EB')}; "
            f"{ColorTheme.font_css(int(THEME.get('balance_font_weight', 500)), int(THEME.get('balance_font_size', 18)))};"
        )

        self.lbl_pnl = QtWidgets.QLabel("--  --")
        self.lbl_pnl.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lbl_pnl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
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

        # Graph container (MaskedFrame)
        self.graph_container = MaskedFrame()
        self.graph_container.setMinimumHeight(200)
        self.graph_container.setMinimumWidth(200)
        self.graph_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )

        graph_layout = QtWidgets.QVBoxLayout(self.graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(0)

        root.addWidget(self.graph_container, 1)

    def _build_header(self) -> QtWidgets.QWidget:
        """
        Build header row.

        Returns:
            Widget containing header layout
        """
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        # "INVESTING" label
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

        # Gap
        header.addSpacing(int(THEME.get("badge_gap", 4)))

        # Mode badge
        self.mode_badge = QtWidgets.QLabel("DEBUG")
        self.mode_badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.mode_badge.setFixedHeight(int(THEME.get("badge_height", 16)))
        self.mode_badge.setFixedWidth(int(THEME.get("badge_width", 50)))
        header.addWidget(self.mode_badge, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        self._update_badge_style("DEBUG")

        # Stretch
        header.addStretch(1)

        # Connection icon
        self.conn_icon = ConnectionIcon()
        self.conn_icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        header.addWidget(self.conn_icon, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        container = QtWidgets.QWidget()
        container.setLayout(header)
        return container

    def _update_badge_style(self, mode: str) -> None:
        """
        Update badge styling for mode.

        Args:
            mode: Trading mode ("DEBUG", "SIM", "LIVE")
        """
        mode = mode.upper()

        badge_radius = int(THEME.get("badge_radius", 8))
        badge_font_size = int(THEME.get("badge_font_size", 8))
        badge_font_weight = int(THEME.get("badge_font_weight", 700))
        glow_blur = int(THEME.get("glow_blur_radius", 12))

        badge_bg = str(THEME.get("badge_bg_color", "#F5B342"))
        badge_border = str(THEME.get("badge_border_color", "#F5B342"))
        badge_text = str(THEME.get("badge_text_color", "#000000"))
        glow_color = str(THEME.get("glow_color", "none"))

        self.mode_badge.setStyleSheet(
            f"color: {badge_text}; "
            f"background-color: {badge_bg}; "
            f"border: 2px solid {badge_border}; "
            f"border-radius: {badge_radius}px; "
            f"padding: 0px; "
            f"{ColorTheme.font_css(badge_font_weight, badge_font_size)};"
        )

        if glow_color != "none" and glow_color.startswith("#"):
            glow_effect = QtWidgets.QGraphicsDropShadowEffect()
            glow_effect.setBlurRadius(glow_blur)
            glow_effect.setColor(QtGui.QColor(glow_color))
            glow_effect.setOffset(0, 0)
            self.mode_badge.setGraphicsEffect(glow_effect)
        else:
            self.mode_badge.setGraphicsEffect(None)

    def _init_modules(self) -> None:
        """
        Initialize all modules.

        Creates:
        - Equity chart (PlotWidget)
        - Hover handler
        - Starts animation
        """
        # Create chart
        plot_widget = self._equity_chart.create_plot_widget()
        if plot_widget is None:
            log.error("Failed to create plot widget")
            return

        # Add plot to graph container
        layout = self.graph_container.layout()
        layout.addWidget(plot_widget, 1)

        # Create hover handler (needs plot and viewbox)
        vb = self._equity_chart.get_plot_widget().getPlotItem().getViewBox() if self._equity_chart.has_plot() else None
        if vb is not None:
            self._hover_handler = HoverHandler(
                plot_widget=plot_widget,
                view_box=vb,
                on_balance_update=self._on_hover_balance_update,
                on_pnl_update=self._on_hover_pnl_update,
                parent=self
            )
            self._hover_handler.init_hover_elements()

        # Start chart animation
        self._equity_chart.start_animation()

    def _wire_signals(self) -> None:
        """
        Wire signals between modules.

        Connects:
        - Equity state signals to chart updates
        """
        # Connect equity state loaded signal
        self._equity_state.equityCurveLoaded.connect(self._on_equity_curve_loaded)

    def _on_equity_curve_loaded(self, mode: str, account: str, points: list[tuple[float, float]]) -> None:
        """
        Handle equity curve loaded from database.

        Args:
            mode: Trading mode
            account: Account name
            points: List of (timestamp, balance) tuples
        """
        # Check if this is for the active scope
        if mode == self._current_mode and account == self._current_account:
            # Update chart with filtered points
            filtered = TimeframeManager.filter_points_for_timeframe(
                points=points,
                timeframe=self._current_timeframe
            )
            self._equity_chart.replot(filtered, self._current_timeframe)

            # Update hover handler
            if self._hover_handler:
                self._hover_handler.set_data(filtered, self._current_timeframe)

            # Calculate PnL
            self._update_pnl_for_timeframe(points)

    def _on_hover_balance_update(self, formatted_balance: str) -> None:
        """
        Handle hover balance update.

        Args:
            formatted_balance: Formatted balance string
        """
        self.lbl_balance.setText(formatted_balance)

    def _on_hover_pnl_update(self, pnl_text: str, color: str) -> None:
        """
        Handle hover PnL update.

        Args:
            pnl_text: Formatted PnL text
            color: Color hex string
        """
        self.lbl_pnl.setText(pnl_text)
        self.lbl_pnl.setStyleSheet(
            f"color:{color}; "
            f"{ColorTheme.font_css(int(THEME.get('pnl_font_weight', 500)), int(THEME.get('pnl_font_size', 12)))};"
        )

    def _update_pnl_for_timeframe(self, points: list[tuple[float, float]]) -> None:
        """
        Calculate and display PnL for current timeframe.

        Args:
            points: List of (timestamp, balance) tuples
        """
        if not points:
            return

        import time

        # Get current balance (last point)
        current_balance = points[-1][1]
        current_time = time.time()

        # Get baseline balance for timeframe
        baseline = PnLCalculator.get_baseline_for_timeframe(
            points=[(int(p[0]), p[1]) for p in points],
            timeframe=self._current_timeframe,
            current_time=int(current_time)
        )

        if baseline is None:
            return

        # Calculate PnL
        pnl_result = PnLCalculator.calculate_pnl(current_balance, baseline)

        # Store state
        self._pnl_val = pnl_result["amount"]
        self._pnl_pct = pnl_result["percentage"]
        self._pnl_up = pnl_result["is_positive"]

        # Update display
        self.set_pnl_for_timeframe(self._pnl_val, self._pnl_pct, self._pnl_up)

        # Update chart color
        self._equity_chart.update_endpoint_color(self._pnl_up)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def set_trading_mode(self, mode: str, account: Optional[str] = None) -> None:
        """
        Set trading mode and account.

        Args:
            mode: Trading mode ("DEBUG", "SIM", "LIVE")
            account: Account name (optional)
        """
        self._current_mode = mode
        self._current_account = account or ""

        # Update badge
        self.mode_badge.setText(mode.upper())
        self._update_badge_style(mode)

        # Update equity state scope
        self._equity_state.set_scope(mode, self._current_account)

        # Load equity curve for this scope
        curve = self._equity_state.get_equity_curve(mode, self._current_account)
        if curve:
            self._on_equity_curve_loaded(mode, self._current_account, curve)

    def set_timeframe(self, tf: str) -> None:
        """
        Set timeframe.

        Args:
            tf: Timeframe string ("LIVE", "1D", "1W", "1M", "3M", "YTD")
        """
        if not TimeframeManager.is_valid_timeframe(tf):
            log.warning(f"Invalid timeframe: {tf}")
            return

        self._current_timeframe = tf

        # Get current equity curve
        curve = self._equity_state.get_active_curve()
        if curve:
            # Filter and replot
            filtered = TimeframeManager.filter_points_for_timeframe(
                points=curve,
                timeframe=tf
            )
            self._equity_chart.replot(filtered, tf)

            # Update hover handler
            if self._hover_handler:
                self._hover_handler.set_data(filtered, tf)

            # Update PnL
            self._update_pnl_for_timeframe(curve)

        # Emit signal
        self.timeframeChanged.emit(tf)

    def set_account_balance(self, balance: Optional[float]) -> None:
        """
        Set account balance.

        Args:
            balance: Balance value
        """
        self._current_balance = balance
        self.lbl_balance.setText(fmt_money(balance))

    def update_equity_series_from_balance(self, balance: Optional[float], mode: Optional[str] = None) -> None:
        """
        Add balance point to equity curve.

        Args:
            balance: Balance value
            mode: Trading mode (defaults to current mode)
        """
        if balance is None:
            return

        import time

        mode = mode or self._current_mode
        timestamp = time.time()

        # Add point to equity state
        self._equity_state.add_balance_point(
            balance=balance,
            timestamp=timestamp,
            mode=mode,
            account=self._current_account
        )

        # Update display if this is the active mode
        if mode == self._current_mode:
            # Get updated curve
            curve = self._equity_state.get_active_curve()
            if curve:
                # Filter and replot
                filtered = TimeframeManager.filter_points_for_timeframe(
                    points=curve,
                    timeframe=self._current_timeframe
                )
                self._equity_chart.replot(filtered, self._current_timeframe)

                # Update hover handler
                if self._hover_handler:
                    self._hover_handler.set_data(filtered, self._current_timeframe)

                # Update PnL
                self._update_pnl_for_timeframe(curve)

    def set_connection_status(self, connected: bool) -> None:
        """
        Set connection status.

        Args:
            connected: Connection status
        """
        # Connection icon updates automatically via signals
        pass

    def set_pnl_for_timeframe(self, pnl_value: Optional[float], pnl_pct: Optional[float], up: Optional[bool]) -> None:
        """
        Set PnL display.

        Args:
            pnl_value: PnL amount
            pnl_pct: PnL percentage
            up: True for gains, False for losses, None for neutral
        """
        # Format PnL text
        pnl_text = PnLCalculator.compose_pnl_text(pnl_value, pnl_pct, up)

        # Get color
        col = pnl_color(up)

        # Update display
        self.lbl_pnl.setText(pnl_text)
        self.lbl_pnl.setStyleSheet(
            f"color:{col}; "
            f"{ColorTheme.font_css(int(THEME.get('pnl_font_weight', 500)), int(THEME.get('pnl_font_size', 12)))};"
        )

    def refresh(self) -> None:
        """
        Refresh panel display.
        """
        with contextlib.suppress(Exception):
            self.update()
