"""
utils/ui_helpers.py

UI helper functions for PyQt6 layouts and widgets.
"""

from __future__ import annotations

from PyQt6 import QtWidgets


def centered_row(widget: QtWidgets.QWidget) -> QtWidgets.QHBoxLayout:
    """
    Create a centered horizontal layout containing a single widget.

    Args:
        widget: Widget to center in the layout

    Returns:
        QHBoxLayout with widget centered (stretch-widget-stretch pattern)
    """
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addStretch(1)
    layout.addWidget(widget)
    layout.addStretch(1)
    return layout
