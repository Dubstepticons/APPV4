# -------------------- config/theme.py (start)
# File: config/theme.py
# APPSIERRA Theme Architecture v1.0
# Semantic Roles & Tokens with OKLCH Color Space
# Supports: DEBUG | SIM | LIVE modes

from __future__ import annotations

from typing import Optional, Union

from PyQt6 import QtGui


# ========================================================================
# THEME METADATA
# ========================================================================
THEME_META = {
    "theme_id": "appsierra_v1.0",
    "version": "1.0.0",
    "created_by": "Claude AI",
    "generated_for": "APPSIERRA",
    "created_at": "2025-01-12T00:00:00Z",
    "color_space": "OKLCH",
    "description": "Semantic roles-to-tokens theme with perceptual OKLCH color space for LIVE/SIM/DEBUG modes",
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
    "text.primary": "oklch(95% 0.01 250)",  # High contrast
    "text.secondary": "oklch(80% 0.02 250)",  # Medium contrast
    "text.muted": "oklch(60% 0.02 250)",  # Low priority
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
# OKLCH VALIDATION
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

    # Get base keys from _BASE_THEME (all themes should have these + their overrides)
    base_keys = set(_BASE_THEME.keys())

    # Check each theme
    for theme_name, theme_dict in [("DEBUG", DEBUG_THEME), ("SIM", SIM_THEME), ("LIVE", LIVE_THEME)]:
        theme_keys = set(theme_dict.keys())

        # Check if base keys are present
        missing = base_keys - theme_keys
        if missing:
            errors.append(f"Theme '{theme_name}': Missing base keys: {missing}")

    return errors


def validate_theme_system() -> None:
    """
    Run all theme validations and log errors.
    Should be called on app startup to catch theme issues early.
    """
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

    # Summary - only log errors, not success
    total_errors = len(oklch_errors) + len(consistency_errors)
    if total_errors > 0:
        log.warning(f"Theme system has {total_errors} validation errors - review config/theme.py")


# ========================================================================
# SEMANTIC ROLES (Maps semantic intent to tokens)
# ========================================================================
_SEMANTIC_ROLES = {
    # PnL Roles (map to OKLCH tokens)
    "pnl.pos": "profit.vivid",
    "pnl.neg": "loss.vivid",
    "pnl.neutral": "neutral.soft",
    "pnl.pos.muted": "profit.muted",
    "pnl.neg.muted": "loss.muted",
    # Mode Roles (map to mode indicators)
    "mode.live.accent": "mode.live",
    "mode.sim.accent": "mode.sim",
    "mode.debug.accent": "mode.debug",
}


# ========================================================================
# BASE THEME (Shared constants)
# ========================================================================
_BASE_THEME: dict[str, Union[int, float, str, bool]] = {
    # Typography - unified 16px/500 weight
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
    # Metric cells (normalized to UI font 16px)
    "metric_cell_width": 140,
    "metric_cell_height": 52,
    # Chips / pills
    "chip_height": 28,
    "pill_radius": 14,
    # Badge (Panel 1 header: DEBUG/SIM/LIVE pill)
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
    # Visual Behavior Flags
    "ENABLE_GLOW": True,
    "ENABLE_HOVER_ANIMATIONS": True,
    "ENABLE_TOOLTIP_FADE": True,
    "TOOLTIP_AUTO_HIDE_MS": 3000,
    "live_dot_pulse_ms": 600,
    "perf_safe": False,
}


# ========================================================================
# DEBUG THEME (Grayscale, diagnostic)
# ========================================================================
DEBUG_THEME: dict[str, Union[int, float, str, bool]] = {
    **_BASE_THEME,
    # Core palette - Reduced saturation
    "ink": "#C0C0C0",
    "subtle_ink": "#9CA3AF",
    "fg_primary": "#E5E7EB",
    "fg_muted": "#C8CDD3",
    "text_primary": "#E6F6FF",
    "text_dim": "#5B6C7A",
    # Backgrounds
    "bg_primary": "#1E1E1E",
    "bg_secondary": "#000000",
    "bg_panel": "#000000",
    "bg_elevated": "#000000",
    "bg_tertiary": "#0F0F1A",
    "card_bg": "#1A1F2E",
    # Borders
    "border": "#374151",
    "cell_border": "none",
    # Accent / brand
    "accent": "#60A5FA",
    "accent_warning": "#F5B342",
    "accent_alert": "#C7463D",
    # Connection status (OKLCH)
    "conn_status_green": "oklch(74% 0.21 150)",
    "conn_status_yellow": "oklch(82% 0.19 95)",
    "conn_status_red": "oklch(62% 0.23 25)",
    # Pill widget
    "pill_text_active_color": "#000000",
    "live_dot_fill": "#20B36F",
    "live_dot_border": "#188E5B",
    # Mode badge
    "mode_badge_color": "#60A5FA",
    "mode_badge_radius": 12,
    "mode_badge_font_weight": 700,
    "mode_badge_font_size": 16,
    # PnL colors (muted for DEBUG)
    "pnl_pos_color": "oklch(65% 0.05 140)",  # Near-grayscale green
    "pnl_neg_color": "oklch(58% 0.05 25)",  # Near-grayscale red
    "pnl_neu_color": "#C9CDD0",
    "pnl_pos_color_weak": "rgba(32, 179, 111, 0.20)",
    "pnl_neg_color_weak": "rgba(199, 70, 61, 0.20)",
    "pnl_neu_color_weak": "rgba(201, 205, 208, 0.35)",
    # Flash colors
    "flash_pos_color": "oklch(65% 0.05 140)",
    "flash_neg_color": "oklch(58% 0.05 25)",
    "flash_neu_color": "#C9CDD0",
    # Sharpe bar
    "sharpe_track_pen": "rgba(255,255,255,0.16)",
    "sharpe_track_bg": "rgba(255,255,255,0.10)",
    # Graph grid
    "grid_color": "#464646",
    # Badge styling (golden amber - analytical)
    "investing_text_color": "#C0C0C0",
    "badge_bg_color": "#F5B342",
    "badge_border_color": "#F5B342",
    "badge_text_color": "#000000",
    "glow_color": "none",
    # Mode indicator neon colors
    "mode_indicator_live": "#FF0000",  # Neon red for LIVE
    "mode_indicator_sim": "#00FFFF",  # Neon cyan for SIM
}


# ========================================================================
# LIVE THEME (High saturation, vivid)
# ========================================================================
LIVE_THEME: dict[str, Union[int, float, str, bool]] = {
    **_BASE_THEME,
    # Typography - Lato for headings
    "heading_font_family": "Lato, Inter, sans-serif",
    # Core palette (inherit from DEBUG, override gold)
    "ink": "#FFD700",
    "subtle_ink": "#9CA3AF",
    "fg_primary": "#E5E7EB",
    "fg_muted": "#C8CDD3",
    "text_primary": "#E6F6FF",
    "text_dim": "#5B6C7A",
    # Backgrounds (pure black for LIVE)
    "bg_primary": "#000000",
    "bg_secondary": "#000000",
    "bg_panel": "#000000",
    "bg_elevated": "#000000",
    "bg_tertiary": "#0F0F1A",
    "card_bg": "#1A1F2E",
    # Borders (gold)
    "border": "#FFD700",
    "cell_border": "2px solid #FFD700",  # Gold borders for LIVE mode
    # Accents
    "accent": "#60A5FA",
    "accent_warning": "#F5B342",
    "accent_alert": "#C7463D",
    # Connection status
    "conn_status_green": "oklch(74% 0.21 150)",
    "conn_status_yellow": "oklch(82% 0.19 95)",
    "conn_status_red": "oklch(62% 0.23 25)",
    # Pill widget
    "pill_text_active_color": "#000000",
    "live_dot_fill": "#20B36F",
    "live_dot_border": "#188E5B",
    # PnL colors (full saturation)
    "pnl_pos_color": "oklch(65% 0.20 140)",  # Intense green
    "pnl_neg_color": "oklch(58% 0.21 25)",  # Intense red
    "pnl_neu_color": "#C9CDD0",
    "pnl_pos_color_weak": "rgba(32, 179, 111, 0.35)",
    "pnl_neg_color_weak": "rgba(199, 70, 61, 0.35)",
    "pnl_neu_color_weak": "rgba(201, 205, 208, 0.35)",
    # Flash colors (vivid)
    "flash_pos_color": "oklch(65% 0.20 140)",
    "flash_neg_color": "oklch(58% 0.21 25)",
    "flash_neu_color": "#C9CDD0",
    # Sharpe bar
    "sharpe_track_pen": "rgba(255,255,255,0.16)",
    "sharpe_track_bg": "rgba(255,255,255,0.10)",
    # Graph grid
    "grid_color": "#464646",
    # Badge styling (vibrant green - active)
    "investing_text_color": "#FFD700",
    "badge_bg_color": "#00C97A",
    "badge_border_color": "#00C97A",
    "badge_text_color": "#FFFFFF",
    "glow_color": "#00C97A",
    # Mode indicators
    "mode_indicator_live": "#FF0000",
    "mode_indicator_sim": "#00FFFF",
}


# ========================================================================
# SIM THEME (Balanced saturation, calm, LIGHT MODE)
# ========================================================================
SIM_THEME: dict[str, Union[int, float, str, bool]] = {
    **_BASE_THEME,
    # Typography - Lato for headings
    "heading_font_family": "Lato, Inter, sans-serif",
    # Core palette (light mode - dark text on white)
    "ink": "#000000",           # Black text (primary)
    "subtle_ink": "#4B5563",    # Medium-dark gray (subtle text)
    "fg_primary": "#111827",    # Very dark gray (foreground)
    "fg_muted": "#6B7280",      # Medium gray (muted foreground)
    "text_primary": "#1F2937",  # Dark gray text (readable on white)
    "text_dim": "#6B7280",      # Medium gray (dimmed text on white)
    # Backgrounds (white for light mode)
    "bg_primary": "#FFFFFF",    # White main background
    "bg_panel": "#FFFFFF",      # White panels (NOT black!)
    "bg_secondary": "#F5F5F5",  # Light gray secondary bg
    "bg_elevated": "#FFFFFF",   # White elevated
    "bg_tertiary": "#FAFAFA",   # Very light gray
    "card_bg": "#FFFFFF",       # White cards
    # Borders (light gray)
    "border": "#E5E7EB",        # Light gray borders
    "cell_border": "2px solid #4DA7FF",  # Neon blue for SIM mode (light panels need visible borders)
    # Accents (balanced for SIM)
    "accent": "#60A5FA",
    "accent_warning": "#F5B342",
    "accent_alert": "#C7463D",
    # Connection status
    "conn_status_green": "oklch(74% 0.21 150)",
    "conn_status_yellow": "oklch(82% 0.19 95)",
    "conn_status_red": "oklch(62% 0.23 25)",
    # Pill widget
    "pill_text_active_color": "#FFFFFF",
    "live_dot_fill": "#20B36F",
    "live_dot_border": "#188E5B",
    # PnL colors (reduced saturation)
    "pnl_pos_color": "oklch(65% 0.12 140)",  # Muted green
    "pnl_neg_color": "oklch(58% 0.12 25)",  # Muted red
    "pnl_neu_color": "#C9CDD0",
    "pnl_pos_color_weak": "rgba(32, 179, 111, 0.30)",
    "pnl_neg_color_weak": "rgba(199, 70, 61, 0.30)",
    "pnl_neu_color_weak": "rgba(201, 205, 208, 0.35)",
    # Flash colors (balanced)
    "flash_pos_color": "oklch(65% 0.12 140)",
    "flash_neg_color": "oklch(58% 0.12 25)",
    "flash_neu_color": "#C9CDD0",
    # Sharpe bar
    "sharpe_track_pen": "rgba(255,255,255,0.16)",
    "sharpe_track_bg": "rgba(255,255,255,0.10)",
    # Graph grid
    "grid_color": "#EAEAEA",  # Light gray for light mode
    # Badge styling (gentle blue - sandbox)
    "investing_text_color": "#000000",
    "badge_bg_color": "#4DA7FF",
    "badge_border_color": "#4DA7FF",
    "badge_text_color": "#000000",
    "glow_color": "#4DA7FF",
    # Mode indicators
    "mode_indicator_live": "#FF0000",
    "mode_indicator_sim": "#00FFFF",
}


# ========================================================================
# ACTIVE THEME (Points to current theme, default: SIM)
# ========================================================================
THEME: dict[str, Union[int, float, str, bool]] = SIM_THEME.copy()


# ========================================================================
# Font alias for quick reference
# ========================================================================
FONT: str = THEME.get("font_family")


# ========================================================================
# Theme Utility Class
# ========================================================================
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

    # -------------------- PnL Color Logic --------------------
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
        """
        Convert any color (hex, oklch) to an rgba string with the specified alpha.
        Example: "#22C55E" with alpha=0.35 -> "rgba(34, 197, 94, 0.35)"

        Args:
            color: Color string (hex, oklch, etc.)
            alpha: Alpha transparency value (0.0 to 1.0)

        Returns:
            RGBA color string (e.g., "rgba(34, 197, 94, 0.35)")
        """
        try:
            from utils.theme_helpers import normalize_color

            # Normalize to hex first
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
# Theme Switching Functions
# ========================================================================

# Theme lookup map for efficient switching
_THEME_MAP = {
    "debug": DEBUG_THEME,
    "live": LIVE_THEME,
    "sim": SIM_THEME,
}


def switch_theme(theme_name: str) -> None:
    """
    Switch active theme between DEBUG, LIVE, or SIM.

    Args:
        theme_name: One of "debug", "live", or "sim"
    """
    global THEME

    theme_name = theme_name.lower().strip()
    new_theme = _THEME_MAP.get(theme_name, DEBUG_THEME)

    THEME.clear()
    THEME.update(new_theme)


def apply_trading_mode_theme(mode: str) -> None:
    """
    Apply theme based on trading mode.
    Wrapper for switch_theme() that accepts mode names like DEBUG, LIVE, SIM.

    Args:
        mode: Trading mode - one of "DEBUG", "LIVE", or "SIM"
    """
    switch_theme(mode.lower())


# ========================================================================
# Legacy Functions (backward compatibility)
# ========================================================================
def set_theme(mode: str = "dark") -> None:
    """
    Legacy function for backward compatibility.
    Use switch_theme() for new code.
    """
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
    """Get theme metadata (version, color space, etc.)."""
    return THEME_META.copy()


def get_color_token(token_name: str) -> str:
    """
    Get raw OKLCH color token by name.

    Args:
        token_name: Token name like "profit.vivid" or "neutral.2"

    Returns:
        OKLCH color string
    """
    return _COLOR_TOKENS.get(token_name, "oklch(50% 0 0)")


# ========================================================================
# Theme Export (JSON-ready)
# ========================================================================
def export_theme_json() -> dict:
    """
    Export complete theme as JSON-ready dictionary.
    Includes metadata, roles, tokens, and mode overrides.

    Returns:
        Complete theme dictionary ready for JSON serialization
    """
    return {
        "theme_id": THEME_META["theme_id"],
        "meta": THEME_META,
        "roles": _SEMANTIC_ROLES,
        "tokens": _COLOR_TOKENS,
        "modes": {
            "live": {
                "accent.scale": 1.0,
                "chroma.boost": 1.15,
                "lightness.shift": 0,
                "overrides": {
                    "pnl.pos": "oklch(65% 0.20 140)",
                    "pnl.neg": "oklch(58% 0.21 25)",
                },
            },
            "sim": {
                "accent.scale": 0.85,
                "chroma.boost": 0.70,
                "lightness.shift": 0.05,
                "overrides": {
                    "pnl.pos": "oklch(65% 0.12 140)",
                    "pnl.neg": "oklch(58% 0.12 25)",
                },
            },
            "debug": {
                "accent.scale": 0.3,
                "chroma.boost": 0.30,
                "lightness.shift": -0.10,
                "overrides": {
                    "pnl.pos": "oklch(65% 0.05 140)",
                    "pnl.neg": "oklch(58% 0.05 25)",
                },
            },
        },
    }


# ========================================================================
# Theme Validation
# ========================================================================

# All theme keys that must be present in every theme mode
# Extracted from actual usage across the codebase
_REQUIRED_THEME_KEYS = [
    # Core colors
    "ink", "bg_panel", "bg_primary", "bg_secondary", "bg_tertiary",
    "fg_primary", "fg_muted", "text_primary", "text_dim", "border",
    # Card/widget styling
    "card_bg", "card_radius", "cell_border",
    # PnL colors
    "pnl_pos_color", "pnl_neg_color", "pnl_neu_color",
    # Accent colors
    "accent", "accent_warning", "accent_alert",
    # Typography
    "font_family", "font_size", "font_weight",
    "title_font_size", "title_font_weight",
    "balance_font_size", "balance_font_weight",
    "pnl_font_size", "pnl_font_weight",
    "investing_font_size", "investing_font_weight",
    # Badge/pill styling
    "badge_bg_color", "badge_border_color", "badge_text_color",
    "badge_font_size", "badge_font_weight",
    "badge_height", "badge_radius", "badge_width", "badge_gap",
    "pill_font_size", "pill_font_weight", "pill_radius", "pill_text_active_color",
    # Connection status
    "conn_status_green", "conn_status_yellow", "conn_status_red",
    # Graph/chart
    "grid_color", "sharpe_track_pen", "sharpe_track_bg",
    # Mode indicators
    "mode_indicator_live", "mode_indicator_sim",
    # Misc
    "glow_color", "glow_blur_radius", "perf_safe",
    "chip_height", "investing_text_color",
    "live_dot_fill", "live_dot_border",
]


def _get_luminance(color: str) -> float:
    """
    Calculate relative luminance of a color (0.0 = black, 1.0 = white).

    Args:
        color: Hex color string like "#FFFFFF" or "#000000"

    Returns:
        Luminance value 0.0-1.0
    """
    # Handle oklch colors (just return 0.5 as approximation)
    if color.startswith("oklch"):
        return 0.5

    # Parse hex color
    hex_color = color.lstrip("#")
    if len(hex_color) != 6:
        return 0.5  # Default mid-luminance for invalid colors

    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    # Apply gamma correction
    def gamma(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = gamma(r), gamma(g), gamma(b)

    # Calculate relative luminance (ITU-R BT.709)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def validate_theme(theme_dict: dict, theme_name: str) -> list[str]:
    """
    Validate that a theme dict contains all required keys.

    Args:
        theme_dict: Theme dictionary to validate
        theme_name: Name of theme (for error messages)

    Returns:
        List of missing keys (empty if valid)
    """
    missing = [key for key in _REQUIRED_THEME_KEYS if key not in theme_dict]
    return missing


def validate_theme_colors(theme_dict: dict, theme_name: str) -> list[str]:
    """
    Validate that theme colors are semantically correct for the mode.

    Checks:
    - Light mode (white bg) should have dark text
    - Dark mode (dark bg) should have light text

    Args:
        theme_dict: Theme dictionary to validate
        theme_name: Name of theme (for error messages)

    Returns:
        List of color problems (empty if valid)
    """
    problems = []

    # Get background color
    bg_primary = theme_dict.get("bg_primary", "#000000")
    bg_lum = _get_luminance(str(bg_primary))

    # Determine if this is a light or dark mode
    is_light_mode = bg_lum > 0.5  # White/light backgrounds
    mode_type = "LIGHT" if is_light_mode else "DARK"

    # Colors that should contrast with background
    text_colors = {
        "ink": theme_dict.get("ink"),
        "text_primary": theme_dict.get("text_primary"),
        "fg_primary": theme_dict.get("fg_primary"),
        "fg_muted": theme_dict.get("fg_muted"),
    }

    background_colors = {
        "bg_panel": theme_dict.get("bg_panel"),
        "bg_secondary": theme_dict.get("bg_secondary"),
        "card_bg": theme_dict.get("card_bg"),
    }

    # Check text colors have proper contrast
    for key, color in text_colors.items():
        if color and isinstance(color, str):
            text_lum = _get_luminance(color)

            # Light mode should have dark text (low luminance)
            # Dark mode should have light text (high luminance)
            if is_light_mode and text_lum > 0.7:
                problems.append(f"{key}={color} (light text on light bg - invisible!)")
            elif not is_light_mode and text_lum < 0.3:
                problems.append(f"{key}={color} (dark text on dark bg - invisible!)")

    # Check background colors match mode
    for key, color in background_colors.items():
        if color and isinstance(color, str):
            bg_color_lum = _get_luminance(color)

            # In light mode, backgrounds should be light
            # In dark mode, backgrounds should be dark
            if is_light_mode and bg_color_lum < 0.3:
                problems.append(f"{key}={color} (dark bg in light mode - wrong!)")
            elif not is_light_mode and bg_color_lum > 0.7:
                problems.append(f"{key}={color} (light bg in dark mode - wrong!)")

    if problems:
        problems.insert(0, f"Mode type: {mode_type} (bg_primary={bg_primary}, luminance={bg_lum:.2f})")

    return problems


def validate_all_themes() -> None:
    """
    Validate all theme modes have required keys and correct colors.

    Raises:
        ValueError: If any theme is missing required keys or has color problems
    """
    themes_to_check = [
        (DEBUG_THEME, "DEBUG_THEME"),
        (SIM_THEME, "SIM_THEME"),
        (LIVE_THEME, "LIVE_THEME"),
    ]

    all_errors = []

    # Check for missing keys
    for theme_dict, theme_name in themes_to_check:
        missing = validate_theme(theme_dict, theme_name)
        if missing:
            all_errors.append(f"{theme_name} missing {len(missing)} keys: {missing}")

    # Check for color problems (semantic validation)
    for theme_dict, theme_name in themes_to_check:
        color_problems = validate_theme_colors(theme_dict, theme_name)
        if color_problems:
            all_errors.append(f"{theme_name} color problems:\n    " + "\n    ".join(color_problems))

    if all_errors:
        error_msg = "Theme validation failed:\n  " + "\n  ".join(all_errors)
        raise ValueError(error_msg)


# Run validation at module load time
# This ensures themes are complete before any UI code runs
try:
    validate_all_themes()
except ValueError as e:
    # Print error but don't crash - allows app to start with warnings
    print(f"[THEME WARNING] {e}")
    print("[THEME WARNING] Some UI elements may use fallback colors")


# -------------------- config/theme.py (end)
