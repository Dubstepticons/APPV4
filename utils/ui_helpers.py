"""
UI Helper Functions

Common PyQt6 UI layout and widget utilities.
"""

from __future__ import annotations
from typing import Optional

from PyQt6 import QtWidgets, QtCore


def centered_row(widget: QtWidgets.QWidget,
                 alignment: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignCenter,
                 stretch_left: int = 1,
                 stretch_right: int = 1) -> QtWidgets.QHBoxLayout:
    """
    Create a horizontal layout with a centered widget.

    Adds stretches on both sides to center the widget in the available space.

    Args:
        widget: Widget to center in the layout
        alignment: Qt alignment flag (default: AlignCenter)
        stretch_left: Stretch factor for left side (default: 1)
        stretch_right: Stretch factor for right side (default: 1)

    Returns:
        QHBoxLayout with centered widget

    Example:
        >>> label = QLabel("Centered Text")
        >>> layout.addLayout(centered_row(label))
    """
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)

    row.addStretch(stretch_left)
    row.addWidget(widget, 0, alignment)
    row.addStretch(stretch_right)

    return row


def spacer(width: Optional[int] = None,
           height: Optional[int] = None,
           horizontal_policy: QtWidgets.QSizePolicy.Policy = QtWidgets.QSizePolicy.Policy.Expanding,
           vertical_policy: QtWidgets.QSizePolicy.Policy = QtWidgets.QSizePolicy.Policy.Minimum) -> QtWidgets.QSpacerItem:
    """
    Create a spacer item for layouts.

    Args:
        width: Fixed width (None for expanding)
        height: Fixed height (None for expanding)
        horizontal_policy: Horizontal size policy
        vertical_policy: Vertical size policy

    Returns:
        QSpacerItem configured as specified

    Example:
        >>> layout.addItem(spacer(width=20))  # Fixed 20px spacer
        >>> layout.addItem(spacer())  # Expanding spacer
    """
    w = width if width is not None else 0
    h = height if height is not None else 0
    return QtWidgets.QSpacerItem(w, h, horizontal_policy, vertical_policy)


def separator(orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Horizontal,
              line_width: int = 1,
              frame_shape: QtWidgets.QFrame.Shape = QtWidgets.QFrame.Shape.HLine,
              frame_shadow: QtWidgets.QFrame.Shadow = QtWidgets.QFrame.Shadow.Sunken) -> QtWidgets.QFrame:
    """
    Create a separator line (horizontal or vertical).

    Args:
        orientation: Horizontal or Vertical
        line_width: Width of the line in pixels
        frame_shape: QFrame shape (HLine or VLine)
        frame_shadow: QFrame shadow style

    Returns:
        QFrame configured as a separator

    Example:
        >>> layout.addWidget(separator())  # Horizontal separator
        >>> layout.addWidget(separator(QtCore.Qt.Orientation.Vertical, QtWidgets.QFrame.Shape.VLine))
    """
    frame = QtWidgets.QFrame()
    frame.setFrameShape(frame_shape)
    frame.setFrameShadow(frame_shadow)
    frame.setLineWidth(line_width)

    if orientation == QtCore.Qt.Orientation.Horizontal:
        frame.setFixedHeight(line_width)
    else:
        frame.setFixedWidth(line_width)

    return frame


def clear_layout(layout: QtWidgets.QLayout) -> None:
    """
    Clear all items from a layout.

    Removes and deletes all child widgets and layouts.

    Args:
        layout: Layout to clear

    Example:
        >>> clear_layout(my_layout)
    """
    if layout is None:
        return

    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())
            item.layout().deleteLater()
