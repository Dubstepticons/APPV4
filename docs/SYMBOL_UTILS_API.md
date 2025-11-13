# Symbol Utils API Reference

## Overview

The `symbol_utils` module provides consistent symbol handling across DTC messages, CSV feeds, and manual inputs. It normalizes different symbol formats and provides contract parsing utilities.

## Quick Start

```python
from utils.symbol_utils import (
    canonicalize_symbol,
    symbols_match,
    extract_contract_info,
    is_futures_contract,
    get_display_symbol,
)

# Normalize DTC symbol
symbol = canonicalize_symbol("F.US.ESH25")  # → "ESH25"

# Check if two symbols are the same
if symbols_match("ESH25", "F.US.ESH25"):  # → True
    print("Same contract!")

# Parse contract details
info = extract_contract_info("MESZ25")
# → {'root': 'MES', 'month': 'Z', 'year': '25', 'contract': 'MESZ25', 'month_name': 'December'}

# Get short display version
display = get_display_symbol("ESH25", 3)  # → "ESH"
```

## API Reference

### `canonicalize_symbol(symbol: str) -> str`

Convert any symbol variant to canonical format.

**Canonical Format**: `ROOT + MONTH + YEAR` (e.g., "ESH25", "NQM24")

**Parameters:**
- `symbol` (str): Symbol in any format

**Returns:**
- `str`: Canonical symbol (uppercase)

**Examples:**
```python
>>> canonicalize_symbol("F.US.ESH25")
'ESH25'

>>> canonicalize_symbol("esh25")
'ESH25'

>>> canonicalize_symbol("F.CME.MESZ25")
'MESZ25'

>>> canonicalize_symbol("ES")  # Spot symbol
'ES'
```

**Supported Formats:**
- DTC format: `F.US.ESH25` → `ESH25`
- CME format: `F.CME.NQM24` → `NQM24`
- Lowercase: `esh25` → `ESH25`
- Already canonical: `ESH25` → `ESH25`

---

### `symbols_match(sym1: str, sym2: str) -> bool`

Check if two symbols refer to the same contract.

**Parameters:**
- `sym1` (str): First symbol (any format)
- `sym2` (str): Second symbol (any format)

**Returns:**
- `bool`: True if symbols match after canonicalization

**Examples:**
```python
>>> symbols_match("ESH25", "F.US.ESH25")
True

>>> symbols_match("esh25", "ESH25")
True

>>> symbols_match("ESH25", "ESM25")
False
```

**Use Cases:**
- Position/order correlation
- Symbol matching across different data sources
- Database lookups

---

### `extract_contract_info(symbol: str) -> Optional[dict]`

Extract contract details from symbol.

**Parameters:**
- `symbol` (str): Symbol to parse (any format)

**Returns:**
- `dict`: Contract information, or `None` if not a futures contract

**Return Dict Fields:**
- `root` (str): Product root (e.g., "ES", "NQ", "MES")
- `month` (str): Month code (e.g., "H", "M", "Z")
- `year` (str): Year (e.g., "25", "24")
- `contract` (str): Full contract code (e.g., "ESH25")
- `month_name` (str): Full month name (e.g., "March")

**Examples:**
```python
>>> extract_contract_info("ESH25")
{
    'root': 'ES',
    'month': 'H',
    'year': '25',
    'contract': 'ESH25',
    'month_name': 'March'
}

>>> extract_contract_info("MESZ25")
{
    'root': 'MES',
    'month': 'Z',
    'year': '25',
    'contract': 'MESZ25',
    'month_name': 'December'
}

>>> extract_contract_info("ES")  # Spot symbol
None
```

**CME Month Codes:**
```
F = January    | G = February | H = March    | J = April
K = May        | M = June     | N = July     | Q = August
U = September  | V = October  | X = November | Z = December
```

---

### `is_futures_contract(symbol: str) -> bool`

Check if symbol represents a futures contract.

**Parameters:**
- `symbol` (str): Symbol to check

**Returns:**
- `bool`: True if symbol matches futures contract pattern

**Examples:**
```python
>>> is_futures_contract("ESH25")
True

>>> is_futures_contract("MESZ25")
True

>>> is_futures_contract("F.US.ESH25")
True

>>> is_futures_contract("ES")
False

>>> is_futures_contract("AAPL")
False
```

**Valid Pattern:**
- 2-4 letters (root) + 1 month code + 2 digits (year)
- Examples: `ESH25`, `MESZ25`, `NQM24`

---

### `get_display_symbol(symbol: str, max_length: int = 3) -> str`

Get short display version of symbol for UI.

**Parameters:**
- `symbol` (str): Full symbol
- `max_length` (int): Maximum length (default: 3)

**Returns:**
- `str`: Short display symbol (uppercase)

**Examples:**
```python
>>> get_display_symbol("ESH25", 3)
'ESH'

>>> get_display_symbol("MESZ25", 3)
'MES'

>>> get_display_symbol("F.US.NQM24", 2)
'NQ'

>>> get_display_symbol("ESH25", 5)
'ESH25'
```

**Use Cases:**
- Compact UI display (3-letter symbols)
- Panel headers
- Chart labels

---

### `normalize_symbol_for_storage(symbol: str) -> str`

Normalize symbol for consistent database storage.

**Parameters:**
- `symbol` (str): Symbol in any format

**Returns:**
- `str`: Normalized symbol for storage

**Examples:**
```python
>>> normalize_symbol_for_storage("F.US.ESH25")
'ESH25'

>>> normalize_symbol_for_storage("esh25")
'ESH25'

>>> normalize_symbol_for_storage("ESH25")
'ESH25'
```

**Use Cases:**
- Database inserts/updates
- Ensuring consistent symbol format in trades table
- Symbol-based queries

---

### `parse_dtc_symbol(dtc_symbol: str) -> dict`

Parse DTC-specific symbol format.

**Parameters:**
- `dtc_symbol` (str): Symbol from DTC message

**Returns:**
- `dict`: Parsed components

**Return Dict Fields:**
- `exchange` (str): Exchange identifier (e.g., "US", "CME")
- `symbol` (str): Symbol part after exchange
- `prefix` (str): Prefix (usually "F" for futures)
- `canonical` (str): Canonical symbol

**Examples:**
```python
>>> parse_dtc_symbol("F.US.ESH25")
{
    'exchange': 'US',
    'symbol': 'ESH25',
    'prefix': 'F',
    'canonical': 'ESH25'
}

>>> parse_dtc_symbol("F.CME.NQM24")
{
    'exchange': 'CME',
    'symbol': 'NQM24',
    'prefix': 'F',
    'canonical': 'NQM24'
}

>>> parse_dtc_symbol("ESH25")  # Already canonical
{
    'exchange': None,
    'symbol': 'ESH25',
    'prefix': None,
    'canonical': 'ESH25'
}
```

---

## Common Use Cases

### 1. Normalize DTC Symbol for Display

```python
def update_symbol_banner(dtc_symbol: str):
    """Update panel symbol banner from DTC message."""
    display = get_display_symbol(dtc_symbol, 3)  # "ESH"
    panel.symbol_banner.setText(display)
```

### 2. Match Position with Order

```python
def find_matching_order(position_symbol: str, orders: list) -> Optional[dict]:
    """Find order matching position symbol."""
    for order in orders:
        if symbols_match(position_symbol, order['Symbol']):
            return order
    return None
```

### 3. Store Trade with Consistent Symbol

```python
def record_trade(symbol: str, qty: int, price: float):
    """Record trade with normalized symbol."""
    canonical = normalize_symbol_for_storage(symbol)
    db.insert_trade(symbol=canonical, qty=qty, price=price)
```

### 4. Display Contract Information

```python
def show_contract_details(symbol: str):
    """Show contract month and year."""
    info = extract_contract_info(symbol)
    if info:
        print(f"Contract: {info['root']} {info['month_name']} 20{info['year']}")
        # Output: "Contract: ES March 2025"
```

### 5. Validate Symbol Format

```python
def validate_symbol_input(user_input: str) -> bool:
    """Validate user-entered symbol."""
    canonical = canonicalize_symbol(user_input)
    return is_futures_contract(canonical)
```

## Testing

### Run Unit Tests

```bash
# Manual tests (no pytest required)
python tests/manual_test_symbol_utils.py
```

### Expected Output

```
============================================================
Symbol Utils Manual Tests
============================================================

✓ canonicalize_symbol passed
✓ symbols_match passed
✓ extract_contract_info passed
✓ is_futures_contract passed
✓ get_display_symbol passed
✓ normalize_symbol_for_storage passed
✓ parse_dtc_symbol passed

============================================================
✓ ALL TESTS PASSED (7/7)
============================================================
```

## Performance

- **canonicalize_symbol**: O(n) where n = symbol length (typically < 20 chars)
- **symbols_match**: O(n + m) where n, m = symbol lengths
- **extract_contract_info**: O(n) with regex match
- **Memory**: Minimal (no caching, stateless functions)

## Error Handling

All functions handle errors gracefully:

```python
# Invalid input → Safe fallback
canonicalize_symbol("")  # → ""
canonicalize_symbol(None)  # → "" (if converted to string)

extract_contract_info("INVALID")  # → None
is_futures_contract("ABC")  # → False

# Whitespace handled
canonicalize_symbol("  ESH25  ")  # → "ESH25"
```

## Integration with Other Modules

### With DTC Parser

```python
# dtc_parser.py normalizes symbols automatically
symbol = payload.get("Symbol")  # "F.US.ESH25"
canonical = canonicalize_symbol(symbol)  # "ESH25"
```

### With Trading Specs

```python
from config.trading_specs import match_spec
from utils.symbol_utils import canonicalize_symbol

symbol = canonicalize_symbol("F.US.MESZ25")  # "MESZ25"
spec = match_spec(symbol)  # Get tick size, point value, etc.
```

### With Database Queries

```python
from utils.symbol_utils import normalize_symbol_for_storage

# Ensure consistent format for queries
symbol = normalize_symbol_for_storage(user_input)
trades = db.query_trades_by_symbol(symbol)
```

## Migration Guide

### Before (Inconsistent Symbol Handling)

```python
# Different parts of code handled symbols differently
symbol1 = msg.get("Symbol")  # "F.US.ESH25"
symbol2 = csv_row["symbol"]  # "ESH25"
symbol3 = user_input.upper()  # "esh25" → "ESH25"

# Hard to match across sources
if symbol1 == symbol2:  # False! (different formats)
    ...
```

### After (Consistent Symbol Handling)

```python
from utils.symbol_utils import canonicalize_symbol, symbols_match

symbol1 = canonicalize_symbol(msg.get("Symbol"))  # "ESH25"
symbol2 = canonicalize_symbol(csv_row["symbol"])  # "ESH25"
symbol3 = canonicalize_symbol(user_input)  # "ESH25"

# Easy matching across sources
if symbols_match(symbol1, symbol2):  # True!
    ...
```

## Related Documentation

- [Mode Filtering Guide](./MODE_FILTERING_GUIDE.md)
- [DTC Parser Reference](./DTC_PARSER_REFERENCE.md)
- [Trading Specs](../config/trading_specs.py)

## Changelog

### Phase 3 (Option B)
- ✅ Created symbol_utils module
- ✅ Implemented canonicalization functions
- ✅ Added contract info parsing
- ✅ Added comprehensive tests
- ✅ Documented API
