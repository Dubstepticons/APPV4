"""
panels/panel1/helpers.py

Utility functions for Panel1 - formatting and color helpers.

This module provides simple helper functions for:
- PnL color selection based on direction
- Currency formatting
- Percentage formatting

Architecture:
- Pure functions (no state)
- Null-safe operations
- Theme-aware

Usage:
    from panels.panel1.helpers import pnl_color, fmt_money, fmt_pct

    color = pnl_color(up=True)  # Returns green
    amount = fmt_money(1234.56)  # Returns "$1,234.56"
    pct = fmt_pct(5.25)  # Returns "+5.25%"
"""

from __future__ import annotations

from typing import Optional

from config.theme import THEME, ColorTheme


def pnl_color(up: Optional[bool]) -> str:
    """
    Return color hex string based on PnL direction.

    Args:
        up: True for positive PnL (green), False for negative (red), None for neutral (gray)

    Returns:
        Color hex string from theme
    """
    if up is None:
        return str(THEME.get("pnl_neu_color", "#C9CDD0"))
    return ColorTheme.pnl_color_from_direction(bool(up))


def fmt_money(v: Optional[float]) -> str:
    """
    Format float as currency string.

    Args:
        v: Dollar amount to format

    Returns:
        Formatted string like "$1,234.56" or "--" if None/invalid

    Examples:
        >>> fmt_money(1234.56)
        '$1,234.56'
        >>> fmt_money(None)
        '--'
        >>> fmt_money(-500.25)
        '$-500.25'
    """
    if v is None:
        return "--"
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "--"


def fmt_pct(p: Optional[float]) -> str:
    """
    Format float as percentage string with sign.

    Args:
        p: Percentage value to format

    Returns:
        Formatted string like "+5.25%" or "--" if None/invalid

    Examples:
        >>> fmt_pct(5.25)
        '+5.25%'
        >>> fmt_pct(-2.50)
        '-2.50%'
        >>> fmt_pct(None)
        '--'
    """
    if p is None:
        return "--"
    try:
        return f"{float(p):+.2f}%"
    except Exception:
        return "--"
