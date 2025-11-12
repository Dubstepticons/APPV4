"""
Helpers Module

Utility functions for Panel2 (Trading panel).
Extracted from panels/panel2.py for modularity.

Functions:
- fmt_time_human(): Format seconds as human-readable time
- sign_from_side(): Convert position side to +1/-1/0
- clamp(): Clamp value between min/max
- extract_symbol_display(): Extract 3-letter symbol from full DTC symbol
"""

from typing import Optional


def fmt_time_human(seconds: int) -> str:
    """
    Format seconds as human-readable time string.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like '20s', '1:20s', '10:00s'

    Examples:
        fmt_time_human(20) -> "20s"
        fmt_time_human(80) -> "1:20s"
        fmt_time_human(600) -> "10:00s"
    """
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}s"


def sign_from_side(is_long: Optional[bool]) -> int:
    """
    Convert position side boolean to signed integer.

    Args:
        is_long: True for long, False for short, None for flat

    Returns:
        +1 for long, -1 for short, 0 for flat/None
    """
    if is_long is True:
        return 1
    if is_long is False:
        return -1
    return 0


def clamp(v: float, lo: float, hi: float) -> float:
    """
    Clamp value between minimum and maximum.

    Args:
        v: Value to clamp
        lo: Minimum value
        hi: Maximum value

    Returns:
        Clamped value
    """
    return max(lo, min(hi, v))


def extract_symbol_display(full_symbol: str) -> str:
    """
    Extract 3-letter display symbol from full DTC symbol.

    Args:
        full_symbol: Full DTC symbol (e.g., "F.US.MESZ25")

    Returns:
        3-letter symbol (e.g., "MES")

    Examples:
        extract_symbol_display("F.US.MESZ25") -> "MES"
        extract_symbol_display("F.US.ESH25") -> "ESH"
        extract_symbol_display("UNKNOWN") -> "UNKNOWN"

    Note:
        Looks for pattern: *.US.XXX* where XXX are the 3 letters we want.
        If format doesn't match, returns full symbol as-is.
    """
    try:
        # Look for pattern: *.US.XXX* where XXX are the 3 letters we want
        parts = full_symbol.split(".")
        for i, part in enumerate(parts):
            if part == "US" and i + 1 < len(parts):
                # Get the next part after 'US'
                next_part = parts[i + 1]
                if len(next_part) >= 3:
                    # Extract first 3 letters
                    return next_part[:3].upper()
        # Fallback: return as-is
        return full_symbol.strip().upper()
    except Exception:
        return full_symbol.strip().upper()
