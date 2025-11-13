# -------------------- config/theme_v2.py (start)
# File: config/theme_v2.py
# APPSIERRA Theme Architecture v2.0
# Refactored with layered architecture, expanded roles, and theme compiler
# Supports: DEBUG | SIM | LIVE modes

from __future__ import annotations

import math
from typing import Optional, Union, Any
from PyQt6 import QtGui


# ========================================================================
# THEME METADATA
# ========================================================================
THEME_META = {
    "theme_id": "appsierra_v2.0",
    "version": "2.0.0",
    "created_by": "Claude AI",
    "generated_for": "APPSIERRA",
    "created_at": "2025-01-13T00:00:00Z",
    "color_space": "OKLCH",
    "description": "Refactored layered theme architecture with semantic roles and compiler",
    "framework": "PyQt6",
    "accessibility": "WCAG AAA compliant",
}


# ========================================================================
# COLOR TOKENS (OKLCH Primitives)
# ========================================================================
_COLOR_TOKENS = {
    # Neutrals
    "neutral.0": "oklch(98% 0.01 250)",  # Near-white surface
    "neutral.1": "oklch(93% 0.01 250)",  # Light surface
    "neutral.2": "oklch(25% 0.02 250)",  # Dark background
    "neutral.3": "oklch(15% 0.02 250)",  # Deepest dark
    "neutral.4": "oklch(40% 0.01 250)",  # Mid-gray
    "neutral.5": "oklch(60% 0.02 250)",  # Light gray
    # PnL Primaries
    "profit.vivid": "oklch(65% 0.17 140)",  # Vibrant green
    "profit.muted": "oklch(65% 0.09 140)",  # Desaturated green
    "loss.vivid": "oklch(58% 0.18 25)",  # Warm red
    "loss.muted": "oklch(58% 0.09 25)",  # Desaturated red
    "neutral.soft": "oklch(82% 0.03 260)",  # Neutral gray-blue
    # Accent Colors
    "accent.blue": "oklch(70% 0.13 250)",  # Informational
    "accent.orange": "oklch(75% 0.16 65)",  # Warning
    "accent.yellow": "oklch(85% 0.14 95)",  # Caution
    "accent.red": "oklch(60% 0.18 30)",  # Alert
    "accent.green": "oklch(65% 0.17 140)",  # Success
    "accent.cyan": "oklch(75% 0.11 200)",  # Chart VWAP
    "accent.amber": "oklch(72% 0.15 75)",  # Chart POC
    # Text Colors
    "text.high_contrast": "oklch(95% 0.01 250)",  # High contrast
    "text.medium_contrast": "oklch(80% 0.02 250)",  # Medium contrast
    "text.low_contrast": "oklch(60% 0.02 250)",  # Low priority
    "text.disabled": "oklch(45% 0.01 250)",  # Non-interactive
    "text.inverse": "oklch(15% 0.02 250)",  # On light backgrounds
    # Background Colors
    "bg.canvas": "oklch(12% 0.02 250)",  # Root dark
    "bg.panel": "oklch(15% 0.02 250)",  # Panel containers
    "bg.surface": "oklch(20% 0.02 250)",  # Elevated cards
    "bg.input": "oklch(18% 0.02 250)",  # Input fields
    "bg.hover": "oklch(22% 0.02 250)",  # Hover state
    "bg.selected": "oklch(25% 0.04 240)",  # Selected items
    # Border Colors
    "border.divider": "oklch(30% 0.02 250)",  # Subtle separators
    "border.focus": "oklch(70% 0.09 230)",  # Focus rings
    "border.input": "oklch(40% 0.02 250)",  # Input outlines
    "border.error": "oklch(60% 0.18 30)",  # Error borders
    # Chart Colors
    "chart.vwap": "oklch(70% 0.11 200)",  # Cyan VWAP line
    "chart.poc": "oklch(72% 0.15 75)",  # Orange POC
    "chart.delta.pos": "oklch(65% 0.15 140)",  # Green delta
    "chart.delta.neg": "oklch(58% 0.15 25)",  # Red delta
    "chart.grid": "oklch(25% 0.01 250)",  # Subtle grid
    "chart.axis": "oklch(60% 0.02 250)",  # Axis labels
    "chart.equity": "oklch(70% 0.12 250)",  # Equity line
    # Connection Status (stoplight)
    "status.connected": "oklch(74% 0.21 150)",  # Healthy green
    "status.warning": "oklch(82% 0.19 95)",  # Caution yellow
    "status.error": "oklch(62% 0.23 25)",  # Critical red
    # Mode Indicators
    "mode.live": "oklch(65% 0.20 140)",  # Vivid green
    "mode.sim": "oklch(70% 0.10 250)",  # Neutral blue
    "mode.debug": "oklch(60% 0.03 250)",  # Grayscale
}


# ========================================================================
# OKLCH → sRGB CONVERSION (For accurate luminance calculation)
# ========================================================================
def oklch_to_srgb(l: float, c: float, h: float) -> tuple[float, float, float]:
    """
    Convert OKLCH to sRGB color space.

    Args:
        l: Lightness (0-100)
        c: Chroma (0-0.5 typically)
        h: Hue (0-360 degrees)

    Returns:
        (r, g, b) tuple with values in 0-1 range
    """
    # Convert to OKLab (cylindrical to Cartesian)
    h_rad = math.radians(h)
    a = c * math.cos(h_rad)
    b = c * math.sin(h_rad)

    # OKLab to linear sRGB
    l_ = l / 100.0

    l_lms = l_ + 0.3963377774 * a + 0.2158037573 * b
    m_lms = l_ - 0.1055613458 * a - 0.0638541728 * b
    s_lms = l_ - 0.0894841775 * a - 1.2914855480 * b

    l_lms = l_lms ** 3
    m_lms = m_lms ** 3
    s_lms = s_lms ** 3

    r_linear = +4.0767416621 * l_lms - 3.3077115913 * m_lms + 0.2309699292 * s_lms
    g_linear = -1.2684380046 * l_lms + 2.6097574011 * m_lms - 0.3413193965 * s_lms
    b_linear = -0.0041960863 * l_lms - 0.7034186147 * m_lms + 1.7076147010 * s_lms

    # Clamp to valid range
    r_linear = max(0.0, min(1.0, r_linear))
    g_linear = max(0.0, min(1.0, g_linear))
    b_linear = max(0.0, min(1.0, b_linear))

    # Linear to sRGB gamma correction
    def gamma(c: float) -> float:
        if c <= 0.0031308:
            return 12.92 * c
        return 1.055 * (c ** (1.0 / 2.4)) - 0.055

    r = gamma(r_linear)
    g = gamma(g_linear)
    b = gamma(b_linear)

    return (r, g, b)


def get_luminance_from_color(color: str) -> float:
    """
    Calculate relative luminance of a color (0.0 = black, 1.0 = white).
    Handles both OKLCH and hex colors.

    Args:
        color: Color string (hex like "#FFFFFF" or oklch like "oklch(50% 0.1 180)")

    Returns:
        Luminance value 0.0-1.0
    """
    import re

    # Handle OKLCH colors
    if color.startswith("oklch"):
        oklch_pattern = re.compile(r"oklch\(\s*([\d.]+)%?\s+([\d.]+)\s+([\d.]+)\s*\)")
        match = oklch_pattern.match(color.strip())
        if match:
            l, c, h = float(match.group(1)), float(match.group(2)), float(match.group(3))
            r, g, b = oklch_to_srgb(l, c, h)
        else:
            return 0.5  # Fallback for malformed OKLCH
    else:
        # Parse hex color
        hex_color = color.lstrip("#")
        if len(hex_color) != 6:
            return 0.5  # Default mid-luminance for invalid colors

        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0

    # Apply gamma correction (sRGB to linear)
    def inv_gamma(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = inv_gamma(r)
    g_lin = inv_gamma(g)
    b_lin = inv_gamma(b)

    # Calculate relative luminance (ITU-R BT.709)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


# ========================================================================
# BASE THEME LAYERS (Decomposed for clarity)
# ========================================================================

# Typography Layer
_BASE_TYPOGRAPHY: dict[str, Union[int, str]] = {
    "font_family": "Inter, Segoe UI, Arial, Helvetica, sans-serif",
    "heading_font_family": "Inter, Segoe UI, Arial, Helvetica, sans-serif",
    "font_size": 16,
    "font_weight": 500,
    "title_font_weight": 500,
    "title_font_size": 16,
    "balance_font_weight": 500,
    "balance_font_size": 18,
    "pnl_font_weight": 500,
    "pnl_font_size": 12,
    "ui_font_weight": 500,
    "ui_font_size": 16,
    "pill_font_weight": 500,
    "pill_font_size": 16,
    "investing_font_size": 22,
    "investing_font_weight": 700,
    "badge_font_size": 8,
    "badge_font_weight": 700,
}

# Layout Layer
_BASE_LAYOUT: dict[str, int] = {
    # Metric cells
    "metric_cell_width": 140,
    "metric_cell_height": 52,
    # Chips / pills
    "chip_height": 28,
    "pill_radius": 14,
    # Badge
    "badge_height": 16,
    "badge_radius": 8,
    "badge_width": 50,
    "badge_gap": 4,
    # Glow effect
    "glow_blur_radius": 12,
    "glow_offset_x": 0,
    "glow_offset_y": 0,
    # Spacing
    "gap_sm": 6,
    "gap_md": 10,
    "gap_lg": 16,
    # Borders & radii
    "card_radius": 8,
    "graph_border_width": 0,
    "panel_radius": 10,
}

# Behavior Layer
_BASE_BEHAVIOR: dict[str, Union[bool, int]] = {
    "ENABLE_GLOW": True,
    "ENABLE_HOVER_ANIMATIONS": True,
    "ENABLE_TOOLTIP_FADE": True,
    "TOOLTIP_AUTO_HIDE_MS": 3000,
    "live_dot_pulse_ms": 600,
    "perf_safe": False,
}


# ========================================================================
# EXPANDED SEMANTIC ROLES (Maps semantic intent to tokens)
# ========================================================================
_SEMANTIC_ROLES = {
    # Text roles
    "role.text.primary": "text.high_contrast",
    "role.text.secondary": "text.medium_contrast",
    "role.text.muted": "text.low_contrast",
    "role.text.disabled": "text.disabled",
    "role.text.inverse": "text.inverse",

    # Background roles
    "role.bg.canvas": "bg.canvas",
    "role.bg.panel": "bg.panel",
    "role.bg.surface": "bg.surface",
    "role.bg.elevated": "bg.surface",
    "role.bg.input": "bg.input",

    # Border roles
    "role.border.default": "border.divider",
    "role.border.focus": "border.focus",
    "role.border.error": "border.error",

    # PnL roles
    "role.pnl.positive": "profit.vivid",
    "role.pnl.negative": "loss.vivid",
    "role.pnl.neutral": "neutral.soft",
    "role.pnl.positive_muted": "profit.muted",
    "role.pnl.negative_muted": "loss.muted",

    # Accent roles
    "role.accent.info": "accent.blue",
    "role.accent.warning": "accent.orange",
    "role.accent.error": "accent.red",
    "role.accent.success": "accent.green",

    # Status roles
    "role.status.connected": "status.connected",
    "role.status.warning": "status.warning",
    "role.status.error": "status.error",

    # Chart roles
    "role.chart.vwap": "chart.vwap",
    "role.chart.poc": "chart.poc",
    "role.chart.grid": "chart.grid",
    "role.chart.equity": "chart.equity",

    # Mode roles
    "role.mode.live": "mode.live",
    "role.mode.sim": "mode.sim",
    "role.mode.debug": "mode.debug",
}


# ========================================================================
# MODE-SPECIFIC OVERRIDES (Chroma/lightness adjustments)
# ========================================================================
_MODE_OVERRIDES = {
    "debug": {
        "accent_scale": 0.3,
        "chroma_boost": 0.30,
        "lightness_shift": -0.10,
        # Direct color overrides
        "pnl_pos_color": "oklch(65% 0.05 140)",  # Near-grayscale green
        "pnl_neg_color": "oklch(58% 0.05 25)",  # Near-grayscale red
        "flash_pos_color": "oklch(65% 0.05 140)",
        "flash_neg_color": "oklch(58% 0.05 25)",
    },
    "sim": {
        "accent_scale": 0.85,
        "chroma_boost": 0.70,
        "lightness_shift": 0.05,
        # Direct color overrides
        "pnl_pos_color": "oklch(65% 0.12 140)",  # Muted green
        "pnl_neg_color": "oklch(58% 0.12 25)",  # Muted red
        "flash_pos_color": "oklch(65% 0.12 140)",
        "flash_neg_color": "oklch(58% 0.12 25)",
    },
    "live": {
        "accent_scale": 1.0,
        "chroma_boost": 1.15,
        "lightness_shift": 0,
        # Direct color overrides
        "pnl_pos_color": "oklch(65% 0.20 140)",  # Intense green
        "pnl_neg_color": "oklch(58% 0.21 25)",  # Intense red
        "flash_pos_color": "oklch(65% 0.20 140)",
        "flash_neg_color": "oklch(58% 0.21 25)",
    },
}


# ========================================================================
# THEME COMPILER (Deep merge with mode-specific logic)
# ========================================================================
def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary
        override: Override dictionary

    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def compile_theme(mode: str) -> dict[str, Any]:
    """
    Compile a complete theme for the specified mode.
    Merges base layers + mode-specific colors + overrides.

    Args:
        mode: One of "debug", "sim", or "live"

    Returns:
        Compiled theme dictionary
    """
    mode = mode.lower()

    # Start with base layers
    theme = {}
    theme.update(_BASE_TYPOGRAPHY)
    theme.update(_BASE_LAYOUT)
    theme.update(_BASE_BEHAVIOR)

    # Add mode-specific adjustments
    if mode == "debug":
        theme.update({
            "heading_font_family": "Inter, Segoe UI, Arial, Helvetica, sans-serif",
            # Dark backgrounds
            "bg_primary": "#1E1E1E",
            "bg_secondary": "#000000",
            "bg_panel": "#000000",
            "bg_elevated": "#000000",
            "bg_tertiary": "#0F0F1A",
            "card_bg": "#1A1F2E",
            # Muted text (grayscale)
            "ink": "#C0C0C0",
            "subtle_ink": "#9CA3AF",
            "fg_primary": "#E5E7EB",
            "fg_muted": "#C8CDD3",
            "text_primary": "#E6F6FF",
            "text_dim": "#5B6C7A",
            # Borders
            "border": "#374151",
            "cell_border": "none",
            # Accents (muted)
            "accent": "#60A5FA",
            "accent_warning": "#F5B342",
            "accent_alert": "#C7463D",
            # Badge (amber)
            "investing_text_color": "#C0C0C0",
            "badge_bg_color": "#F5B342",
            "badge_border_color": "#F5B342",
            "badge_text_color": "#000000",
            "glow_color": "none",
            # Grid
            "grid_color": "#464646",
            # Mode badge
            "mode_badge_color": "#60A5FA",
            "mode_badge_radius": 12,
            "mode_badge_font_weight": 700,
            "mode_badge_font_size": 16,
        })
    elif mode == "sim":
        theme.update({
            "heading_font_family": "Lato, Inter, sans-serif",
            # Light backgrounds (white)
            "bg_primary": "#FFFFFF",
            "bg_panel": "#FFFFFF",
            "bg_secondary": "#F5F5F5",
            "bg_elevated": "#FFFFFF",
            "bg_tertiary": "#FAFAFA",
            "card_bg": "#FFFFFF",
            # Dark text (for light mode)
            "ink": "#000000",
            "subtle_ink": "#4B5563",
            "fg_primary": "#111827",
            "fg_muted": "#6B7280",
            "text_primary": "#1F2937",
            "text_dim": "#6B7280",
            # Borders (light gray)
            "border": "#E5E7EB",
            "cell_border": "2px solid #4DA7FF",  # Neon blue for SIM
            # Accents (balanced)
            "accent": "#60A5FA",
            "accent_warning": "#F5B342",
            "accent_alert": "#C7463D",
            # Badge (blue)
            "investing_text_color": "#000000",
            "badge_bg_color": "#4DA7FF",
            "badge_border_color": "#4DA7FF",
            "badge_text_color": "#000000",
            "glow_color": "#4DA7FF",
            # Grid (light)
            "grid_color": "#EAEAEA",
        })
    elif mode == "live":
        theme.update({
            "heading_font_family": "Lato, Inter, sans-serif",
            # Pure black backgrounds
            "bg_primary": "#000000",
            "bg_secondary": "#000000",
            "bg_panel": "#000000",
            "bg_elevated": "#000000",
            "bg_tertiary": "#0F0F1A",
            "card_bg": "#1A1F2E",
            # Gold text
            "ink": "#FFD700",
            "subtle_ink": "#9CA3AF",
            "fg_primary": "#E5E7EB",
            "fg_muted": "#C8CDD3",
            "text_primary": "#E6F6FF",
            "text_dim": "#5B6C7A",
            # Gold borders
            "border": "#FFD700",
            "cell_border": "2px solid #FFD700",  # Gold for LIVE
            # Accents (vivid)
            "accent": "#60A5FA",
            "accent_warning": "#F5B342",
            "accent_alert": "#C7463D",
            # Badge (green)
            "investing_text_color": "#FFD700",
            "badge_bg_color": "#00C97A",
            "badge_border_color": "#00C97A",
            "badge_text_color": "#FFFFFF",
            "glow_color": "#00C97A",
            # Grid
            "grid_color": "#464646",
        })

    # Add common colors (connection status, pills, etc.)
    theme.update({
        "conn_status_green": "oklch(74% 0.21 150)",
        "conn_status_yellow": "oklch(82% 0.19 95)",
        "conn_status_red": "oklch(62% 0.23 25)",
        "pill_text_active_color": "#000000" if mode == "sim" else "#000000",
        "live_dot_fill": "#20B36F",
        "live_dot_border": "#188E5B",
        "pnl_neu_color": "#C9CDD0",
        "pnl_pos_color_weak": f"rgba(32, 179, 111, {0.20 if mode == 'debug' else 0.30 if mode == 'sim' else 0.35})",
        "pnl_neg_color_weak": f"rgba(199, 70, 61, {0.20 if mode == 'debug' else 0.30 if mode == 'sim' else 0.35})",
        "pnl_neu_color_weak": "rgba(201, 205, 208, 0.35)",
        "flash_neu_color": "#C9CDD0",
        "sharpe_track_pen": "rgba(255,255,255,0.16)",
        "sharpe_track_bg": "rgba(255,255,255,0.10)",
        "mode_indicator_live": "#FF0000",
        "mode_indicator_sim": "#00FFFF",
    })

    # Apply mode-specific overrides
    if mode in _MODE_OVERRIDES:
        theme.update(_MODE_OVERRIDES[mode])

    return theme


# ========================================================================
# THEME REGISTRY (Centralized theme management)
# ========================================================================
class ThemeRegistry:
    """
    Centralized theme registry for managing and accessing themes.
    Provides theme compilation, caching, and retrieval.
    """

    _themes: dict[str, dict] = {}
    _active_mode: str = "sim"

    @classmethod
    def compile_all(cls) -> None:
        """Pre-compile all theme modes for fast switching."""
        for mode in ["debug", "sim", "live"]:
            cls._themes[mode] = compile_theme(mode)

    @classmethod
    def get(cls, mode: str) -> dict:
        """
        Get compiled theme for specified mode.

        Args:
            mode: One of "debug", "sim", or "live"

        Returns:
            Compiled theme dictionary
        """
        mode = mode.lower()
        if mode not in cls._themes:
            cls._themes[mode] = compile_theme(mode)
        return cls._themes[mode].copy()

    @classmethod
    def get_active(cls) -> dict:
        """Get the currently active theme."""
        return cls.get(cls._active_mode)

    @classmethod
    def set_active(cls, mode: str) -> None:
        """Set the active theme mode."""
        cls._active_mode = mode.lower()

    @classmethod
    def list_available(cls) -> list[str]:
        """List all available theme modes."""
        return ["debug", "sim", "live"]

    @classmethod
    def get_default(cls) -> dict:
        """Get the default theme (SIM)."""
        return cls.get("sim")


# Pre-compile all themes at module load
ThemeRegistry.compile_all()


# ========================================================================
# LEGACY THEME DICTIONARIES (For backward compatibility)
# ========================================================================
DEBUG_THEME = ThemeRegistry.get("debug")
SIM_THEME = ThemeRegistry.get("sim")
LIVE_THEME = ThemeRegistry.get("live")
THEME = SIM_THEME.copy()


# ========================================================================
# THEME SWITCHING (Updated to use registry)
# ========================================================================
_THEME_MAP = {
    "debug": DEBUG_THEME,
    "live": LIVE_THEME,
    "sim": SIM_THEME,
}


def switch_theme(theme_name: str) -> None:
    """
    Switch active theme using the registry system.

    Args:
        theme_name: One of "debug", "live", or "sim"
    """
    global THEME

    try:
        from utils.logger import get_logger
        log = get_logger(__name__)
        log.info(f"[switch_theme] Switching to {theme_name}")
    except:
        pass

    theme_name = theme_name.lower().strip()

    # Get theme from registry
    new_theme = ThemeRegistry.get(theme_name)
    ThemeRegistry.set_active(theme_name)

    # Update global THEME
    THEME.clear()
    THEME.update(new_theme)

    try:
        from utils.logger import get_logger
        log = get_logger(__name__)
        log.info(f"[switch_theme] Theme switched to {theme_name}")
    except:
        pass


# ========================================================================
# Theme Utility Class (Unchanged, uses THEME global)
# ========================================================================
FONT: str = THEME.get("font_family")


class ColorTheme:
    """Helper functions for color and font retrieval."""

    @staticmethod
    def font_css(weight: int, size: int, family: str | None = None) -> str:
        """Get font CSS for body/UI text (Inter)."""
        fam = family or THEME.get("font_family")
        return f"font:{int(weight)} {int(size)}px {fam}"

    @staticmethod
    def heading_font_css(weight: int, size: int, family: str | None = None) -> str:
        """Get font CSS for headings/emphasis (Lato in LIVE/SIM, Inter in DEBUG)."""
        fam = family or THEME.get("heading_font_family")
        return f"font:{int(weight)} {int(size)}px {fam}"

    @staticmethod
    def qfont(weight: int, size_px: int) -> QtGui.QFont:
        """Get QFont for body/UI text (Inter)."""
        f = QtGui.QFont()
        font_families = [fam.strip() for fam in str(THEME.get("font_family")).split(",")]
        f.setFamilies(font_families)
        f.setPixelSize(int(size_px))
        f.setWeight(int(weight))
        return f

    @staticmethod
    def heading_qfont(weight: int, size_px: int) -> QtGui.QFont:
        """Get QFont for headings/emphasis (Lato in LIVE/SIM, Inter in DEBUG)."""
        f = QtGui.QFont()
        font_families = [fam.strip() for fam in str(THEME.get("heading_font_family")).split(",")]
        f.setFamilies(font_families)
        f.setPixelSize(int(size_px))
        f.setWeight(int(weight))
        return f

    @staticmethod
    def pnl_color_from_value(value: Optional[float]) -> str:
        from utils.theme_helpers import normalize_color

        if value is None:
            return normalize_color(str(THEME.get("pnl_neu_color", "#C9CDD0")))
        try:
            v = float(value)
        except Exception:
            return normalize_color(str(THEME.get("pnl_neu_color", "#C9CDD0")))
        if v > 0:
            return normalize_color(str(THEME.get("pnl_pos_color", "#20B36F")))
        if v < 0:
            return normalize_color(str(THEME.get("pnl_neg_color", "#C7463D")))
        return normalize_color(str(THEME.get("pnl_neu_color", "#C9CDD0")))

    @staticmethod
    def pnl_color_from_direction(up: Optional[bool]) -> str:
        from utils.theme_helpers import normalize_color

        if up is True:
            return normalize_color(str(THEME.get("pnl_pos_color", "#20B36F")))
        if up is False:
            return normalize_color(str(THEME.get("pnl_neg_color", "#C7463D")))
        return normalize_color(str(THEME.get("pnl_neu_color", "#C9CDD0")))

    @staticmethod
    def pill_color(selected_up: Optional[bool]) -> str:
        return ColorTheme.pnl_color_from_direction(selected_up)

    @staticmethod
    def make_weak_color(color: str, alpha: float = 0.35) -> str:
        """Convert any color to rgba with specified alpha."""
        try:
            from utils.theme_helpers import normalize_color

            hex_color = normalize_color(color).lstrip("#")
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha})"
        except Exception:
            from utils.theme_helpers import normalize_color

            fallback = normalize_color(str(THEME.get("pnl_neu_color", "#C9CDD0")))
            return ColorTheme.make_weak_color(fallback, alpha)


# ========================================================================
# Legacy Functions (Backward compatibility)
# ========================================================================
def apply_trading_mode_theme(mode: str) -> None:
    """Apply theme based on trading mode."""
    switch_theme(mode.lower())


def set_theme(mode: str = "dark") -> None:
    """Legacy function for backward compatibility."""
    if mode == "light":
        switch_theme("sim")
    else:
        switch_theme("live")


def set_theme_for_account(account_id: str) -> None:
    """Switch between LIVE and SIM themes based on account ID."""
    if not account_id:
        switch_theme("live")
        return

    acct = account_id.strip().lower()
    if acct == "120005":
        switch_theme("live")
    elif acct == "sim1":
        switch_theme("sim")
    else:
        switch_theme("debug")


def get_theme() -> dict:
    """Get current active theme dictionary."""
    return THEME.copy()


def get_theme_meta() -> dict:
    """Get theme metadata."""
    return THEME_META.copy()


def get_color_token(token_name: str) -> str:
    """Get raw OKLCH color token by name."""
    return _COLOR_TOKENS.get(token_name, "oklch(50% 0 0)")


# ========================================================================
# Validation (Using improved luminance calculation)
# ========================================================================
def validate_theme_colors(theme_dict: dict, theme_name: str) -> list[str]:
    """
    Validate that theme colors are semantically correct for the mode.
    Uses proper OKLCH → sRGB conversion for accurate luminance.
    """
    problems = []

    # Get background color
    bg_primary = theme_dict.get("bg_primary", "#000000")
    bg_lum = get_luminance_from_color(str(bg_primary))

    # Determine if this is a light or dark mode
    is_light_mode = bg_lum > 0.5
    mode_type = "LIGHT" if is_light_mode else "DARK"

    # Check text colors have proper contrast
    text_colors = {
        "ink": theme_dict.get("ink"),
        "text_primary": theme_dict.get("text_primary"),
        "fg_primary": theme_dict.get("fg_primary"),
    }

    for key, color in text_colors.items():
        if color and isinstance(color, str):
            text_lum = get_luminance_from_color(color)

            # Light mode should have dark text (low luminance)
            # Dark mode should have light text (high luminance)
            if is_light_mode and text_lum > 0.7:
                problems.append(f"{key}={color} (light text on light bg - low contrast!)")
            elif not is_light_mode and text_lum < 0.3:
                problems.append(f"{key}={color} (dark text on dark bg - low contrast!)")

    if problems:
        problems.insert(0, f"Mode type: {mode_type} (bg_primary={bg_primary}, luminance={bg_lum:.2f})")

    return problems


def validate_all_themes() -> None:
    """Validate all theme modes."""
    themes_to_check = [
        (DEBUG_THEME, "DEBUG_THEME"),
        (SIM_THEME, "SIM_THEME"),
        (LIVE_THEME, "LIVE_THEME"),
    ]

    all_errors = []

    for theme_dict, theme_name in themes_to_check:
        color_problems = validate_theme_colors(theme_dict, theme_name)
        if color_problems:
            all_errors.append(f"{theme_name} color problems:\n    " + "\n    ".join(color_problems))

    if all_errors:
        error_msg = "Theme validation warnings:\n  " + "\n  ".join(all_errors)
        print(f"[THEME WARNING] {error_msg}")


# ========================================================================
# Backward Compatibility Functions (For tests and legacy code)
# ========================================================================
def validate_oklch_tokens() -> list[str]:
    """
    Validate all OKLCH color tokens for correct format and ranges.

    Returns:
        List of error messages (empty if all valid)
    """
    import re

    errors = []

    # OKLCH format: oklch(L% C H) where L=0-100%, C=0-0.5, H=0-360
    oklch_pattern = re.compile(r"oklch\(\s*([\d.]+)%?\s+([\d.]+)\s+([\d.]+)\s*\)")

    for token_name, color in _COLOR_TOKENS.items():
        if not color.startswith("oklch("):
            continue

        match = oklch_pattern.match(color.strip())
        if not match:
            errors.append(f"Token '{token_name}': Malformed OKLCH format '{color}'")
            continue

        # Extract values
        l_str, c_str, h_str = match.groups()
        l_val = float(l_str)
        c_val = float(c_str)
        h_val = float(h_str)

        # Check for percentage sign
        if "%" not in color:
            errors.append(f"Token '{token_name}': Missing % in lightness value '{color}'")

        # Validate ranges
        if not (0 <= l_val <= 100):
            errors.append(f"Token '{token_name}': Lightness {l_val} out of range [0, 100]")
        if not (0 <= c_val <= 0.5):
            errors.append(f"Token '{token_name}': Chroma {c_val} out of typical range [0, 0.5]")
        if not (0 <= h_val <= 360):
            errors.append(f"Token '{token_name}': Hue {h_val} out of range [0, 360]")

    return errors


def validate_theme_keys_consistency() -> list[str]:
    """
    Validate that all three theme modes (DEBUG, SIM, LIVE) have consistent keys.

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []

    # Get keys from all themes
    debug_keys = set(DEBUG_THEME.keys())
    sim_keys = set(SIM_THEME.keys())
    live_keys = set(LIVE_THEME.keys())

    # Check for missing keys in each theme
    all_keys = debug_keys | sim_keys | live_keys

    for theme_name, theme_keys in [("DEBUG", debug_keys), ("SIM", sim_keys), ("LIVE", live_keys)]:
        missing = all_keys - theme_keys
        if missing:
            errors.append(f"Theme '{theme_name}': Missing keys: {missing}")

    return errors


def validate_theme_system() -> None:
    """
    Run all theme validations and log errors.
    Should be called on app startup to catch theme issues early.

    Legacy function for backward compatibility.
    In v2.0, validation runs automatically at module load.
    """
    try:
        from utils.logger import get_logger
        log = get_logger(__name__)

        # Validate OKLCH tokens
        oklch_errors = validate_oklch_tokens()
        if oklch_errors:
            log.error(f"OKLCH validation failed with {len(oklch_errors)} errors:")
            for error in oklch_errors:
                log.error(f"  - {error}")

        # Validate theme key consistency
        consistency_errors = validate_theme_keys_consistency()
        if consistency_errors:
            log.error(f"Theme consistency validation failed with {len(consistency_errors)} errors:")
            for error in consistency_errors:
                log.error(f"  - {error}")

        # Summary
        total_errors = len(oklch_errors) + len(consistency_errors)
        if total_errors > 0:
            log.warning(f"Theme system has {total_errors} validation errors - review config/theme.py")
        else:
            log.info("Theme system validation passed - all OKLCH tokens and keys are valid")
    except:
        pass


# Run validation at module load
try:
    validate_all_themes()
except Exception as e:
    print(f"[THEME WARNING] Validation failed: {e}")


# -------------------- config/theme.py (end)
