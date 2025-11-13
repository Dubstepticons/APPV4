"""
Trading Mode Detection and Management Utilities

Provides centralized mode detection logic for APPSIERRA trading system.
Detects trading mode (DEBUG/SIM/LIVE) from various sources:
- Account names (e.g., "Sim1" → SIM, "120005" → LIVE)
- DTC message fields
- Configuration settings

This module consolidates mode detection logic that was previously scattered
across multiple files, providing a single source of truth for mode determination.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import structlog
    log = structlog.get_logger(__name__)
    HAS_STRUCTLOG = True
except ImportError:
    # Fallback to simple logging if structlog not available
    HAS_STRUCTLOG = False

    class SimpleLogger:
        """Simple logger fallback when structlog unavailable"""
        def debug(self, msg, **kwargs):
            pass  # Silent in production
        def info(self, msg, **kwargs):
            print(f"[INFO] {msg}", kwargs if kwargs else "")
        def warning(self, msg, **kwargs):
            print(f"[WARNING] {msg}", kwargs if kwargs else "")
        def error(self, msg, **kwargs):
            print(f"[ERROR] {msg}", kwargs if kwargs else "")

    log = SimpleLogger()


# ============================================================================
# CORE MODE DETECTION
# ============================================================================

def detect_mode_from_account(account: str) -> str:
    """
    Detect trading mode from account identifier.

    This is the canonical mode detection function used throughout the system.

    Detection rules:
    - Account starting with "Sim" (case-insensitive) → SIM
    - Account that is all digits → LIVE
    - Everything else → DEBUG

    Args:
        account: Account identifier string (e.g., "Sim1", "120005", "TestAccount")

    Returns:
        Mode string: "SIM", "LIVE", or "DEBUG"

    Examples:
        >>> detect_mode_from_account("Sim1")
        'SIM'
        >>> detect_mode_from_account("Sim2")
        'SIM'
        >>> detect_mode_from_account("120005")
        'LIVE'
        >>> detect_mode_from_account("TestAccount")
        'DEBUG'
        >>> detect_mode_from_account("")
        'DEBUG'
    """
    if not account:
        return "DEBUG"

    account = account.strip()

    # Check for SIM account (case-insensitive)
    if account.lower().startswith("sim"):
        return "SIM"

    # Check for LIVE account (all digits)
    if account.isdigit():
        return "LIVE"

    # Everything else is DEBUG
    return "DEBUG"


def auto_detect_mode_from_order(order_msg: Dict[str, Any]) -> Optional[str]:
    """
    Detect trading mode from DTC ORDER_UPDATE message (Type 301).

    Extracts TradeAccount field and uses detect_mode_from_account().

    Args:
        order_msg: DTC ORDER_UPDATE message dictionary

    Returns:
        Mode string ("SIM", "LIVE", "DEBUG") or None if account not found

    Examples:
        >>> auto_detect_mode_from_order({"TradeAccount": "Sim1", "Type": 301})
        'SIM'
        >>> auto_detect_mode_from_order({"Type": 301})
        None
    """
    account = order_msg.get("TradeAccount")
    if not account:
        return None
    return detect_mode_from_account(account)


def auto_detect_mode_from_position(position_msg: Dict[str, Any]) -> Optional[str]:
    """
    Detect trading mode from DTC POSITION_UPDATE message (Type 306).

    Extracts TradeAccount field and uses detect_mode_from_account().

    Args:
        position_msg: DTC POSITION_UPDATE message dictionary

    Returns:
        Mode string ("SIM", "LIVE", "DEBUG") or None if account not found

    Examples:
        >>> auto_detect_mode_from_position({"TradeAccount": "120005", "Type": 306})
        'LIVE'
        >>> auto_detect_mode_from_position({"Type": 306})
        None
    """
    account = position_msg.get("TradeAccount")
    if not account:
        return None
    return detect_mode_from_account(account)


# ============================================================================
# MODE COMPARISON & VALIDATION
# ============================================================================

def is_sim_mode(mode: str) -> bool:
    """
    Check if mode is SIM.

    Args:
        mode: Mode string to check

    Returns:
        True if mode is "SIM" (case-insensitive), False otherwise
    """
    return mode.upper() == "SIM"


def is_live_mode(mode: str) -> bool:
    """
    Check if mode is LIVE.

    Args:
        mode: Mode string to check

    Returns:
        True if mode is "LIVE" (case-insensitive), False otherwise
    """
    return mode.upper() == "LIVE"


def is_debug_mode(mode: str) -> bool:
    """
    Check if mode is DEBUG.

    Args:
        mode: Mode string to check

    Returns:
        True if mode is "DEBUG" (case-insensitive), False otherwise
    """
    return mode.upper() == "DEBUG"


def modes_match(mode1: str, mode2: str) -> bool:
    """
    Check if two modes are equivalent (case-insensitive comparison).

    Args:
        mode1: First mode string
        mode2: Second mode string

    Returns:
        True if modes match, False otherwise
    """
    return mode1.upper() == mode2.upper()


# ============================================================================
# DEBOUNCED MODE SWITCHING
# ============================================================================

# Global state for debouncing
_last_mode_switch_time: float = 0.0
_last_mode_switch_from: Optional[str] = None
_last_mode_switch_to: Optional[str] = None
_mode_switch_debounce_seconds: float = 2.0  # 2-second cooldown


def should_switch_mode_debounced(
    current_mode: str,
    new_mode: str,
    debounce_seconds: Optional[float] = None
) -> bool:
    """
    Check if mode switch should proceed, with debouncing to prevent rapid toggling.

    Prevents mode switches within debounce window (default 2 seconds) unless
    it's the same switch being attempted again.

    Args:
        current_mode: Current trading mode
        new_mode: Proposed new trading mode
        debounce_seconds: Custom debounce period (overrides default 2.0s)

    Returns:
        True if mode switch should proceed, False if it should be debounced

    Examples:
        >>> should_switch_mode_debounced("SIM", "LIVE")
        True
        >>> # Immediately after:
        >>> should_switch_mode_debounced("LIVE", "DEBUG")
        False  # Too soon, debounced
    """
    global _last_mode_switch_time, _last_mode_switch_from, _last_mode_switch_to

    # If modes are the same, no switch needed
    if modes_match(current_mode, new_mode):
        return False

    debounce = debounce_seconds if debounce_seconds is not None else _mode_switch_debounce_seconds
    current_time = time.time()
    time_since_last_switch = current_time - _last_mode_switch_time

    # Check if this is the same switch being attempted again
    same_switch = (
        _last_mode_switch_from == current_mode and
        _last_mode_switch_to == new_mode
    )

    # Allow switch if:
    # 1. First switch ever (_last_mode_switch_time == 0)
    # 2. Enough time has passed
    # 3. Same switch being reattempted (idempotent)
    if _last_mode_switch_time == 0 or time_since_last_switch >= debounce or same_switch:
        # Update debounce state
        _last_mode_switch_time = current_time
        _last_mode_switch_from = current_mode
        _last_mode_switch_to = new_mode
        return True

    # Debounced
    log.debug(
        "mode_switch_debounced",
        current_mode=current_mode,
        new_mode=new_mode,
        time_since_last=f"{time_since_last_switch:.2f}s",
        debounce_window=f"{debounce}s",
    )
    return False


def reset_mode_switch_debounce() -> None:
    """
    Reset the mode switch debounce timer.

    Useful for testing or when you want to allow immediate mode switches
    (e.g., after app restart or manual override).
    """
    global _last_mode_switch_time, _last_mode_switch_from, _last_mode_switch_to
    _last_mode_switch_time = 0.0
    _last_mode_switch_from = None
    _last_mode_switch_to = None


# ============================================================================
# LOGGING & DIAGNOSTICS
# ============================================================================

def log_mode_switch(
    previous_mode: str,
    new_mode: str,
    account: str,
    reason: str = "unknown",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a mode switch event with structured context.

    Creates a structured log entry for mode changes, including timestamp,
    modes, account, and optional metadata for debugging.

    Args:
        previous_mode: Mode before switch
        new_mode: Mode after switch
        account: Trading account identifier
        reason: Reason for switch (e.g., "dtc_message", "user_action", "mode_drift")
        metadata: Optional additional context to include in log

    Examples:
        >>> log_mode_switch("SIM", "LIVE", "120005", "dtc_message",
        ...                 {"message_type": 301, "symbol": "MESZ24"})
    """
    log_data = {
        "event": "mode_switch",
        "previous_mode": previous_mode,
        "new_mode": new_mode,
        "account": account,
        "reason": reason,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    if metadata:
        log_data["metadata"] = metadata

    log.info("MODE_SWITCH", **log_data)


def log_mode_drift(
    expected_mode: str,
    expected_account: str,
    incoming_mode: str,
    incoming_account: str,
    message_type: Optional[int] = None
) -> None:
    """
    Log a mode drift detection event.

    Mode drift occurs when incoming DTC messages don't match the current
    active mode/account, which could indicate user switched accounts in
    Sierra Chart or configuration mismatch.

    Args:
        expected_mode: Currently active mode
        expected_account: Currently active account
        incoming_mode: Mode detected from incoming message
        incoming_account: Account from incoming message
        message_type: Optional DTC message type (301, 306, etc.)

    Examples:
        >>> log_mode_drift("SIM", "Sim1", "LIVE", "120005", 301)
    """
    log.warning(
        "MODE_DRIFT_DETECTED",
        expected_mode=expected_mode,
        expected_account=expected_account,
        incoming_mode=incoming_mode,
        incoming_account=incoming_account,
        message_type=message_type,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        safety_action="Consider disarming LIVE trading if drift persists",
    )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_mode_display_name(mode: str) -> str:
    """
    Get human-readable display name for mode.

    Args:
        mode: Mode string

    Returns:
        Display name for UI

    Examples:
        >>> get_mode_display_name("SIM")
        'Simulation'
        >>> get_mode_display_name("LIVE")
        'Live Trading'
        >>> get_mode_display_name("DEBUG")
        'Debug/Development'
    """
    mode_upper = mode.upper()
    display_names = {
        "SIM": "Simulation",
        "LIVE": "Live Trading",
        "DEBUG": "Debug/Development",
    }
    return display_names.get(mode_upper, mode)


def validate_mode(mode: str) -> bool:
    """
    Validate that mode is one of the recognized values.

    Args:
        mode: Mode string to validate

    Returns:
        True if mode is valid ("SIM", "LIVE", or "DEBUG"), False otherwise
    """
    return mode.upper() in {"SIM", "LIVE", "DEBUG"}


# ============================================================================
# TESTING & DIAGNOSTICS
# ============================================================================

if __name__ == "__main__":
    # Self-test examples
    print("=" * 60)
    print("APPSIERRA Trade Mode Detection - Self Test")
    print("=" * 60)
    print()

    # Test account detection
    test_accounts = [
        ("Sim1", "SIM"),
        ("Sim2", "SIM"),
        ("SIM", "SIM"),
        ("sim", "SIM"),
        ("120005", "LIVE"),
        ("999999", "LIVE"),
        ("TestAccount", "DEBUG"),
        ("", "DEBUG"),
    ]

    print("Account Detection Tests:")
    print("-" * 40)
    for account, expected in test_accounts:
        result = detect_mode_from_account(account)
        status = "✓" if result == expected else "✗"
        print(f"{status} Account: '{account}' → {result} (expected: {expected})")

    print()
    print("Mode Comparison Tests:")
    print("-" * 40)
    print(f"✓ is_sim_mode('SIM'): {is_sim_mode('SIM')}")
    print(f"✓ is_live_mode('LIVE'): {is_live_mode('LIVE')}")
    print(f"✓ is_debug_mode('DEBUG'): {is_debug_mode('DEBUG')}")
    print(f"✓ modes_match('SIM', 'sim'): {modes_match('SIM', 'sim')}")

    print()
    print("Display Names:")
    print("-" * 40)
    for mode in ["SIM", "LIVE", "DEBUG"]:
        print(f"  {mode} → {get_mode_display_name(mode)}")

    print()
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
