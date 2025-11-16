"""
panels/panel1/state_persistence.py

Persist and restore equity curve history for Panel1.

This mirrors Panel2's state persistence so Panel1 retains its line graph
across restarts.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import structlog

from utils.atomic_persistence import (
    delete_file_safe,
    get_scoped_path,
    load_json_atomic,
    save_json_atomic,
)

log = structlog.get_logger(__name__)


class EquityStatePersistence:
    """Persist equity curve samples per (mode, account) scope."""

    _PLACEHOLDER_ACCOUNT = "default"

    def __init__(self, mode: str, account: str | None):
        self.mode = (mode or "SIM").upper()
        self.account_raw = account or ""
        self.account = self._sanitize_account(self.account_raw) or self._PLACEHOLDER_ACCOUNT

    @staticmethod
    def _sanitize_account(account: str) -> str:
        account = account or ""
        safe = "".join(c if c.isalnum() else "_" for c in account.strip())
        return safe

    def _path(self, account_override: str | None = None) -> Path:
        account = account_override or self.account
        return get_scoped_path("runtime_state_panel1", self.mode, account)

    def load_points(self) -> List[Tuple[float, float]]:
        """Load persisted equity points."""
        data = load_json_atomic(self._path())
        if not data and self.account != self._PLACEHOLDER_ACCOUNT:
            # Fall back to placeholder if present (pre-account data)
            placeholder_data = load_json_atomic(self._path(self._PLACEHOLDER_ACCOUNT))
            if placeholder_data:
                data = placeholder_data
                # Seed main file for future loads and remove placeholder
                save_json_atomic(data, self._path())
                delete_file_safe(self._path(self._PLACEHOLDER_ACCOUNT))

        if not data:
            return []

        return self._extract_points(data)

    def append_point(self, timestamp: float, balance: float) -> bool:
        """Append a new equity sample and save atomically."""
        self._seed_from_placeholder_if_needed()

        path = self._path()
        payload = load_json_atomic(path) or {}
        points = payload.get("points", [])
        points.append({"ts": float(timestamp), "balance": float(balance)})
        payload["points"] = points

        saved = save_json_atomic(payload, path)
        if not saved:
            log.warning(
                "[EquityPersistence] Failed to append point",
                mode=self.mode,
                account=self.account_raw or self._PLACEHOLDER_ACCOUNT,
            )
        return saved

    def clear(self) -> bool:
        """Remove persisted state."""
        return delete_file_safe(self._path())

    def _extract_points(self, data: dict) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        for entry in data.get("points", []):
            try:
                ts = float(entry.get("ts"))
                bal = float(entry.get("balance", entry.get("bal")))
            except (TypeError, ValueError):
                continue
            points.append((ts, bal))

        points.sort(key=lambda p: p[0])
        return points

    def _seed_from_placeholder_if_needed(self) -> None:
        """If placeholder file exists and account changed, migrate data."""
        if not self.account_raw:
            return  # still using placeholder

        placeholder_path = self._path(self._PLACEHOLDER_ACCOUNT)
        target_path = self._path()

        if placeholder_path.exists() and not target_path.exists():
            data = load_json_atomic(placeholder_path)
            if data:
                save_json_atomic(data, target_path)
            delete_file_safe(placeholder_path)
