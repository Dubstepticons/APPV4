"""
Panel1 Helper Widgets

Extracted from monolithic panel1.py for better maintainability.
Contains small, reusable UI components.
"""

from __future__ import annotations
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from config.theme import THEME


class MaskedFrame(QtWidgets.QFrame):
    """
    A QFrame that paints a theme background and automatically masks itself
    to the painted geometry. Children (like PlotWidget) are clipped to this shape.

    This widget provides a themed, rounded-corner container that clips
    its children to match the painted shape.

    Usage:
        >>> frame = MaskedFrame()
        >>> frame.set_background_color("#1E1E1E")
        >>> layout = QVBoxLayout(frame)
        >>> layout.addWidget(child_widget)
    """

    def __init__(self, parent=None):
        """
        Initialize masked frame.

        Args:
            parent: Parent Qt widget
        """
        super().__init__(parent)
        self._bg_color = THEME.get("bg_secondary", "#000000")

    def set_background_color(self, color: str) -> None:
        """
        Update the background color dynamically.

        Args:
            color: Hex color string (e.g., "#1E1E1E")
        """
        self._bg_color = color
        self.update()  # Trigger repaint

    def _shape_path(self) -> QtGui.QPainterPath:
        """
        Define the shape geometry.

        Currently creates rounded rectangle. Can be customized
        for waves, polygons, or other shapes.

        Returns:
            QPainterPath defining the widget shape
        """
        rect = QtCore.QRectF(self.rect())
        radius = float(THEME.get("card_radius", 8))
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the background and apply mask.

        Args:
            event: Paint event from Qt
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Paint background (no border)
        path = self._shape_path()
        painter.setBrush(QtGui.QBrush(QtGui.QColor(self._bg_color)))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # Clip widget and children to shape
        region = QtGui.QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

        # Explicitly end painter (avoid QBackingStore warnings)
        painter.end()

        # Continue normal painting
        super().paintEvent(event)


def pnl_color(up: Optional[bool]) -> str:
    """
    Return theme color for P&L direction.

    Args:
        up: True for profit (green), False for loss (red), None for neutral

    Returns:
        Hex color string from theme

    Example:
        >>> color = pnl_color(up=True)   # Green
        >>> color = pnl_color(up=False)  # Red
        >>> color = pnl_color(up=None)   # Neutral
    """
    if up is True:
        return THEME.get("positive", "#00FF00")
    elif up is False:
        return THEME.get("negative", "#FF0000")
    else:
        return THEME.get("text", "#FFFFFF")
