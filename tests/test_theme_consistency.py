# -------------------- test_theme_consistency (start)
import re

from config import theme


HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
OKLCH_RE = re.compile(r"^oklch\(\s*[\d.]+%?\s+[\d.]+\s+[\d.]+\s*\)$")


def _is_color(value: str) -> bool:
    """Detect if a value looks like a color (hex or oklch)."""
    if not isinstance(value, str):
        return False
    return bool(HEX_RE.match(value) or OKLCH_RE.match(value) or value.startswith("rgb"))


def test_all_themes_have_same_keys():
    """Ensure DEBUG, LIVE, and SIM themes contain identical keys."""
    base_keys = set(theme.DEBUG_THEME.keys())
    for name, t in [("LIVE", theme.LIVE_THEME), ("SIM", theme.SIM_THEME)]:
        missing = base_keys - set(t.keys())
        extra = set(t.keys()) - base_keys
        assert not missing, f"{name} missing keys: {missing}"
        assert not extra, f"{name} has extra keys: {extra}"


def test_all_modes_cover_base_theme():
    """Ensure every mode defines all keys from _BASE_THEME."""
    base_keys = set(theme._BASE_THEME.keys())
    for name, t in [
        ("DEBUG", theme.DEBUG_THEME),
        ("LIVE", theme.LIVE_THEME),
        ("SIM", theme.SIM_THEME),
    ]:
        missing = base_keys - set(t.keys())
        assert not missing, f"{name} missing base keys: {missing}"


def test_color_fields_are_valid_formats():
    """Ensure all color-like fields are valid hex or OKLCH strings."""
    for name, t in [
        ("DEBUG", theme.DEBUG_THEME),
        ("LIVE", theme.LIVE_THEME),
        ("SIM", theme.SIM_THEME),
    ]:
        bad_colors = {}
        for k, v in t.items():
            if isinstance(v, str) and (
                "color" in k or "bg" in k or "fg" in k or "ink" in k or "accent" in k or "border" in k or "pnl" in k
            ):
                if not _is_color(v) and v not in ("none", "transparent"):
                    bad_colors[k] = v
        assert not bad_colors, f"{name} theme has invalid color values: {bad_colors}"


def test_theme_types_match_debug_baseline():
    """Ensure LIVE and SIM theme values match DEBUG types."""
    baseline = {k: type(v) for k, v in theme.DEBUG_THEME.items()}
    for name, t in [("LIVE", theme.LIVE_THEME), ("SIM", theme.SIM_THEME)]:
        mismatched = {k: (type(t[k]), baseline[k]) for k in t if k in baseline and type(t[k]) is not baseline[k]}
        assert not mismatched, f"{name} theme type mismatches: {mismatched}"


def test_oklch_validation_function():
    """Test the validate_oklch_tokens() function returns no errors."""
    errors = theme.validate_oklch_tokens()
    assert not errors, f"OKLCH validation failed: {errors}"


def test_oklch_tokens_have_percentage_sign():
    """Ensure all OKLCH tokens use percentage notation (L%) not decimal (0.L)."""
    for token_name, color in theme._COLOR_TOKENS.items():
        if color.startswith("oklch("):
            assert "%" in color, f"Token '{token_name}': OKLCH missing % sign: '{color}'"


def test_oklch_lightness_in_range():
    """Ensure all OKLCH lightness values are in range [0, 100]."""
    import re

    oklch_pattern = re.compile(r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)")
    for token_name, color in theme._COLOR_TOKENS.items():
        if not color.startswith("oklch("):
            continue
        match = oklch_pattern.match(color.strip())
        if match:
            l_val = float(match.group(1))
            assert 0 <= l_val <= 100, f"Token '{token_name}': Lightness {l_val} out of range [0, 100]"


def test_oklch_chroma_in_range():
    """Ensure all OKLCH chroma values are in typical range [0, 0.5]."""
    import re

    oklch_pattern = re.compile(r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)")
    for token_name, color in theme._COLOR_TOKENS.items():
        if not color.startswith("oklch("):
            continue
        match = oklch_pattern.match(color.strip())
        if match:
            c_val = float(match.group(2))
            assert 0 <= c_val <= 0.5, f"Token '{token_name}': Chroma {c_val} out of typical range [0, 0.5]"


def test_oklch_hue_in_range():
    """Ensure all OKLCH hue values are in range [0, 360]."""
    import re

    oklch_pattern = re.compile(r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)")
    for token_name, color in theme._COLOR_TOKENS.items():
        if not color.startswith("oklch("):
            continue
        match = oklch_pattern.match(color.strip())
        if match:
            h_val = float(match.group(3))
            assert 0 <= h_val <= 360, f"Token '{token_name}': Hue {h_val} out of range [0, 360]"


def test_theme_key_consistency_function():
    """Test the validate_theme_keys_consistency() function returns no errors."""
    errors = theme.validate_theme_keys_consistency()
    assert not errors, f"Theme key consistency validation failed: {errors}"


def test_switch_theme_function():
    """Test that switch_theme() correctly switches between modes."""
    # Test switching to each mode
    for mode_name in ["debug", "live", "sim"]:
        theme.switch_theme(mode_name)
        # Verify THEME dict was updated
        assert theme.THEME is not None
        assert len(theme.THEME) > 0

    # Test unknown mode defaults to DEBUG
    theme.switch_theme("unknown_mode")
    assert theme.THEME.get("pnl_pos_color") == theme.DEBUG_THEME.get("pnl_pos_color")


def test_no_hardcoded_colors_in_production_code():
    """Verify no hardcoded hex colors in panel/widget files (regression test)."""
    import os
    from pathlib import Path

    # Check key production files
    production_files = [
        "panels/panel1.py",
        "panels/panel2.py",
        "panels/panel3.py",
        "widgets/connection_icon.py",
        "widgets/metric_cell.py",
    ]

    hex_pattern = re.compile(r'["\'](#[0-9A-Fa-f]{6})["\']')

    for rel_path in production_files:
        file_path = Path(__file__).parent.parent / rel_path
        if not file_path.exists():
            continue

        with open(file_path, "r") as f:
            content = f.read()

        # Find all hex colors
        matches = hex_pattern.findall(content)

        # Filter out colors that appear in THEME.get() fallbacks
        suspicious = [m for m in matches if "THEME.get" not in content[max(0, content.find(m) - 50) : content.find(m) + 50]]

        assert not suspicious, f"Found hardcoded hex colors in {rel_path}: {suspicious}"


# -------------------- test_theme_consistency (end)
