"""
services/trade_constants.py

Centralized trading constants and business rules.
All panels and services should import from this single source.
"""

from __future__ import annotations

import os


# Trading math constants
# MES (Micro E-mini S&P 500): $5 per point, $0.62 commission per contract
DOLLARS_PER_POINT = float(os.getenv("APPSIERRA_DOLLARS_PER_POINT", "5.00"))
COMM_PER_CONTRACT = float(os.getenv("APPSIERRA_COMM_PER_CONTRACT", "0.62"))

# NOTE: For ES (E-mini S&P 500), use:
# DOLLARS_PER_POINT = 50.0
# COMM_PER_CONTRACT = 2.25
