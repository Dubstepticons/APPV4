"""
Theme Management Module

Handles theme switching, visual synchronization, and PnL-based color updates.
Extracted from core/app_manager.py for modularity.

Functions:
- set_theme_mode(): Switch theme mode (DEBUG/SIM/LIVE)
- on_theme_changed(): Refresh all panels with new theme
- optimize_archives_ui(): Database maintenance helper
- pnl_color_from_direction(): Get color based on PnL direction
- sync_pills_color_from_panel1(): Update pill colors from PnL state
"""

import os
from config.theme import THEME, switch_theme


def set_theme_mode(main_window, mode: str) -> None:
    """
    Switch theme mode (called by toolbar buttons or hotkey).
    Sets the theme, emits signal, and updates central widget background.

    Args:
        main_window: MainWindow instance
        mode: One of "DEBUG", "SIM", or "LIVE"
    """
    try:
        from utils.logger import get_logger
        log = get_logger(__name__)
        log.info(f"[set_theme_mode] START - mode={mode}")
    except:
        pass

    try:
        if mode not in ("DEBUG", "SIM", "LIVE"):
            try:
                from utils.logger import get_logger
                log = get_logger(__name__)
                log.warning(f"[set_theme_mode] Invalid mode: {mode}")
            except:
                pass
            return

        # Switch the THEME dictionary
        switch_theme(mode.lower())

        # Emit signal to trigger on_theme_changed
        try:
            from utils.logger import get_logger
            log = get_logger(__name__)
            log.info(f"[set_theme_mode] About to emit themeChanged signal with mode={mode}")
        except:
            pass

        main_window.themeChanged.emit(mode)

        try:
            from utils.logger import get_logger
            log = get_logger(__name__)
            log.info(f"[set_theme_mode] themeChanged signal emitted successfully")
        except:
            pass

        # Update central widget background
        central = main_window.centralWidget()
        if central:
            bg_color = THEME.get('bg_primary', '#000000')
            central.setStyleSheet(
                f"QWidget#CentralWidget {{ background: {bg_color}; }}"
            )
            try:
                from utils.logger import get_logger
                log = get_logger(__name__)
                log.info(f"[set_theme_mode] Central widget background updated to {bg_color}")
            except:
                pass

        try:
            from utils.logger import get_logger
            log = get_logger(__name__)
            log.info(f"[set_theme_mode] END - theme mode set to {mode}")
        except:
            pass
    except Exception as e:
        try:
            from utils.logger import get_logger
            log = get_logger(__name__)
            log.error(f"[set_theme_mode] Error: {e}", exc_info=True)
        except:
            print(f"[set_theme_mode] ERROR: {e}")


def on_theme_changed(main_window, mode: str) -> None:
    """
    Respond to theme mode changes ("DEBUG" / "SIM" / "LIVE").
    Refreshes all panels and UI elements to match new theme.

    Args:
        main_window: MainWindow instance
        mode: One of "DEBUG", "SIM", or "LIVE"
    """
    try:
        from utils.logger import get_logger
        log = get_logger(__name__)

        log.info(f"[ThemeManager.on_theme_changed] START - mode={mode}")

        if mode not in ("DEBUG", "SIM", "LIVE"):
            log.warning(f"[ThemeManager] Invalid mode: {mode}")
            return

        main_window.current_theme_mode = mode

        # DEBUG: Log theme state
        log.info(f"[ThemeManager] Switching to mode: {mode}")
        log.info(f"[ThemeManager] THEME.bg_panel = {THEME.get('bg_panel', 'KEY_NOT_FOUND')}")
        log.info(f"[ThemeManager] THEME.cell_border = {THEME.get('cell_border', 'KEY_NOT_FOUND')}")
        log.info(f"[ThemeManager] THEME.bg_primary = {THEME.get('bg_primary', 'KEY_NOT_FOUND')}")
        log.info(f"[ThemeManager] THEME.ink = {THEME.get('ink', 'KEY_NOT_FOUND')}")

        # Refresh connection icon
        log.debug(f"[ThemeManager] Refreshing connection icon...")
        icon = getattr(main_window.panel_balance, "conn_icon", None)
        if icon and hasattr(icon, "refresh_theme"):
            icon.refresh_theme()
            log.debug(f"[ThemeManager] Connection icon refreshed")
        else:
            log.debug(f"[ThemeManager] Connection icon not found or no refresh_theme method")

        # Refresh Panel 1 (balance/investing)
        log.debug(f"[ThemeManager] Refreshing Panel 1...")
        if hasattr(main_window.panel_balance, "_refresh_theme_colors"):
            main_window.panel_balance._refresh_theme_colors()
            log.debug(f"[ThemeManager] Panel 1 _refresh_theme_colors() called")
        else:
            log.debug(f"[ThemeManager] Panel 1 has no _refresh_theme_colors method")

        # Refresh Panel 2 (live)
        log.debug(f"[ThemeManager] Refreshing Panel 2...")
        if hasattr(main_window.panel_live, "refresh_theme"):
            log.info(f"[ThemeManager] Calling refresh_theme on Panel2")
            main_window.panel_live.refresh_theme()
            log.info(f"[ThemeManager] Panel 2 refresh_theme() completed")
        else:
            log.error(f"[ThemeManager] Panel 2 has no refresh_theme method!")

        # Refresh Panel 3 (stats)
        log.debug(f"[ThemeManager] Refreshing Panel 3...")
        if hasattr(main_window.panel_stats, "refresh_theme"):
            log.info(f"[ThemeManager] Calling refresh_theme on Panel3")
            main_window.panel_stats.refresh_theme()
            log.info(f"[ThemeManager] Panel 3 refresh_theme() completed")
        else:
            log.error(f"[ThemeManager] Panel 3 has no refresh_theme method!")

        # Update central widget background
        log.debug(f"[ThemeManager] Updating central widget background...")
        central = main_window.centralWidget()
        if central:
            bg_color = THEME.get('bg_primary', '#000000')
            central.setStyleSheet(
                f"QWidget#CentralWidget {{ background: {bg_color}; }}"
            )
            log.debug(f"[ThemeManager] Central widget background set to {bg_color}")
        else:
            log.warning(f"[ThemeManager] Central widget not found")

        log.info(f"[ThemeManager.on_theme_changed] END - mode={mode}")
    except Exception as e:
        from utils.logger import get_logger
        log = get_logger(__name__)
        log.error(f"[ThemeManager] Error in on_theme_changed: {e}", exc_info=True)


def optimize_archives_ui(main_window) -> None:
    """
    Manual trigger to VACUUM SQLite archive databases.
    Scans the working directory and 'data/' for *.db files.

    Args:
        main_window: MainWindow instance (used as parent for dialogs)
    """
    try:
        from utils.archive_maintenance import optimize_archives_with_prompt
    except Exception:
        return

    try:
        root = os.getcwd()
        # Prefer data/ if present, else cwd
        data_dir = os.path.join(root, "data")
        scan_root = data_dir if os.path.isdir(data_dir) else root
        optimize_archives_with_prompt(scan_root, threshold_mb=200.0, parent=main_window)
    except Exception:
        pass


def pnl_color_from_direction(up: object) -> str:
    """
    Derive a HEX color for PnL direction.

    Args:
        up: True (positive), False (negative), or None (neutral)

    Returns:
        HEX color string from THEME or safe default

    Examples:
        >>> pnl_color_from_direction(True)   # Green
        '#22C55E'
        >>> pnl_color_from_direction(False)  # Red
        '#EF4444'
        >>> pnl_color_from_direction(None)   # Gray
        '#9CA3AF'
    """
    try:
        pos = THEME.get("pnl_pos_color", "#22C55E")
        neg = THEME.get("pnl_neg_color", "#EF4444")
        neu = THEME.get("pnl_neu_color", "#9CA3AF")

        if up is True:
            return str(pos)
        if up is False:
            return str(neg)
        return str(neu)
    except Exception:
        return "#C8CDD3"  # Fallback gray


def sync_pills_color_from_panel1(main_window) -> None:
    """
    Read Panel1's current PnL direction and apply it to the active pill color.
    Safe if pills or _pnl_up aren't present.

    Args:
        main_window: MainWindow instance with panel references
    """
    try:
        # Derive pill color from Panel1 current PnL direction
        up = getattr(main_window.panel_balance, "_pnl_up", None)
        color = pnl_color_from_direction(up)

        # Update Panel2 pills color
        pills2 = getattr(main_window.panel_live, "pills", None)
        if pills2 and hasattr(pills2, "set_active_color"):
            pills2.set_active_color(color)

        # Leave Panel 3 (stats) to color its own pills based on its timeframe PnL
    except Exception:
        pass
