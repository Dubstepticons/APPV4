"""
Trade Mode Detection and Management

Provides canonical mode detection logic (single source of truth).
Used by StateManager, MessageRouter, TradeManager, and panels.
"""

import time
from typing import Optional
from utils.logger import get_logger

log = get_logger(__name__)

# Debounce tracking
_last_mode_switch_time = 0.0
_mode_switch_cooldown = 2.0  # seconds


def detect_mode_from_account(account: str) -> str:
    """
    Detect trading mode from account string.

    CANONICAL MODE DETECTION (single source of truth):
    - Accounts containing "sim", "demo", "test" → SIM
    - Accounts containing "live", "real", or numeric-only (e.g., "120005") → LIVE
    - Everything else → DEBUG

    Args:
        account: Account identifier string

    Returns:
        Mode string: "SIM", "LIVE", or "DEBUG"
    """
    if not account:
        return "DEBUG"

    account_lower = account.lower()

    # SIM mode indicators
    if any(indicator in account_lower for indicator in ["sim", "demo", "test", "paper"]):
        return "SIM"

    # LIVE mode indicators
    if "live" in account_lower or "real" in account_lower:
        return "LIVE"

    # Numeric-only accounts are typically LIVE accounts (e.g., "120005")
    if account.isdigit():
        return "LIVE"

    # Default to DEBUG for unknown account types
    return "DEBUG"


def auto_detect_mode_from_order(payload: dict) -> Optional[str]:
    """
    Detect mode from order payload.

    Args:
        payload: Order message payload from DTC

    Returns:
        Detected mode or None if unable to detect
    """
    # Try to get account from various possible fields
    account = payload.get("TradeAccount") or payload.get("account") or payload.get("Account")

    if account:
        return detect_mode_from_account(account)

    return None


def auto_detect_mode_from_position(payload: dict) -> Optional[str]:
    """
    Detect mode from position payload.

    Args:
        payload: Position message payload from DTC

    Returns:
        Detected mode or None if unable to detect
    """
    # Try to get account from various possible fields
    account = payload.get("TradeAccount") or payload.get("account") or payload.get("Account")

    if account:
        return detect_mode_from_account(account)

    return None


def should_switch_mode_debounced(new_mode: str, current_mode: str) -> bool:
    """
    Determine if mode switch should occur, with debouncing to prevent rapid switches.

    Args:
        new_mode: Proposed new mode
        current_mode: Current active mode

    Returns:
        True if mode switch should proceed, False if debounced
    """
    global _last_mode_switch_time

    # No switch needed if modes are the same
    if new_mode == current_mode:
        return False

    current_time = time.time()
    time_since_last_switch = current_time - _last_mode_switch_time

    # Debounce: prevent switches within cooldown period
    if time_since_last_switch < _mode_switch_cooldown:
        log.debug(
            f"Mode switch debounced: {current_mode}->{new_mode} "
            f"(cooldown: {_mode_switch_cooldown - time_since_last_switch:.1f}s remaining)"
        )
        return False

    # Allow switch and update timestamp
    _last_mode_switch_time = current_time
    return True


def log_mode_switch(source: str, old_mode: str, new_mode: str, account: Optional[str] = None) -> None:
    """
    Log a mode switch event with consistent formatting.

    Args:
        source: Source component triggering the switch (e.g., "StateManager", "MessageRouter")
        old_mode: Previous mode
        new_mode: New mode
        account: Optional account identifier
    """
    account_info = f" (account: {account})" if account else ""
    log.info(f"[Mode] {source}: {old_mode} -> {new_mode}{account_info}")


def reset_mode_switch_debounce() -> None:
    """
    Reset the debounce timer. Useful for testing or forced mode switches.
    """
    global _last_mode_switch_time
    _last_mode_switch_time = 0.0
