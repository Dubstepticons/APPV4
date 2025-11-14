"""
panels/panel1/masked_frame.py

Custom QFrame with rounded background and automatic clipping.

This module provides MaskedFrame - a QFrame that paints a themed background
and automatically masks itself (and its children) to the painted geometry.

Architecture:
- Extends QtWidgets.QFrame
- Theme-aware background
- Automatic child clipping

Usage:
    from panels.panel1.masked_frame import MaskedFrame

    frame = MaskedFrame(parent=widget)
    frame.set_background_color("#1a1a1a")

    # Children (like PlotWidget) are automatically clipped to rounded rect
    plot = pg.PlotWidget(parent=frame)
"""

from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from config.theme import THEME


class MaskedFrame(QtWidgets.QFrame):
    """
    A QFrame that paints a theme background and automatically masks itself
    to the painted geometry.

    Children (like PlotWidget) are clipped to this shape, creating rounded
    corners without manual clipping.

    Features:
    - Theme-aware background color
    - Rounded rect geometry (configurable radius)
    - Automatic child clipping
    - Antialiased painting
    - No border
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """
        Initialize masked frame.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self._bg_color = THEME.get("bg_secondary", "#000000")

    def set_background_color(self, color: str) -> None:
        """
        Update the background color dynamically.

        Args:
            color: Color hex string (e.g., "#1a1a1a")
        """
        self._bg_color = color
        self.update()  # Trigger repaint

    def _shape_path(self) -> QtGui.QPainterPath:
        """
        Define the shape geometry.

        Currently creates a rounded rectangle. Can be changed to any
        geometry later (waves, polygons, etc.).

        Returns:
            QPainterPath defining the frame shape
        """
        rect = QtCore.QRectF(self.rect())  # Convert QRect -> QRectF
        r = float(THEME.get("card_radius", 8))
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, r, r)
        return path

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the frame background and apply mask.

        Steps:
        1. Paint background with themed color
        2. Create mask region from painted shape
        3. Apply mask to clip children

        Args:
            event: Paint event
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # 1) Paint the background (no border)
        path = self._shape_path()
        painter.setBrush(QtGui.QBrush(QtGui.QColor(self._bg_color)))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)  # Remove border
        painter.drawPath(path)

        # 2) Clip this widget (and its children) to that exact shape
        region = QtGui.QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

        # Explicitly end painter to avoid QBackingStore warnings
        painter.end()

        # Continue normal painting
        super().paintEvent(event)
