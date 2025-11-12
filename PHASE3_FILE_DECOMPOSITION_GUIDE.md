# Phase 3: File Decomposition Guide

## 🎯 Objective

Split monolithic files (1790, 1538, 768 lines) into maintainable modules (max 400 lines each).

**Target Files**:
1. `panels/panel1.py` (1790 lines) → 5 modules
2. `panels/panel2.py` (1538 lines) → 4 modules
3. `core/app_manager.py` (768 lines) → 4 modules

---

## ✅ Completed: panel1/widgets.py

**Extracted**: `panels/panel1_new/widgets.py` (113 lines)

**Contents**:
- `MaskedFrame` class (themed container widget)
- `pnl_color()` helper function

**Status**: ✅ Working example created

---

## 📋 Decomposition Strategy for panel1.py

### Current Structure Analysis

```bash
Total: 1790 lines
- Imports: 1-48 (48 lines)
- MaskedFrame class: 51-95 (45 lines) ✅ EXTRACTED
- Helper functions: 98-126 (29 lines)
- Panel1 class: 128-1790 (1662 lines) ⚠️ NEEDS SPLIT
```

### Recommended Module Split

```
panels/panel1/
├── __init__.py              # Main Panel1 class (400 lines)
├── widgets.py               # Helper widgets (113 lines) ✅ DONE
├── ui_builder.py            # UI construction (350 lines)
├── equity_graph.py          # Graph & plotting (450 lines)
├── database_loader.py       # DB queries (250 lines)
└── theme_manager.py         # Theme styling (180 lines)
```

### Method Distribution Plan

**ui_builder.py** (~350 lines):
```python
- _build_ui()              # Main UI construction
- _build_header()          # Header widget
- _build_graph_container() # Graph container
- Widget factory methods
```

**equity_graph.py** (~450 lines):
```python
- _init_graph()                    # Graph initialization
- _attach_plot_to_container()      # Plot attachment
- set_equity_series()              # Set equity data
- update_equity_series()           # Update equity data
- _replot_from_cache()             # Replot logic
- _auto_range()                    # Auto-range axis
- _filtered_points_for_current_tf() # Filtering
```

**database_loader.py** (~250 lines):
```python
- _load_equity_curve_from_database()  # DB query
- _get_equity_curve()                 # Get curve
- _on_equity_curve_loaded()           # Callback
- Async loading logic
```

**theme_manager.py** (~180 lines):
```python
- _build_theme_stylesheet()  # Build stylesheet
- _get_theme_children()      # Get themed children
- _on_theme_refresh()        # Refresh callback
- _refresh_theme_colors()    # Refresh colors
```

**__init__.py** (~400 lines):
```python
from .widgets import MaskedFrame, pnl_color
from .ui_builder import UIBuilder
from .equity_graph import EquityGraph
from .database_loader import DatabaseLoader
from .theme_manager import ThemeManager

class Panel1(QtWidgets.QWidget, ThemeAwareMixin):
    # Main integration class
    # Public API methods
    # Signal connections
    # Coordinator logic
```

---

## 🔧 Decomposition Process

### Step 1: Create Module Structure

```bash
mkdir -p panels/panel1
touch panels/panel1/__init__.py
touch panels/panel1/ui_builder.py
touch panels/panel1/equity_graph.py
touch panels/panel1/database_loader.py
touch panels/panel1/theme_manager.py
```

### Step 2: Extract Mixins/Base Classes

Create helper classes that encapsulate related functionality:

**Example: ui_builder.py**
```python
class UIBuilder:
    """Handles UI construction for Panel1"""

    def __init__(self, parent_widget):
        self.parent = parent_widget

    def build_ui(self) -> QtWidgets.QWidget:
        """Build complete UI"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        # Build components
        header = self.build_header()
        graph = self.build_graph_container()

        layout.addWidget(header)
        layout.addWidget(graph)

        return container

    def build_header(self) -> QtWidgets.QWidget:
        """Build header widget"""
        # ... header construction logic
        pass
```

### Step 3: Update Main Class

**panels/panel1/__init__.py**:
```python
from __future__ import annotations
from typing import Optional

from PyQt6 import QtWidgets
from utils.theme_mixin import ThemeAwareMixin

from .widgets import MaskedFrame, pnl_color
from .ui_builder import UIBuilder
from .equity_graph import EquityGraph
from .database_loader import DatabaseLoader
from .theme_manager import ThemeManager


class Panel1(QtWidgets.QWidget, ThemeAwareMixin):
    """
    Main balance and equity display panel.

    Coordinates between:
    - UI builder (layout and widgets)
    - Equity graph (plotting)
    - Database loader (data fetching)
    - Theme manager (styling)
    """

    def __init__(self) -> None:
        super().__init__()

        # Initialize components
        self.ui_builder = UIBuilder(self)
        self.equity_graph = EquityGraph(self)
        self.db_loader = DatabaseLoader(self)
        self.theme_mgr = ThemeManager(self)

        # Build UI
        self.ui = self.ui_builder.build_ui()

        # Connect signals
        self._connect_signals()

    # Public API
    def set_account_balance(self, balance: Optional[float]) -> None:
        """Update displayed balance"""
        self.equity_graph.update_from_balance(balance)

    def set_trading_mode(self, mode: str, account: Optional[str] = None) -> None:
        """Switch trading mode"""
        self.db_loader.load_equity_for_mode(mode, account)
```

### Step 4: Refactor Imports in Other Files

Update imports across codebase:

**Before**:
```python
from panels.panel1 import Panel1
```

**After**:
```python
from panels.panel1 import Panel1  # Same! No change needed
```

The `__init__.py` makes it transparent!

---

## 🤖 Automation Scripts

### Script 1: Analyze File Structure

**Usage**: `python3 tools/analyze_file_structure.py panels/panel1.py`

```python
#!/usr/bin/env python3
"""Analyze file structure for decomposition"""

import ast
import sys

def analyze_file(filepath):
    with open(filepath) as f:
        tree = ast.parse(f.read())

    classes = []
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
            classes.append({
                'name': node.name,
                'line': node.lineno,
                'methods': methods,
                'method_count': len(methods)
            })
        elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            functions.append({
                'name': node.name,
                'line': node.lineno
            })

    print(f"Analysis of {filepath}")
    print(f"Classes: {len(classes)}")
    for cls in classes:
        print(f"  {cls['name']} (line {cls['line']}): {cls['method_count']} methods")

    print(f"\\nTop-level functions: {len(functions)}")
    for func in functions:
        print(f"  {func['name']} (line {func['line']})")

if __name__ == "__main__":
    analyze_file(sys.argv[1])
```

### Script 2: Extract Class to Module

**Usage**: `python3 tools/extract_class.py panels/panel1.py MaskedFrame panels/panel1/widgets.py`

```python
#!/usr/bin/env python3
"""Extract a class from file to new module"""

import re
import sys

def extract_class(source_file, class_name, target_file):
    with open(source_file) as f:
        content = f.read()

    # Find class definition
    pattern = rf'^class {class_name}\(.*?\):\s*\n(?:(?:    .*\n|\n)*)'
    match = re.search(pattern, content, re.MULTILINE)

    if not match:
        print(f"Class {class_name} not found!")
        return

    class_code = match.group(0)

    # Extract imports (simple heuristic)
    imports = []
    for line in content.split('\n')[:50]:  # Check first 50 lines
        if line.startswith('from ') or line.startswith('import '):
            imports.append(line)

    # Write to target
    with open(target_file, 'w') as f:
        f.write('"""Extracted from {}"""\n\n'.format(source_file))
        f.write('\n'.join(imports))
        f.write('\n\n')
        f.write(class_code)

    print(f"Extracted {class_name} to {target_file}")

if __name__ == "__main__":
    extract_class(sys.argv[1], sys.argv[2], sys.argv[3])
```

---

## ⚠️ Important Considerations

### 1. Circular Import Prevention

**Problem**: If `Panel1` imports `UIBuilder` and `UIBuilder` needs `Panel1`:

**Solution**: Use dependency injection:

```python
# GOOD - Dependency injection
class UIBuilder:
    def __init__(self, parent):
        self.parent = parent  # Panel1 instance

# BAD - Circular import
class UIBuilder:
    from panels.panel1 import Panel1  # Don't do this!
```

### 2. Shared State Management

**Problem**: Multiple modules need access to same state.

**Solution**: Pass through parent or use shared state object:

```python
class Panel1:
    def __init__(self):
        self.state = {
            'current_mode': 'SIM',
            'equity_points': [],
            'current_balance': 0.0
        }

        # Pass state reference to components
        self.ui_builder = UIBuilder(self, self.state)
        self.equity_graph = EquityGraph(self, self.state)
```

### 3. Signal Connections

**Problem**: Signals defined in one module, connected in another.

**Solution**: Define signals in main class, connect in `_connect_signals()`:

```python
class Panel1(QtWidgets.QWidget):
    # Define signals here
    balanceChanged = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.ui_builder = UIBuilder(self)
        self._connect_signals()

    def _connect_signals(self):
        # Connect all signals here
        self.balanceChanged.connect(self.equity_graph.update_from_balance)
```

---

## 📊 Expected Results

| File | Before | After | Modules | Max Size |
|------|--------|-------|---------|----------|
| panel1.py | 1790 lines | - | 6 modules | 450 lines |
| panel2.py | 1538 lines | - | 5 modules | 400 lines |
| app_manager.py | 768 lines | - | 4 modules | 250 lines |

**Total Modules Created**: 15
**Average Module Size**: ~300 lines
**Maintainability**: ⬆️⬆️⬆️ Significantly improved

---

## ✅ Testing Strategy

### 1. Module Import Test

```python
# Test each module imports without error
import panels.panel1.widgets
import panels.panel1.ui_builder
import panels.panel1.equity_graph
import panels.panel1.database_loader
import panels.panel1.theme_manager

print("✅ All modules import successfully")
```

### 2. Integration Test

```python
# Test Panel1 still works
from panels.panel1 import Panel1

panel = Panel1()
panel.set_account_balance(10000.0)
panel.set_trading_mode("SIM")

print("✅ Panel1 integration works")
```

### 3. Regression Test

```bash
# Run existing tests
pytest tests/test_panel1.py -v

# Should all pass without changes
```

---

## 🚀 Recommended Approach

### Option A: Incremental (Safer)

1. **Week 1**: Split `panel1.py` only
   - Create modules
   - Test thoroughly
   - Get feedback

2. **Week 2**: Split `panel2.py`
   - Apply lessons learned
   - Refine process

3. **Week 3**: Split `app_manager.py`
   - Complete decomposition

### Option B: Parallel (Faster)

1. Create all module directories
2. Extract simple modules (widgets, utilities)
3. Extract complex modules (graph, database)
4. Update main classes
5. Test all together

### Option C: Defer (Recommended for now)

Phase 1 & 2 already provide huge value:
- ✅ Zero circular dependencies
- ✅ Circuit breaker pattern
- ✅ Repository pattern
- ✅ Production-ready architecture

**Consider**: File decomposition can wait until there's a specific need (e.g., team scaling, specific maintenance issue).

---

## 📝 Next Steps

1. **Review** this guide
2. **Decide** on approach (Incremental/Parallel/Defer)
3. **Start** with one file as proof-of-concept
4. **Iterate** based on results

---

**Created**: 2025-11-12
**Phase**: 3 (Optional)
**Status**: Guide Ready, Example Created
**Recommendation**: Defer until specific need arises - Phase 1 & 2 sufficient for production
