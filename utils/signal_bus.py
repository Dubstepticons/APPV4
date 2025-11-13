"""
SignalBus - Centralized signal management for APPV4

Provides a clean registry for all application signals with namespacing support.
Replaces scattered module-level signal definitions with a unified API.

Usage:
    from utils.signal_bus import bus

    # Connect to signals
    bus.position.connect(handler)

    # Emit signals
    bus.position.send(payload)

    # Access by category
    bus.dtc.position.send(payload)

Benefits:
- Central registry makes signal topology visible
- Easier to test (can mock entire bus)
- Supports future mode-specific namespacing (bus.sim.position vs bus.live.position)
- Prevents signal coupling issues
"""

from __future__ import annotations

from blinker import Signal


class SignalBus:
    """
    Centralized signal registry for APPV4.

    All application signals are accessed through this bus for consistency.
    """

    def __init__(self):
        # ===== DTC PROTOCOL SIGNALS =====
        # Raw signals from DTC bridge (normalized, not mode-filtered)
        self.trade_account = Signal("trade_account")
        self.balance = Signal("balance")
        self.position = Signal("position")
        self.order = Signal("order")

        # ===== CONNECTION LIFECYCLE SIGNALS =====
        # Session lifecycle events
        self.handshake_ready = Signal("handshake_ready")  # TCP connected + DTC logon successful
        self.seed_ready = Signal("seed_ready")  # Initial data queries completed
        self.connection_lost = Signal("connection_lost")  # DTC disconnected

        # ===== MODE-AWARE SIGNALS (Future Enhancement) =====
        # These will be added when mode partitioning is implemented
        # self.sim = ModeNamespace("SIM")
        # self.live = ModeNamespace("LIVE")

    def emit_all(self, signal_name: str, payload: dict):
        """
        Emit signal by name (convenience method for dynamic dispatch).

        Args:
            signal_name: Name of signal to emit
            payload: Signal payload dict
        """
        sig = getattr(self, signal_name, None)
        if sig and isinstance(sig, Signal):
            sig.send(payload)
        else:
            raise ValueError(f"Unknown signal: {signal_name}")


# Global singleton bus instance
bus = SignalBus()


# ===== BACKWARD COMPATIBILITY ALIASES =====
# These allow existing code to continue using old import patterns
# TODO: Remove these after all code is migrated to use `bus` directly

signal_trade_account = bus.trade_account
signal_balance = bus.balance
signal_position = bus.position
signal_order = bus.order
