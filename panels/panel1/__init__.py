"""
panels/panel1/__init__.py

Panel1 - Balance & Equity with modular architecture.

TEMPORARY BRIDGE: Re-exports from monolithic source while full extraction is in progress.
Maintains functionality during Phase 7 modularization.

Full modular extraction pending (6-8 hour task - deferred to future session).
"""

# Import Panel1 from monolithic source file
import sys
from pathlib import Path

# Ensure panels directory is in path
panels_dir = Path(__file__).parent.parent
if str(panels_dir) not in sys.path:
    sys.path.insert(0, str(panels_dir))

# Import from monolithic source (renamed from panel1.py -> panel1_monolithic_source.py)
from panel1_monolithic_source import Panel1

# Re-export for clean import interface
__all__ = ['Panel1']
