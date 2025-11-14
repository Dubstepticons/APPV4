"""
config/feature_flags.py

Feature flags for gradual migration to new architecture.

This module provides a centralized system for toggling between old and new
implementations during the migration period. Feature flags allow for:

- Zero downtime migrations
- Instant rollback if issues arise
- A/B testing of implementations
- Gradual rollout to production
- Environment-specific configurations

Usage:
    from config.feature_flags import FeatureFlags

    # Check if new Panel1 should be used
    if FeatureFlags.USE_NEW_PANEL1:
        from panels.panel1 import Panel1  # New decomposed version
    else:
        from panels.panel1_old import Panel1  # Old monolith

    # Check at runtime
    if FeatureFlags.is_enabled("USE_NEW_PANEL2"):
        # Use new implementation
        pass

Environment Variables:
    USE_NEW_PANEL1=1        - Enable new Panel1 architecture
    USE_NEW_PANEL2=1        - Enable new Panel2 architecture
    USE_TYPED_EVENTS=1      - Enable typed domain events
    ENABLE_MIGRATION_LOGS=1 - Extra logging for migration tracking
    ENABLE_PERF_TRACKING=1  - Performance monitoring

Architecture:
    Priority order for flag values:
    1. Environment variables (highest priority)
    2. Config file (config/settings.py)
    3. Default values (lowest priority)

    This allows:
    - Development: Use config file
    - Staging: Override with env vars
    - Production: Full env var control
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from utils.logger import get_logger

log = get_logger(__name__)


class FeatureFlags:
    """
    Centralized feature flag management.

    All flags are class-level attributes that can be accessed statically.
    Flags are loaded once at import time and cached.

    Flags can be overridden by:
    1. Environment variables (USE_NEW_PANEL1=1)
    2. Config file (FEATURE_FLAGS dict in config/settings.py)
    3. Runtime updates (FeatureFlags.USE_NEW_PANEL1 = True)
    """

    # =========================================================================
    # PANEL MIGRATIONS
    # =========================================================================

    USE_NEW_PANEL1: bool = None  # Set during _initialize()
    """
    Use new decomposed Panel1 architecture (8 modules).

    True:  panels/panel1/* (new decomposed version)
    False: panels/panel1_old.py (old monolith)

    Default: False (use old for safety)
    """

    USE_NEW_PANEL2: bool = None
    """
    Use new decomposed Panel2 architecture (8 modules).

    True:  panels/panel2/* (new decomposed version)
    False: panels/panel2_old.py (old monolith)

    Default: False (use old for safety)
    """

    # =========================================================================
    # EVENT SYSTEM MIGRATIONS
    # =========================================================================

    USE_TYPED_EVENTS: bool = None
    """
    Use typed domain events instead of dict payloads.

    True:  Emit/receive domain.events.* typed events
    False: Emit/receive dict payloads (legacy)

    Default: False (gradual migration)
    """

    # =========================================================================
    # LOGGING & MONITORING
    # =========================================================================

    ENABLE_MIGRATION_LOGS: bool = None
    """
    Enable extra logging for migration tracking.

    True:  Log which implementation is being used
    False: Standard logging only

    Default: True (helpful during migration)
    """

    ENABLE_PERF_TRACKING: bool = None
    """
    Enable performance tracking for new implementations.

    True:  Track startup time, replot time, etc.
    False: No performance tracking

    Default: True (validate no regressions)
    """

    # =========================================================================
    # INTERNAL STATE
    # =========================================================================

    _initialized: bool = False
    _config_cache: Dict[str, Any] = {}

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    @classmethod
    def is_enabled(cls, flag_name: str) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Name of the flag (e.g., "USE_NEW_PANEL1")

        Returns:
            True if enabled, False otherwise

        Example:
            if FeatureFlags.is_enabled("USE_NEW_PANEL1"):
                # Use new Panel1
                pass
        """
        cls._ensure_initialized()

        return getattr(cls, flag_name, False)

    @classmethod
    def get(cls, flag_name: str, default: bool = False) -> bool:
        """
        Get feature flag value with fallback.

        Args:
            flag_name: Name of the flag
            default: Default value if flag doesn't exist

        Returns:
            Flag value or default
        """
        cls._ensure_initialized()

        return getattr(cls, flag_name, default)

    @classmethod
    def set(cls, flag_name: str, value: bool) -> None:
        """
        Set feature flag value at runtime.

        Args:
            flag_name: Name of the flag
            value: New value

        Note:
            This only affects the current process.
            Use environment variables for persistent changes.
        """
        if hasattr(cls, flag_name):
            setattr(cls, flag_name, bool(value))
            log.info(f"Feature flag updated: {flag_name} = {value}")
        else:
            log.warning(f"Unknown feature flag: {flag_name}")

    @classmethod
    def enable_all_new_features(cls) -> None:
        """
        Enable all new features (for testing).

        Useful for:
        - Integration testing
        - Staging environments
        - Development validation
        """
        cls.USE_NEW_PANEL1 = True
        cls.USE_NEW_PANEL2 = True
        cls.USE_TYPED_EVENTS = True

        log.info("All new features ENABLED")
        cls.print_status()

    @classmethod
    def disable_all_new_features(cls) -> None:
        """
        Disable all new features (rollback).

        Useful for:
        - Emergency rollback
        - Regression testing
        - Validation of old code
        """
        cls.USE_NEW_PANEL1 = False
        cls.USE_NEW_PANEL2 = False
        cls.USE_TYPED_EVENTS = False

        log.info("All new features DISABLED (rollback)")
        cls.print_status()

    @classmethod
    def print_status(cls) -> None:
        """
        Print current feature flag status to console.

        Useful for:
        - Startup diagnostics
        - Debugging configuration issues
        - Validation after changes
        """
        cls._ensure_initialized()

        print("")
        print("=" * 70)
        print("FEATURE FLAGS STATUS")
        print("=" * 70)
        print("")
        print("Panel Migrations:")
        print(f"  USE_NEW_PANEL1: {cls.USE_NEW_PANEL1}")
        print(f"  USE_NEW_PANEL2: {cls.USE_NEW_PANEL2}")
        print("")
        print("Event System:")
        print(f"  USE_TYPED_EVENTS: {cls.USE_TYPED_EVENTS}")
        print("")
        print("Monitoring:")
        print(f"  ENABLE_MIGRATION_LOGS: {cls.ENABLE_MIGRATION_LOGS}")
        print(f"  ENABLE_PERF_TRACKING: {cls.ENABLE_PERF_TRACKING}")
        print("")
        print("=" * 70)
        print("")

    @classmethod
    def get_all_flags(cls) -> Dict[str, bool]:
        """
        Get all feature flags as a dictionary.

        Returns:
            Dict mapping flag names to values

        Useful for:
        - Logging
        - Debugging
        - Status reports
        """
        cls._ensure_initialized()

        return {
            "USE_NEW_PANEL1": cls.USE_NEW_PANEL1,
            "USE_NEW_PANEL2": cls.USE_NEW_PANEL2,
            "USE_TYPED_EVENTS": cls.USE_TYPED_EVENTS,
            "ENABLE_MIGRATION_LOGS": cls.ENABLE_MIGRATION_LOGS,
            "ENABLE_PERF_TRACKING": cls.ENABLE_PERF_TRACKING,
        }

    # =========================================================================
    # PRIVATE IMPLEMENTATION
    # =========================================================================

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure flags are initialized (lazy loading)."""
        if not cls._initialized:
            cls._initialize()

    @classmethod
    def _initialize(cls) -> None:
        """
        Initialize all feature flags from environment and config.

        Priority:
        1. Environment variables
        2. Config file
        3. Defaults
        """
        if cls._initialized:
            return

        # Load flags
        cls.USE_NEW_PANEL1 = cls._get_flag("USE_NEW_PANEL1", default=False)
        cls.USE_NEW_PANEL2 = cls._get_flag("USE_NEW_PANEL2", default=False)
        cls.USE_TYPED_EVENTS = cls._get_flag("USE_TYPED_EVENTS", default=False)
        cls.ENABLE_MIGRATION_LOGS = cls._get_flag("ENABLE_MIGRATION_LOGS", default=True)
        cls.ENABLE_PERF_TRACKING = cls._get_flag("ENABLE_PERF_TRACKING", default=True)

        cls._initialized = True

        # Log initialization
        if cls.ENABLE_MIGRATION_LOGS:
            log.info("Feature flags initialized")
            log.debug(f"Flags: {cls.get_all_flags()}")

    @classmethod
    def _get_flag(cls, name: str, default: bool = False) -> bool:
        """
        Get feature flag value with priority order.

        Args:
            name: Flag name
            default: Default value

        Returns:
            Flag value from environment, config, or default
        """
        # Priority 1: Environment variable
        env_value = os.getenv(name)
        if env_value is not None:
            value = cls._parse_bool(env_value)
            if cls.ENABLE_MIGRATION_LOGS:
                log.debug(f"Flag {name} from environment: {value}")
            return value

        # Priority 2: Config file
        config_value = cls._get_from_config(name)
        if config_value is not None:
            value = bool(config_value)
            if cls.ENABLE_MIGRATION_LOGS:
                log.debug(f"Flag {name} from config: {value}")
            return value

        # Priority 3: Default
        if cls.ENABLE_MIGRATION_LOGS:
            log.debug(f"Flag {name} using default: {default}")
        return default

    @classmethod
    def _get_from_config(cls, name: str) -> Optional[bool]:
        """
        Get flag value from config/settings.py.

        Args:
            name: Flag name

        Returns:
            Value from config, or None if not found
        """
        try:
            from config.settings import FEATURE_FLAGS

            if name in FEATURE_FLAGS:
                return FEATURE_FLAGS[name]
        except (ImportError, AttributeError):
            pass

        return None

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """
        Parse string as boolean.

        Args:
            value: String value

        Returns:
            Boolean interpretation

        Truthy: "1", "true", "yes", "on" (case-insensitive)
        Falsy: Everything else
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on", "enabled")

        return bool(value)


# Initialize flags on import
FeatureFlags._initialize()


# Convenience functions for common checks
def use_new_panel1() -> bool:
    """Check if new Panel1 should be used."""
    return FeatureFlags.USE_NEW_PANEL1


def use_new_panel2() -> bool:
    """Check if new Panel2 should be used."""
    return FeatureFlags.USE_NEW_PANEL2


def use_typed_events() -> bool:
    """Check if typed events should be used."""
    return FeatureFlags.USE_TYPED_EVENTS


def enable_migration_logs() -> bool:
    """Check if migration logging is enabled."""
    return FeatureFlags.ENABLE_MIGRATION_LOGS
