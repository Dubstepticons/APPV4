"""
DTC Message Parser and Normalizer

Converts raw DTC protocol messages into normalized AppMessage envelopes.
Extracted from data_bridge.py to separate parsing logic from transport layer.

This module is the canonical parser for all DTC messages - all normalization
logic should live here, not scattered throughout the codebase.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
import structlog

from services.dtc_constants import type_to_name

log = structlog.get_logger(__name__)


# ===== AppMessage Model =====
class AppMessage(BaseModel):
    """
    App-internal normalized message envelope.

    Routed to MessageRouter and emitted via SignalBus.
    All DTC messages are converted to this format for uniform processing.
    """

    type: str = Field(..., description="TRADE_ACCOUNT | BALANCE_UPDATE | POSITION_UPDATE | ORDER_UPDATE")
    payload: dict = Field(default_factory=dict)


# ===== Normalizer Functions =====
def _normalize_trade_account(msg: dict) -> dict:
    """Extract trade account from DTC message."""
    for k in ("TradeAccount", "Account", "account"):
        v = msg.get(k)
        if isinstance(v, str) and v.strip():
            return {"account": v.strip()}
    return {}


def _pick_balance(msg: dict) -> Optional[float]:
    """Extract balance from DTC message (tries multiple field names)."""
    for k in ("BalanceAvailableForNewPositions", "AccountValue", "NetLiquidatingValue", "CashBalance"):
        v = msg.get(k)
        try:
            if v is not None:
                return float(v)
        except Exception:
            continue
    return None


def _normalize_balance(msg: dict) -> dict:
    """
    Normalize balance update from DTC message.

    Returns dict with 'balance' key and preserves other relevant fields.
    """
    bal = _pick_balance(msg)
    out = {"balance": bal} if bal is not None else {}

    # Preserve additional balance-related fields
    for k in ("TradeAccount", "AccountValue", "NetLiquidatingValue", "CashBalance", "AvailableFunds"):
        if k in msg and msg[k] is not None:
            out[k] = msg[k]

    return out


def _normalize_position(msg: dict) -> dict:
    """
    Normalize position update from DTC message.

    Handles multiple field name variants and ensures consistent output format.
    """
    sym = msg.get("Symbol") or msg.get("symbol")
    qty = msg.get("PositionQuantity", msg.get("Quantity", msg.get("qty", 0)))
    avg = msg.get("AveragePrice", msg.get("avg_entry"))

    out = {
        "symbol": sym,
        "qty": int(qty) if isinstance(qty, (int, float)) else 0,
        "avg_entry": float(avg) if isinstance(avg, (int, float, str)) and str(avg) not in ("", "None") else None,
    }

    # Include trade account for mode detection
    if "TradeAccount" in msg and msg["TradeAccount"] is not None:
        out["TradeAccount"] = msg["TradeAccount"]

    # Optional timestamp
    if "DateTime" in msg and msg["DateTime"] is not None:
        out["DateTime"] = msg["DateTime"]

    # Include PnL fields if present
    for k in ("OpenProfitLoss", "UnrealizedProfitLoss", "ClosedProfitLoss"):
        if k in msg and msg[k] is not None:
            out[k] = msg[k]

    return out


def _normalize_order(msg: dict) -> dict:
    """
    Normalize order update from DTC message.

    Extracts key order fields while preserving all relevant metadata.
    """
    keep: dict[str, Any] = {}

    # Standard order fields
    fields = (
        "Symbol",
        "BuySell",
        "OrderStatus",
        "Price1",
        "Price2",
        "FilledQuantity",
        "Quantity",
        "AverageFillPrice",
        "LastFillPrice",
        "ServerOrderID",
        "ClientOrderID",
        "TimeInForce",
        "Text",
        "UpdateReason",
        "OrderType",
        "DateTime",
    )

    for k in fields:
        if k in msg and msg[k] is not None:
            keep[k] = msg[k]

    # Include trade account for mode detection
    if "TradeAccount" in msg and msg["TradeAccount"] is not None:
        keep["TradeAccount"] = msg["TradeAccount"]

    return keep


# ===== Main Parser Function =====
def parse_dtc_message(dtc: dict, *, mode_map: Optional[dict[str, str]] = None) -> Optional[AppMessage]:
    """
    Parse DTC message and convert to normalized AppMessage.

    Args:
        dtc: Raw DTC message dict
        mode_map: Optional mapping of account -> mode (e.g., {"120005": "LIVE", "Sim1": "SIM"})

    Returns:
        AppMessage if message should be routed to app layer, None if control frame

    Example:
        >>> msg = {"Type": 306, "Symbol": "ESH25", "PositionQuantity": 1, "TradeAccount": "120005"}
        >>> mode_map = {"120005": "LIVE"}
        >>> app_msg = parse_dtc_message(msg, mode_map=mode_map)
        >>> app_msg.type
        'POSITION_UPDATE'
        >>> app_msg.payload["mode"]
        'LIVE'
    """
    msg_type = dtc.get("Type")
    name = type_to_name(msg_type)

    # Silently drop control frames (no app event)
    if name in ("Heartbeat", "EncodingResponse", "LogonResponse"):
        return None

    # Route account-related messages
    if name in ("TradeAccountResponse", "TradeAccountsResponse"):
        payload = _normalize_trade_account(dtc)
        _add_mode_if_available(payload, mode_map)
        return AppMessage(type="TRADE_ACCOUNT", payload=payload)

    # Route balance updates (Types 600, 602)
    if name in ("AccountBalanceUpdate", "AccountBalanceResponse"):
        log.debug(f"[DTC] Routing balance message Type={msg_type}, name={name}, payload preview: {str(dtc)[:150]}")
        payload = _normalize_balance(dtc)
        _add_mode_if_available(payload, mode_map)
        return AppMessage(type="BALANCE_UPDATE", payload=payload)

    # Route position updates (Type 306)
    if name == "PositionUpdate":
        # DEBUG: Log ALL incoming PositionUpdate messages
        log.info(f"[DTC] PositionUpdate RAW: {dtc}")
        payload = _normalize_position(dtc)
        _add_mode_if_available(payload, mode_map)
        log.info(f"[DTC] PositionUpdate NORMALIZED: {payload}")
        return AppMessage(type="POSITION_UPDATE", payload=payload)

    # Route order/fill updates (Types 301, 304, 307)
    if name in ("OrderUpdate", "OrderFillResponse", "HistoricalOrderFillResponse"):
        # DEBUG: Log ALL incoming OrderUpdate messages
        log.info(f"[DTC] {name} RAW: {dtc}")
        payload = _normalize_order(dtc)
        _add_mode_if_available(payload, mode_map)
        log.info(f"[DTC] {name} NORMALIZED: {payload}")
        return AppMessage(type="ORDER_UPDATE", payload=payload)

    # DEBUG: Log unhandled message types (helps identify missing handlers)
    try:
        from config.settings import DEBUG_DTC

        # Patch 2: Suppress Type 501 (market data) noise from debug logs
        if DEBUG_DTC and msg_type not in (501,):
            import sys

            print(f"[UNHANDLED-DTC-TYPE] Type {msg_type} ({name}) - no handler", file=sys.stderr, flush=True)
    except Exception:
        pass

    return None


def _add_mode_if_available(payload: dict, mode_map: Optional[dict[str, str]]) -> None:
    """
    Add 'mode' field to payload if account can be mapped to mode.

    Modifies payload in-place.

    Args:
        payload: Normalized payload dict
        mode_map: Mapping of account -> mode
    """
    if not mode_map:
        return

    account = payload.get("TradeAccount") or payload.get("account")
    if account and account in mode_map:
        payload["mode"] = mode_map[account]
