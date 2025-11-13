"""
State Manager Module

Handles state persistence and mode management for Panel2 (Trading panel).
Extracted from panels/panel2.py for modularity.

Functions:
- get_state_path(): Get scoped state file path
- load_state(): Load session state from JSON
- save_state(): Save session state to JSON
- set_trading_mode(): Switch trading mode with state preservation

State Format:
{
    "entry_time_epoch": float,
    "heat_start_epoch": float,
    "trade_min_price": float,
    "trade_max_price": float,
    "mode": str,
    "account": str
}
"""

from typing import Optional
from utils.logger import get_logger

log = get_logger(__name__)


def get_state_path(panel) -> str:
    """
    Get scoped state file path for current (mode, account).

    Args:
        panel: Panel2 instance

    Returns:
        Path to state file: data/runtime_state_panel2_{mode}_{account}.json
    """
    from utils.atomic_persistence import get_scoped_path
    path = get_scoped_path("runtime_state_panel2", panel.current_mode, panel.current_account)
    return str(path)


def load_state(panel) -> None:
    """
    Load session state from scoped state file.

    Uses atomic_persistence for safe loading. Restores:
    - entry_time_epoch
    - heat_start_epoch
    - trade_min_price
    - trade_max_price

    Args:
        panel: Panel2 instance
    """
    try:
        from utils.atomic_persistence import load_json_atomic

        state_path = get_state_path(panel)
        data = load_json_atomic(state_path)

        if data:
            panel.entry_time_epoch = data.get("entry_time_epoch")
            panel.heat_start_epoch = data.get("heat_start_epoch")
            panel._trade_min_price = data.get("trade_min_price")
            panel._trade_max_price = data.get("trade_max_price")
            log.info(f"[Panel2] Restored session timers from {state_path}")
        else:
            log.debug(f"[Panel2] No persisted state found for {panel.current_mode}/{panel.current_account}")
    except Exception as e:
        log.warning(f"[Panel2] Failed to load persisted state: {e}")


def save_state(panel) -> None:
    """
    Save session state to scoped state file.

    Uses atomic_persistence for safe writes. Saves:
    - entry_time_epoch
    - heat_start_epoch
    - trade_min_price
    - trade_max_price
    - mode
    - account

    Args:
        panel: Panel2 instance
    """
    try:
        from pathlib import Path
        from utils.atomic_persistence import save_json_atomic

        state_path = Path(get_state_path(panel))

        data = {
            "entry_time_epoch": panel.entry_time_epoch,
            "heat_start_epoch": panel.heat_start_epoch,
            "trade_min_price": panel._trade_min_price,
            "trade_max_price": panel._trade_max_price,
            "mode": panel.current_mode,
            "account": panel.current_account,
        }

        success = save_json_atomic(data, state_path)
        if success:
            log.debug(f"[Panel2] Saved session state for {panel.current_mode}/{panel.current_account}")
    except Exception as e:
        log.error(f"[Panel2] Persist write failed: {e}")


def set_trading_mode(panel, mode: str, account: Optional[str] = None) -> None:
    """
    Update trading mode for this panel.

    CRITICAL: This implements the ModeChanged contract:
    1. Freeze current state (save to current scope)
    2. Swap to new (mode, account) scope
    3. Reload session state from new scope
    4. Single repaint

    Args:
        panel: Panel2 instance
        mode: Trading mode ("SIM", "LIVE", "DEBUG")
        account: Account identifier (optional, defaults to empty string)
    """
    mode = mode.upper()
    if mode not in ("DEBUG", "SIM", "LIVE"):
        log.warning(f"[Panel2] Invalid trading mode: {mode}")
        return

    # Use empty string if account not provided
    if account is None:
        account = ""

    # Check if mode/account actually changed
    if mode == panel.current_mode and account == panel.current_account:
        log.debug(f"[Panel2] Mode/account unchanged: {mode}, {account}")
        return

    old_scope = (panel.current_mode, panel.current_account)
    new_scope = (mode, account)
    log.info(f"[Panel2] Mode change: {old_scope} -> {new_scope}")

    # 1. Freeze: Save current state to old scope
    save_state(panel)

    # 2. Swap: Update active scope
    panel.current_mode = mode
    panel.current_account = account

    # 3. Reload: Load state from new scope
    load_state(panel)

    # 4. Single repaint: Refresh all cells
    from panels.panel2 import metrics_updater
    metrics_updater.refresh_all_cells(panel)
    metrics_updater.update_live_banner(panel)

    log.info(f"[Panel2] Switched to {mode}/{account}")
