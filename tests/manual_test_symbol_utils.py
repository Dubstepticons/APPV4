"""
Manual test script for symbol_utils (no pytest required).

Run with: python tests/manual_test_symbol_utils.py
"""

import sys
sys.path.insert(0, "/home/user/APPV4")

from utils.symbol_utils import (
    canonicalize_symbol,
    symbols_match,
    extract_contract_info,
    is_futures_contract,
    get_display_symbol,
    normalize_symbol_for_storage,
    parse_dtc_symbol,
)


def test_canonicalize_symbol():
    """Test symbol canonicalization."""
    print("Testing canonicalize_symbol...")

    # DTC format conversion
    assert canonicalize_symbol("F.US.ESH25") == "ESH25", "DTC format failed"
    assert canonicalize_symbol("F.US.MESZ25") == "MESZ25", "DTC MES format failed"

    # Already canonical
    assert canonicalize_symbol("ESH25") == "ESH25", "Canonical failed"

    # Case normalization
    assert canonicalize_symbol("esh25") == "ESH25", "Case normalization failed"

    # Spot symbols
    assert canonicalize_symbol("ES") == "ES", "Spot symbol failed"

    print("✓ canonicalize_symbol passed")


def test_symbols_match():
    """Test symbol matching."""
    print("Testing symbols_match...")

    # Exact match
    assert symbols_match("ESH25", "ESH25") is True, "Exact match failed"

    # Format variant match
    assert symbols_match("ESH25", "F.US.ESH25") is True, "Format variant failed"

    # Case insensitive
    assert symbols_match("ESH25", "esh25") is True, "Case insensitive failed"

    # No match
    assert symbols_match("ESH25", "ESM25") is False, "Non-match detection failed"

    print("✓ symbols_match passed")


def test_extract_contract_info():
    """Test contract info extraction."""
    print("Testing extract_contract_info...")

    # Standard contract
    info = extract_contract_info("ESH25")
    assert info is not None, "Standard contract extraction failed"
    assert info["root"] == "ES", "Root extraction failed"
    assert info["month"] == "H", "Month extraction failed"
    assert info["year"] == "25", "Year extraction failed"
    assert info["month_name"] == "March", "Month name failed"

    # Micro contract
    info = extract_contract_info("MESZ25")
    assert info is not None, "Micro contract extraction failed"
    assert info["root"] == "MES", "MES root failed"
    assert info["month"] == "Z", "December month failed"

    # Non-futures
    assert extract_contract_info("ES") is None, "Non-futures detection failed"

    print("✓ extract_contract_info passed")


def test_is_futures_contract():
    """Test futures contract validation."""
    print("Testing is_futures_contract...")

    assert is_futures_contract("ESH25") is True, "Valid contract failed"
    assert is_futures_contract("ES") is False, "Spot rejection failed"

    print("✓ is_futures_contract passed")


def test_get_display_symbol():
    """Test display symbol extraction."""
    print("Testing get_display_symbol...")

    assert get_display_symbol("ESH25", 3) == "ESH", "Display symbol failed"
    assert get_display_symbol("MESZ25", 3) == "MES", "MES display failed"
    assert get_display_symbol("ESH25", 2) == "ES", "Custom length failed"

    print("✓ get_display_symbol passed")


def test_normalize_symbol_for_storage():
    """Test storage normalization."""
    print("Testing normalize_symbol_for_storage...")

    assert normalize_symbol_for_storage("F.US.ESH25") == "ESH25", "Storage norm failed"
    assert normalize_symbol_for_storage("esh25") == "ESH25", "Case norm failed"

    print("✓ normalize_symbol_for_storage passed")


def test_parse_dtc_symbol():
    """Test DTC symbol parsing."""
    print("Testing parse_dtc_symbol...")

    result = parse_dtc_symbol("F.US.ESH25")
    assert result["prefix"] == "F", "Prefix extraction failed"
    assert result["exchange"] == "US", "Exchange extraction failed"
    assert result["symbol"] == "ESH25", "Symbol extraction failed"
    assert result["canonical"] == "ESH25", "Canonical extraction failed"

    print("✓ parse_dtc_symbol passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Symbol Utils Manual Tests")
    print("="*60 + "\n")

    try:
        test_canonicalize_symbol()
        test_symbols_match()
        test_extract_contract_info()
        test_is_futures_contract()
        test_get_display_symbol()
        test_normalize_symbol_for_storage()
        test_parse_dtc_symbol()

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60 + "\n")
        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
