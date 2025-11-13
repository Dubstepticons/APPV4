"""
Symbol Canonicalization and Utilities

Provides consistent symbol handling across DTC, CSV, and manual inputs.
Ensures symbol formats are normalized for database storage and matching.

Examples:
    >>> canonicalize_symbol("F.US.ESH25")
    'ESH25'

    >>> symbols_match("ESH25", "F.US.ESH25")
    True

    >>> extract_contract_info("ESH25")
    {'root': 'ES', 'month': 'H', 'year': '25', 'contract': 'ESH25'}
"""

from __future__ import annotations

import re
from typing import Optional


# Contract month codes (CME standard)
MONTH_CODES = {
    'F': 'January',
    'G': 'February',
    'H': 'March',
    'J': 'April',
    'K': 'May',
    'M': 'June',
    'N': 'July',
    'Q': 'August',
    'U': 'September',
    'V': 'October',
    'X': 'November',
    'Z': 'December',
}


def canonicalize_symbol(symbol: str) -> str:
    """
    Convert any symbol variant to canonical format.

    Canonical format: ROOT + MONTH + YEAR (e.g., "ESH25", "NQM24")

    Handles formats:
    - "F.US.ESH25" -> "ESH25"
    - "ESH25" -> "ESH25"
    - "F.US.MESZ25" -> "MESZ25"
    - "ES" -> "ES" (spot/root only)

    Args:
        symbol: Symbol in any format

    Returns:
        Canonical symbol string (uppercase)

    Examples:
        >>> canonicalize_symbol("F.US.ESH25")
        'ESH25'
        >>> canonicalize_symbol("esh25")
        'ESH25'
        >>> canonicalize_symbol("ES")
        'ES'
    """
    if not symbol:
        return ""

    symbol = symbol.strip().upper()

    # Handle DTC format: F.US.XXXXX
    if ".US." in symbol:
        parts = symbol.split(".")
        for i, part in enumerate(parts):
            if part == "US" and i + 1 < len(parts):
                return parts[i + 1]

    # Already canonical or spot/root only
    return symbol


def symbols_match(sym1: str, sym2: str) -> bool:
    """
    Check if two symbols refer to the same contract.

    Handles different format variants:
    - "ESH25" matches "F.US.ESH25"
    - "esh25" matches "ESH25"
    - Case insensitive

    Args:
        sym1: First symbol (any format)
        sym2: Second symbol (any format)

    Returns:
        True if symbols match after canonicalization

    Examples:
        >>> symbols_match("ESH25", "F.US.ESH25")
        True
        >>> symbols_match("esh25", "ESH25")
        True
        >>> symbols_match("ESH25", "ESM25")
        False
    """
    return canonicalize_symbol(sym1) == canonicalize_symbol(sym2)


def extract_contract_info(symbol: str) -> Optional[dict]:
    """
    Extract contract details from symbol.

    Parses symbol to extract:
    - root: Product root (e.g., "ES", "NQ", "MES")
    - month: Month code (e.g., "H", "M", "Z")
    - year: Year (e.g., "25", "24")
    - contract: Full contract code (e.g., "ESH25")
    - month_name: Full month name (e.g., "March")

    Args:
        symbol: Symbol to parse (any format)

    Returns:
        Dict with contract info, or None if not a futures contract

    Examples:
        >>> extract_contract_info("ESH25")
        {'root': 'ES', 'month': 'H', 'year': '25', 'contract': 'ESH25', 'month_name': 'March'}

        >>> extract_contract_info("F.US.MESZ25")
        {'root': 'MES', 'month': 'Z', 'year': '25', 'contract': 'MESZ25', 'month_name': 'December'}

        >>> extract_contract_info("ES")
        None
    """
    canonical = canonicalize_symbol(symbol)

    # Pattern: 2-4 letters (root) + 1 letter (month) + 2 digits (year)
    # Examples: ESH25, MESZ25, NQM24
    pattern = r'^([A-Z]{2,4})([FGHJKMNQUVXZ])(\d{2})$'
    match = re.match(pattern, canonical)

    if not match:
        return None

    root, month, year = match.groups()

    return {
        'root': root,
        'month': month,
        'year': year,
        'contract': canonical,
        'month_name': MONTH_CODES.get(month, 'Unknown'),
    }


def is_futures_contract(symbol: str) -> bool:
    """
    Check if symbol represents a futures contract.

    Args:
        symbol: Symbol to check

    Returns:
        True if symbol matches futures contract pattern

    Examples:
        >>> is_futures_contract("ESH25")
        True
        >>> is_futures_contract("ES")
        False
        >>> is_futures_contract("F.US.MESZ25")
        True
    """
    return extract_contract_info(symbol) is not None


def get_display_symbol(symbol: str, max_length: int = 3) -> str:
    """
    Get short display version of symbol for UI.

    Extracts first N characters of the root for compact display.

    Args:
        symbol: Full symbol
        max_length: Maximum length of display symbol (default: 3)

    Returns:
        Short display symbol (uppercase)

    Examples:
        >>> get_display_symbol("ESH25", 3)
        'ESH'
        >>> get_display_symbol("MESZ25", 3)
        'MES'
        >>> get_display_symbol("F.US.NQM24", 2)
        'NQ'
    """
    canonical = canonicalize_symbol(symbol)
    info = extract_contract_info(canonical)

    if info:
        # For futures: show root + month code (up to max_length)
        display = info['root'] + info['month']
        return display[:max_length].upper()
    else:
        # For non-futures: just take first N characters
        return canonical[:max_length].upper()


def normalize_symbol_for_storage(symbol: str) -> str:
    """
    Normalize symbol for consistent database storage.

    Ensures all symbols are stored in canonical uppercase format.

    Args:
        symbol: Symbol in any format

    Returns:
        Normalized symbol for storage

    Examples:
        >>> normalize_symbol_for_storage("F.US.ESH25")
        'ESH25'
        >>> normalize_symbol_for_storage("esh25")
        'ESH25'
    """
    return canonicalize_symbol(symbol)


def parse_dtc_symbol(dtc_symbol: str) -> dict:
    """
    Parse DTC-specific symbol format.

    DTC symbols: "F.US.XXXXX" or "F.CME.XXXXX"

    Args:
        dtc_symbol: Symbol from DTC message

    Returns:
        Dict with parsed components

    Examples:
        >>> parse_dtc_symbol("F.US.ESH25")
        {'exchange': 'US', 'symbol': 'ESH25', 'prefix': 'F', 'canonical': 'ESH25'}
    """
    parts = dtc_symbol.strip().split(".")

    result = {
        'exchange': None,
        'symbol': dtc_symbol,
        'prefix': None,
        'canonical': canonicalize_symbol(dtc_symbol),
    }

    if len(parts) >= 3:
        result['prefix'] = parts[0]  # e.g., "F" for futures
        result['exchange'] = parts[1]  # e.g., "US" or "CME"
        result['symbol'] = ".".join(parts[2:])  # e.g., "ESH25"

    return result
