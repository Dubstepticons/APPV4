"""
Unit tests for symbol_utils module.

Tests symbol canonicalization, matching, and contract parsing.
"""

import pytest
from utils.symbol_utils import (
    canonicalize_symbol,
    symbols_match,
    extract_contract_info,
    is_futures_contract,
    get_display_symbol,
    normalize_symbol_for_storage,
    parse_dtc_symbol,
)


class TestSymbolCanonicalization:
    """Test symbol canonicalization."""

    def test_dtc_format_conversion(self):
        """Test DTC format (F.US.XXX) conversion."""
        assert canonicalize_symbol("F.US.ESH25") == "ESH25"
        assert canonicalize_symbol("F.US.MESZ25") == "MESZ25"
        assert canonicalize_symbol("F.CME.NQM24") == "NQM24"

    def test_already_canonical(self):
        """Test already canonical symbols remain unchanged."""
        assert canonicalize_symbol("ESH25") == "ESH25"
        assert canonicalize_symbol("NQM24") == "NQM24"
        assert canonicalize_symbol("MESZ25") == "MESZ25"

    def test_case_normalization(self):
        """Test case normalization to uppercase."""
        assert canonicalize_symbol("esh25") == "ESH25"
        assert canonicalize_symbol("nqm24") == "NQM24"
        assert canonicalize_symbol("f.us.esh25") == "ESH25"

    def test_spot_symbols(self):
        """Test spot/root only symbols."""
        assert canonicalize_symbol("ES") == "ES"
        assert canonicalize_symbol("NQ") == "NQ"
        assert canonicalize_symbol("MES") == "MES"

    def test_empty_symbol(self):
        """Test empty string handling."""
        assert canonicalize_symbol("") == ""
        assert canonicalize_symbol("   ") == ""


class TestSymbolMatching:
    """Test symbol matching across formats."""

    def test_exact_match(self):
        """Test exact symbol matching."""
        assert symbols_match("ESH25", "ESH25") is True
        assert symbols_match("NQM24", "NQM24") is True

    def test_format_variant_match(self):
        """Test matching across format variants."""
        assert symbols_match("ESH25", "F.US.ESH25") is True
        assert symbols_match("MESZ25", "F.US.MESZ25") is True
        assert symbols_match("NQM24", "F.CME.NQM24") is True

    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        assert symbols_match("ESH25", "esh25") is True
        assert symbols_match("f.us.esh25", "ESH25") is True

    def test_no_match(self):
        """Test non-matching symbols."""
        assert symbols_match("ESH25", "ESM25") is False
        assert symbols_match("ESH25", "NQH25") is False
        assert symbols_match("ES", "MES") is False


class TestContractInfoExtraction:
    """Test contract information parsing."""

    def test_standard_contract(self):
        """Test standard ES contract parsing."""
        info = extract_contract_info("ESH25")
        assert info is not None
        assert info["root"] == "ES"
        assert info["month"] == "H"
        assert info["year"] == "25"
        assert info["contract"] == "ESH25"
        assert info["month_name"] == "March"

    def test_micro_contract(self):
        """Test micro contract (MES) parsing."""
        info = extract_contract_info("MESZ25")
        assert info is not None
        assert info["root"] == "MES"
        assert info["month"] == "Z"
        assert info["year"] == "25"
        assert info["contract"] == "MESZ25"
        assert info["month_name"] == "December"

    def test_dtc_format_contract(self):
        """Test parsing DTC format symbols."""
        info = extract_contract_info("F.US.NQM24")
        assert info is not None
        assert info["root"] == "NQ"
        assert info["month"] == "M"
        assert info["year"] == "24"
        assert info["contract"] == "NQM24"
        assert info["month_name"] == "June"

    def test_month_codes(self):
        """Test all CME month codes."""
        month_tests = [
            ("ESF25", "F", "January"),
            ("ESG25", "G", "February"),
            ("ESH25", "H", "March"),
            ("ESJ25", "J", "April"),
            ("ESK25", "K", "May"),
            ("ESM25", "M", "June"),
            ("ESN25", "N", "July"),
            ("ESQ25", "Q", "August"),
            ("ESU25", "U", "September"),
            ("ESV25", "V", "October"),
            ("ESX25", "X", "November"),
            ("ESZ25", "Z", "December"),
        ]
        for symbol, month_code, month_name in month_tests:
            info = extract_contract_info(symbol)
            assert info is not None
            assert info["month"] == month_code
            assert info["month_name"] == month_name

    def test_non_futures_symbol(self):
        """Test non-futures symbols return None."""
        assert extract_contract_info("ES") is None
        assert extract_contract_info("AAPL") is None
        assert extract_contract_info("SPY") is None


class TestFuturesContractValidation:
    """Test futures contract validation."""

    def test_valid_contracts(self):
        """Test valid futures contract recognition."""
        assert is_futures_contract("ESH25") is True
        assert is_futures_contract("MESZ25") is True
        assert is_futures_contract("NQM24") is True
        assert is_futures_contract("F.US.ESH25") is True

    def test_invalid_contracts(self):
        """Test invalid contract rejection."""
        assert is_futures_contract("ES") is False
        assert is_futures_contract("AAPL") is False
        assert is_futures_contract("SPY123") is False
        assert is_futures_contract("") is False


class TestDisplaySymbol:
    """Test display symbol extraction."""

    def test_standard_display(self):
        """Test standard 3-char display."""
        assert get_display_symbol("ESH25", 3) == "ESH"
        assert get_display_symbol("MESZ25", 3) == "MES"
        assert get_display_symbol("NQM24", 3) == "NQM"

    def test_custom_length(self):
        """Test custom display length."""
        assert get_display_symbol("ESH25", 2) == "ES"
        assert get_display_symbol("MESZ25", 4) == "MESZ"
        assert get_display_symbol("NQM24", 5) == "NQM24"

    def test_dtc_format_display(self):
        """Test display from DTC format."""
        assert get_display_symbol("F.US.ESH25", 3) == "ESH"
        assert get_display_symbol("F.US.MESZ25", 3) == "MES"


class TestStorageNormalization:
    """Test symbol normalization for storage."""

    def test_storage_normalization(self):
        """Test consistent normalization for DB storage."""
        assert normalize_symbol_for_storage("F.US.ESH25") == "ESH25"
        assert normalize_symbol_for_storage("esh25") == "ESH25"
        assert normalize_symbol_for_storage("ESH25") == "ESH25"


class TestDTCSymbolParsing:
    """Test DTC-specific symbol parsing."""

    def test_full_dtc_format(self):
        """Test full DTC format parsing."""
        result = parse_dtc_symbol("F.US.ESH25")
        assert result["prefix"] == "F"
        assert result["exchange"] == "US"
        assert result["symbol"] == "ESH25"
        assert result["canonical"] == "ESH25"

    def test_cme_exchange(self):
        """Test CME exchange format."""
        result = parse_dtc_symbol("F.CME.NQM24")
        assert result["prefix"] == "F"
        assert result["exchange"] == "CME"
        assert result["symbol"] == "NQM24"
        assert result["canonical"] == "NQM24"

    def test_already_canonical_dtc_parse(self):
        """Test parsing already canonical symbols."""
        result = parse_dtc_symbol("ESH25")
        assert result["canonical"] == "ESH25"
        # prefix and exchange will be None since no dots
        assert result["prefix"] is None
        assert result["exchange"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
