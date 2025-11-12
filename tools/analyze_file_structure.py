#!/usr/bin/env python3
"""
Analyze File Structure for Decomposition

Parses Python files and reports class/function structure to help plan decomposition.

Usage:
    python3 tools/analyze_file_structure.py panels/panel1.py
    python3 tools/analyze_file_structure.py panels/panel2.py
"""

import ast
import sys
from pathlib import Path


def count_lines_in_node(node, source_lines):
    """Count actual lines of code in an AST node"""
    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
        return node.end_lineno - node.lineno + 1
    return 0


def analyze_file(filepath):
    """
    Analyze Python file structure.

    Args:
        filepath: Path to Python file

    Prints:
        - File statistics
        - Class definitions with method counts
        - Top-level functions
        - Recommended decomposition strategy
    """
    path = Path(filepath)

    if not path.exists():
        print(f"Error: {filepath} not found!")
        return

    with open(path) as f:
        content = f.read()
        source_lines = content.split('\n')

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        return

    # Collect classes and functions
    classes = []
    functions = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [
                {
                    'name': m.name,
                    'line': m.lineno,
                    'lines': count_lines_in_node(m, source_lines)
                }
                for m in node.body if isinstance(m, ast.FunctionDef)
            ]

            classes.append({
                'name': node.name,
                'line': node.lineno,
                'lines': count_lines_in_node(node, source_lines),
                'methods': methods,
                'method_count': len(methods)
            })

        elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            functions.append({
                'name': node.name,
                'line': node.lineno,
                'lines': count_lines_in_node(node, source_lines)
            })

        elif isinstance(node, (ast.Import, ast.ImportFrom)) and node.col_offset == 0:
            imports.append(node.lineno)

    # Print analysis
    total_lines = len(source_lines)
    print(f"\n{'='*70}")
    print(f"FILE STRUCTURE ANALYSIS: {filepath}")
    print(f"{'='*70}\n")

    print(f"📊 Statistics:")
    print(f"   Total lines: {total_lines}")
    print(f"   Import statements: {len(imports)}")
    print(f"   Classes: {len(classes)}")
    print(f"   Top-level functions: {len(functions)}\n")

    # Classes detail
    if classes:
        print(f"📦 Classes:")
        for cls in sorted(classes, key=lambda x: x['line']):
            print(f"   {cls['name']} (lines {cls['line']}-{cls['line']+cls['lines']})")
            print(f"      Size: {cls['lines']} lines")
            print(f"      Methods: {cls['method_count']}")

            # Show largest methods
            large_methods = [m for m in cls['methods'] if m['lines'] > 50]
            if large_methods:
                print(f"      Large methods (>50 lines):")
                for m in sorted(large_methods, key=lambda x: -x['lines']):
                    print(f"         - {m['name']}: {m['lines']} lines (line {m['line']})")
            print()

    # Functions detail
    if functions:
        print(f"🔧 Top-level Functions:")
        for func in sorted(functions, key=lambda x: x['line']):
            print(f"   {func['name']} (line {func['line']}): {func['lines']} lines")
        print()

    # Decomposition recommendations
    print(f"💡 Decomposition Recommendations:")

    if total_lines > 1000:
        print(f"   ⚠️  File is large ({total_lines} lines) - decomposition recommended")
        print(f"   📌 Target: Split into {(total_lines // 400) + 1} modules (~400 lines each)")
    elif total_lines > 500:
        print(f"   ⚡ File is medium ({total_lines} lines) - consider splitting")
        print(f"   📌 Target: 2-3 modules")
    else:
        print(f"   ✅ File size is manageable ({total_lines} lines)")

    # Class-specific recommendations
    for cls in classes:
        if cls['lines'] > 800:
            print(f"\n   Class '{cls['name']}' is very large ({cls['lines']} lines)")
            print(f"   Suggested modules:")

            # Group methods by category (simple heuristic)
            ui_methods = [m for m in cls['methods'] if any(x in m['name'].lower() for x in ['build', 'ui', 'widget', 'layout'])]
            db_methods = [m for m in cls['methods'] if any(x in m['name'].lower() for x in ['load', 'database', 'query', 'db'])]
            graph_methods = [m for m in cls['methods'] if any(x in m['name'].lower() for x in ['graph', 'plot', 'chart', 'equity'])]
            theme_methods = [m for m in cls['methods'] if any(x in m['name'].lower() for x in ['theme', 'style', 'color'])]

            if ui_methods:
                print(f"      - ui_builder.py ({len(ui_methods)} methods): UI construction")
            if db_methods:
                print(f"      - database_loader.py ({len(db_methods)} methods): Data loading")
            if graph_methods:
                print(f"      - graph_manager.py ({len(graph_methods)} methods): Graphing logic")
            if theme_methods:
                print(f"      - theme_manager.py ({len(theme_methods)} methods): Theme styling")

            other_methods = len(cls['methods']) - len(ui_methods) - len(db_methods) - len(graph_methods) - len(theme_methods)
            if other_methods > 0:
                print(f"      - __init__.py ({other_methods} methods): Core logic")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 tools/analyze_file_structure.py <filepath>")
        print("\nExamples:")
        print("  python3 tools/analyze_file_structure.py panels/panel1.py")
        print("  python3 tools/analyze_file_structure.py panels/panel2.py")
        print("  python3 tools/analyze_file_structure.py core/app_manager.py")
        sys.exit(1)

    analyze_file(sys.argv[1])
