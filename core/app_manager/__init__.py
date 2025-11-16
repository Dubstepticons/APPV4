"""
Application Manager Package

Decomposed from monolithic app_manager.py (823 lines) into modular components.

Structure:
- window.py: MainWindow class skeleton and window setup
- ui_builder.py: Panel construction and UI layout
- theme_manager.py: Theme switching, mode selector, toolbar
- dtc_manager.py: DTC client initialization and signal handlers
- signal_coordinator.py: Cross-panel signal wiring and coordination

Usage:
    from core.app_manager import MainWindow

    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
"""

from core.app_manager.window import MainWindow

__all__ = ["MainWindow"]
