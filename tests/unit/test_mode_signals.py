"""
Unit tests for mode-specific signal namespacing.

Tests mode-filtered signal routing and emission.
"""

import pytest
from utils.signal_bus import SignalBus, ModeNamespace


class TestModeNamespace:
    """Test ModeNamespace class."""

    def test_namespace_creation(self):
        """Test mode namespace initialization."""
        sim_ns = ModeNamespace("SIM")
        assert sim_ns.mode == "SIM"
        assert hasattr(sim_ns, "position")
        assert hasattr(sim_ns, "order")
        assert hasattr(sim_ns, "balance")
        assert hasattr(sim_ns, "trade_account")

    def test_namespace_signal_names(self):
        """Test signal naming in namespaces."""
        sim_ns = ModeNamespace("SIM")
        assert sim_ns.position.name == "sim.position"
        assert sim_ns.order.name == "sim.order"
        assert sim_ns.balance.name == "sim.balance"

        live_ns = ModeNamespace("LIVE")
        assert live_ns.position.name == "live.position"
        assert live_ns.order.name == "live.order"


class TestSignalBus:
    """Test SignalBus with mode namespacing."""

    def test_bus_initialization(self):
        """Test signal bus creates all namespaces."""
        bus = SignalBus()
        assert hasattr(bus, "sim")
        assert hasattr(bus, "live")
        assert hasattr(bus, "debug")
        assert isinstance(bus.sim, ModeNamespace)
        assert isinstance(bus.live, ModeNamespace)
        assert isinstance(bus.debug, ModeNamespace)

    def test_global_signals_exist(self):
        """Test global (non-mode-specific) signals exist."""
        bus = SignalBus()
        assert hasattr(bus, "position")
        assert hasattr(bus, "order")
        assert hasattr(bus, "balance")
        assert hasattr(bus, "trade_account")
        assert hasattr(bus, "handshake_ready")
        assert hasattr(bus, "seed_ready")


class TestModeSignalEmission:
    """Test mode-filtered signal emission."""

    def test_emit_to_global_only(self):
        """Test emission to global signal."""
        bus = SignalBus()
        global_received = []
        sim_received = []

        # Subscribe to both global and SIM-specific
        bus.position.connect(lambda sender, **kwargs: global_received.append(kwargs))
        bus.sim.position.connect(lambda sender, **kwargs: sim_received.append(kwargs))

        # Emit to global only (no mode field)
        bus.emit_all("position", {"symbol": "ESH25", "qty": 2})

        # Only global should receive
        assert len(global_received) == 1
        assert len(sim_received) == 0

    def test_emit_with_sim_mode(self):
        """Test emission with SIM mode routing."""
        bus = SignalBus()
        global_received = []
        sim_received = []
        live_received = []

        # Subscribe to global, SIM, and LIVE
        bus.position.connect(lambda sender, **kwargs: global_received.append(kwargs))
        bus.sim.position.connect(lambda sender, **kwargs: sim_received.append(kwargs))
        bus.live.position.connect(lambda sender, **kwargs: live_received.append(kwargs))

        # Emit with SIM mode
        bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 2})

        # Global and SIM should receive, LIVE should not
        assert len(global_received) == 1
        assert len(sim_received) == 1
        assert len(live_received) == 0
        assert global_received[0]["mode"] == "SIM"
        assert sim_received[0]["mode"] == "SIM"

    def test_emit_with_live_mode(self):
        """Test emission with LIVE mode routing."""
        bus = SignalBus()
        global_received = []
        sim_received = []
        live_received = []

        # Subscribe to global, SIM, and LIVE
        bus.order.connect(lambda sender, **kwargs: global_received.append(kwargs))
        bus.sim.order.connect(lambda sender, **kwargs: sim_received.append(kwargs))
        bus.live.order.connect(lambda sender, **kwargs: live_received.append(kwargs))

        # Emit with LIVE mode
        bus.emit_with_mode("order", {"mode": "LIVE", "Symbol": "ESH25", "OrderStatus": 3})

        # Global and LIVE should receive, SIM should not
        assert len(global_received) == 1
        assert len(sim_received) == 0
        assert len(live_received) == 1
        assert global_received[0]["mode"] == "LIVE"
        assert live_received[0]["mode"] == "LIVE"

    def test_emit_with_debug_mode(self):
        """Test emission with DEBUG mode routing."""
        bus = SignalBus()
        global_received = []
        sim_received = []
        debug_received = []

        # Subscribe to global, SIM, and DEBUG
        bus.balance.connect(lambda sender, **kwargs: global_received.append(kwargs))
        bus.sim.balance.connect(lambda sender, **kwargs: sim_received.append(kwargs))
        bus.debug.balance.connect(lambda sender, **kwargs: debug_received.append(kwargs))

        # Emit with DEBUG mode
        bus.emit_with_mode("balance", {"mode": "DEBUG", "balance": 10000.0})

        # Global and DEBUG should receive, SIM should not
        assert len(global_received) == 1
        assert len(sim_received) == 0
        assert len(debug_received) == 1


class TestMultipleSubscribers:
    """Test multiple subscribers to mode-specific signals."""

    def test_multiple_sim_subscribers(self):
        """Test multiple handlers on SIM namespace."""
        bus = SignalBus()
        handler1_calls = []
        handler2_calls = []

        def handler1(sender, **kwargs):
            handler1_calls.append(kwargs)

        def handler2(sender, **kwargs):
            handler2_calls.append(kwargs)

        # Both subscribe to SIM positions
        bus.sim.position.connect(handler1)
        bus.sim.position.connect(handler2)

        # Emit SIM position
        bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 1})

        # Both should receive
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1

    def test_cross_mode_isolation(self):
        """Test modes don't interfere with each other."""
        bus = SignalBus()
        sim_calls = []
        live_calls = []

        bus.sim.position.connect(lambda sender, **kwargs: sim_calls.append(kwargs))
        bus.live.position.connect(lambda sender, **kwargs: live_calls.append(kwargs))

        # Emit multiple messages
        bus.emit_with_mode("position", {"mode": "SIM", "symbol": "ESH25", "qty": 1})
        bus.emit_with_mode("position", {"mode": "LIVE", "symbol": "NQM24", "qty": 2})
        bus.emit_with_mode("position", {"mode": "SIM", "symbol": "MESZ25", "qty": 3})

        # SIM should have 2, LIVE should have 1
        assert len(sim_calls) == 2
        assert len(live_calls) == 1
        assert sim_calls[0]["symbol"] == "ESH25"
        assert sim_calls[1]["symbol"] == "MESZ25"
        assert live_calls[0]["symbol"] == "NQM24"


class TestBackwardCompatibility:
    """Test backward compatibility with global signals."""

    def test_global_signals_still_work(self):
        """Test global signals work without mode field."""
        bus = SignalBus()
        received = []

        bus.position.connect(lambda sender, **kwargs: received.append(kwargs))

        # Emit without mode field (old behavior)
        bus.position.send({"symbol": "ESH25", "qty": 1})

        assert len(received) == 1
        assert received[0]["symbol"] == "ESH25"

    def test_emit_all_compatibility(self):
        """Test emit_all method still works."""
        bus = SignalBus()
        received = []

        bus.order.connect(lambda sender, **kwargs: received.append(kwargs))

        # Use emit_all (old API)
        bus.emit_all("order", {"OrderStatus": 3})

        assert len(received) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
