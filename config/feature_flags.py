"""
Minimal feature flag helpers.

Legacy panel toggles have been removed. The remaining flags allow us to
opt-in to optional systems (typed events, extra logging, perf tracking)
via environment variables without touching code.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from utils.logger import get_logger

log = get_logger(__name__)


class FeatureFlags:
    """Lightweight wrapper around env/config-driven booleans."""

    USE_TYPED_EVENTS: bool = None
    ENABLE_MIGRATION_LOGS: bool = None
    ENABLE_PERF_TRACKING: bool = None

    _initialized: bool = False

    @classmethod
    def get_all_flags(cls) -> Dict[str, bool]:
        return {
            "USE_TYPED_EVENTS": cls.USE_TYPED_EVENTS,
            "ENABLE_MIGRATION_LOGS": cls.ENABLE_MIGRATION_LOGS,
            "ENABLE_PERF_TRACKING": cls.ENABLE_PERF_TRACKING,
        }

    @classmethod
    def is_enabled(cls, name: str) -> bool:
        return bool(cls.get_all_flags().get(name, False))

    @classmethod
    def _initialize(cls) -> None:
        if cls._initialized:
            return

        cls.USE_TYPED_EVENTS = cls._get_flag("USE_TYPED_EVENTS", default=False)
        cls.ENABLE_MIGRATION_LOGS = cls._get_flag("ENABLE_MIGRATION_LOGS", default=True)
        cls.ENABLE_PERF_TRACKING = cls._get_flag("ENABLE_PERF_TRACKING", default=True)
        cls._initialized = True

        if cls.ENABLE_MIGRATION_LOGS:
            log.info("Feature flags initialized", flags=cls.get_all_flags())

    @classmethod
    def _get_flag(cls, name: str, default: bool = False) -> bool:
        env_value = os.getenv(name)
        if env_value is not None:
            return cls._parse_bool(env_value)

        config_value = cls._get_from_config(name)
        if config_value is not None:
            return bool(config_value)

        return default

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on", "enabled")
        return bool(value)

    @staticmethod
    def _get_from_config(name: str) -> Optional[bool]:
        try:
            from config.settings import FEATURE_FLAGS

            return FEATURE_FLAGS.get(name)
        except (ImportError, AttributeError):
            return None


FeatureFlags._initialize()


def use_typed_events() -> bool:
    return FeatureFlags.USE_TYPED_EVENTS


def enable_migration_logs() -> bool:
    return FeatureFlags.ENABLE_MIGRATION_LOGS


def enable_perf_tracking() -> bool:
    return FeatureFlags.ENABLE_PERF_TRACKING
