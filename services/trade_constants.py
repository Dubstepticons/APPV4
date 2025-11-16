"""
services/trade_constants.py

Centralized trading constants and business rules.
All panels and services should import from this single source.
"""

from __future__ import annotations

import os


# Trading math constants
DOLLARS_PER_POINT = float(os.getenv("APPSIERRA_DOLLARS_PER_POINT", "5.00"))  # MES: $5/pt
COMM_PER_CONTRACT = float(os.getenv("APPSIERRA_COMM_PER_CONTRACT", "0.62"))  # per contract, round-turn approx
