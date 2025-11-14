import contextlib
import os
import sys

from PyQt6 import QtWidgets

from config.theme import THEME, ColorTheme, validate_theme_system
from core.app_manager import MainWindow


# Cosmetic UI feature flags (only visible in debug mode)
if os.getenv("DEBUG_DTC", "0") == "1":
    print("ENABLE_GLOW:", THEME.get("ENABLE_GLOW", True))
    print("ENABLE_HOVER_ANIMATIONS:", THEME.get("ENABLE_HOVER_ANIMATIONS", True))
    print("TOOLTIP_AUTO_HIDE_MS:", THEME.get("TOOLTIP_AUTO_HIDE_MS", 3000))


def main():
    # Validate theme system on startup
    validate_theme_system()

    app = QtWidgets.QApplication(sys.argv)
    # Set application font globally from THEME
    with contextlib.suppress(Exception):
        app.setFont(
            ColorTheme.qfont(
                int(THEME.get("ui_font_weight", 500)),
                int(THEME.get("ui_font_size", 14)),
            )
        )
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
