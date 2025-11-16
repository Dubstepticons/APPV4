"""
Convenience script to print which panels are currently active.

Usage:
    python tools/show_panel_status.py

The script reports the module/file each Panel class resolves to so you can
verify the decomposed implementations are wired up.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from panels.panel1 import Panel1  # noqa: E402
from panels.panel2 import Panel2  # noqa: E402


def describe_panel(cls) -> str:
    module = getattr(cls, "__module__", "<unknown>")
    file = getattr(sys.modules.get(module, object()), "__file__", "<unknown>")
    return f"{module} ({file})"


def main() -> int:
    print("=== Panel Implementations ===")
    print(f"Panel1 class module: {describe_panel(Panel1)}")
    print(f"Panel2 class module: {describe_panel(Panel2)}")
    print()
    print("Legacy monoliths have been removed; these paths should always point")
    print("to panels.panel1.panel1_main and panels.panel2.panel2_main.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
