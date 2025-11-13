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


class ModeNamespace:
    """
    Mode-specific signal namespace (e.g., SIM, LIVE).

    Allows subscribers to listen only to signals for a specific trading mode.

    Usage:
        bus.sim.position.connect(handler)  # Only SIM position updates
        bus.live.order.connect(handler)    # Only LIVE order updates
    """

    def __init__(self, mode: str):
        self.mode = mode
        # Create mode-specific signals
        self.position = Signal(f"{mode.lower()}.position")
        self.order = Signal(f"{mode.lower()}.order")
        self.balance = Signal(f"{mode.lower()}.balance")
        self.trade_account = Signal(f"{mode.lower()}.trade_account")


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

        # ===== MODE-AWARE SIGNALS =====
        # Mode-specific signal namespaces for filtered subscriptions
        self.sim = ModeNamespace("SIM")
        self.live = ModeNamespace("LIVE")
        self.debug = ModeNamespace("DEBUG")

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

    def emit_with_mode(self, signal_name: str, payload: dict):
        """
        Emit to both global signal and mode-specific signal.

        Emits to:
        1. Global signal (e.g., bus.position) - all subscribers
        2. Mode-specific signal (e.g., bus.sim.position) - mode-filtered subscribers

        Args:
            signal_name: Base signal name ("position", "order", "balance", "trade_account")
            payload: Signal payload dict (must include 'mode' field)

        Examples:
            >>> bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 2})
            # Emits to both bus.position and bus.sim.position
        """
        # Emit to global signal
        self.emit_all(signal_name, payload)

        # Emit to mode-specific signal if mode is present
        mode = payload.get("mode")
        if mode:
            mode_ns = None
            if mode == "SIM":
                mode_ns = self.sim
            elif mode == "LIVE":
                mode_ns = self.live
            elif mode == "DEBUG":
                mode_ns = self.debug

            if mode_ns:
                mode_signal = getattr(mode_ns, signal_name, None)
                if mode_signal and isinstance(mode_signal, Signal):
                    mode_signal.send(payload)


# Global singleton bus instance
bus = SignalBus()


# ===== BACKWARD COMPATIBILITY ALIASES =====
# These allow existing code to continue using old import patterns
# TODO: Remove these after all code is migrated to use `bus` directly

signal_trade_account = bus.trade_account
signal_balance = bus.balance
signal_position = bus.position
signal_order = bus.order
