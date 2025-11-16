"""
Masked Frame Module

Provides a reusable rounded frame widget with theme-aware background painting.
Used as container for the equity graph in Panel1.

Extracted from panels/panel1.py for modularity.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from config.theme import THEME


class MaskedFrame(QtWidgets.QFrame):
    """
    A QFrame that paints a theme background and automatically masks itself
    to the painted geometry. Children (like PlotWidget) are clipped to this shape.

    Features:
    - Rounded corners (radius from theme)
    - Theme-aware background color
    - Automatic child widget clipping
    - Dynamic color updates

    Usage:
        frame = MaskedFrame(parent)
        frame.set_background_color("#1a1a1a")
        plot_widget.setParent(frame)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_color = THEME.get("bg_secondary", "#000000")

    def set_background_color(self, color: str) -> None:
        """
        Update the background color dynamically.

        Args:
            color: Hex color string (e.g., "#1a1a1a")
        """
        self._bg_color = color
        self.update()  # Trigger repaint

    def _shape_path(self) -> QtGui.QPainterPath:
        """
        Define the shape path for the frame.

        Returns:
            QPainterPath with rounded rectangle

        Note:
            Change this to any geometry later (waves, polygons, etc.)
        """
        rect = QtCore.QRectF(self.rect())  # Convert QRect -> QRectF
        r = float(THEME.get("card_radius", 8))
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, r, r)
        return path

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the frame with rounded corners and mask.

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
