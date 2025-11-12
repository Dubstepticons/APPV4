"""
Modern Message Router - Python 3.10+ Pattern Matching

Demonstrates modern Python patterns for cleaner message routing.
Uses structural pattern matching (PEP 636) introduced in Python 3.10.

Benefits over traditional if/else chains:
- More readable and maintainable
- Type-safe matching on message structure
- Cleaner error handling
- Better IDE support and autocomplete
"""

from __future__ import annotations
from typing import Any, Protocol
from dataclasses import dataclass

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class DTCMessage:
    """
    Structured DTC message representation.

    Using dataclass for automatic __init__, __repr__, and pattern matching.
    """
    type: str
    payload: dict[str, Any]


class MessageHandler(Protocol):
    """Protocol for message handlers (dependency injection)"""

    def handle_balance(self, balance: float, account: str) -> None: ...
    def handle_position(self, symbol: str, qty: int, avg_price: float) -> None: ...
    def handle_order(self, order_data: dict) -> None: ...
    def handle_trade_account(self, account: str) -> None: ...


class ModernMessageRouter:
    """
    Message router using Python 3.10+ pattern matching.

    Demonstrates cleaner, more maintainable message routing vs traditional approach.

    Example:
        >>> router = ModernMessageRouter(handler)
        >>> router.route_message(DTCMessage("BALANCE_UPDATE", {"balance": 10000}))
    """

    def __init__(self, handler: MessageHandler):
        """
        Initialize router.

        Args:
            handler: Object implementing MessageHandler protocol
        """
        self.handler = handler
        self.stats = {
            'total_routed': 0,
            'by_type': {},
            'errors': 0
        }

    def route_message(self, message: DTCMessage) -> bool:
        """
        Route message using structural pattern matching.

        Args:
            message: DTCMessage to route

        Returns:
            True if successfully routed, False otherwise

        Note:
            Uses Python 3.10+ match/case syntax for cleaner routing logic
        """
        self.stats['total_routed'] += 1
        self.stats['by_type'][message.type] = self.stats['by_type'].get(message.type, 0) + 1

        try:
            # Pattern matching on message type and structure
            match message:
                # Balance update with required fields
                case DTCMessage(type="BALANCE_UPDATE",
                               payload={"balance": float(balance), "account": str(account)}):
                    log.debug(f"[Route] Balance update: {balance} for {account}")
                    self.handler.handle_balance(balance, account)
                    return True

                # Position update with symbol and quantity
                case DTCMessage(type="POSITION_UPDATE",
                               payload={"symbol": str(symbol), "qty": int(qty), "avg_entry": float(price)}):
                    log.debug(f"[Route] Position update: {symbol} qty={qty}")
                    self.handler.handle_position(symbol, qty, price)
                    return True

                # Order update (pass entire payload)
                case DTCMessage(type="ORDER_UPDATE", payload=order_data):
                    log.debug(f"[Route] Order update: {order_data.get('Symbol', 'N/A')}")
                    self.handler.handle_order(order_data)
                    return True

                # Trade account enumeration
                case DTCMessage(type="TRADE_ACCOUNT", payload={"account": str(account)}):
                    log.debug(f"[Route] Trade account: {account}")
                    self.handler.handle_trade_account(account)
                    return True

                # Heartbeat (silently ignore)
                case DTCMessage(type="HEARTBEAT", payload=_):
                    return True

                # Unknown message type
                case DTCMessage(type=msg_type, payload=_):
                    log.warning(f"[Route] Unhandled message type: {msg_type}")
                    return False

                # Invalid message structure
                case _:
                    log.error(f"[Route] Invalid message structure: {message}")
                    self.stats['errors'] += 1
                    return False

        except Exception as e:
            log.error(f"[Route] Error routing message: {e}")
            self.stats['errors'] += 1
            return False

    def get_stats(self) -> dict:
        """Get routing statistics"""
        return self.stats.copy()


# Comparison: Traditional vs Modern approach

class TraditionalMessageRouter:
    """
    OLD APPROACH - Nested if/else chains (for comparison)

    This is how message routing looked before pattern matching.
    Notice how it's more verbose and harder to read.
    """

    def __init__(self, handler: MessageHandler):
        self.handler = handler

    def route_message_old_way(self, message: DTCMessage) -> bool:
        """Traditional routing with nested if/else"""

        # Nested if/else chains - harder to read
        if message.type == "BALANCE_UPDATE":
            if "balance" in message.payload and "account" in message.payload:
                balance = message.payload["balance"]
                account = message.payload["account"]
                if isinstance(balance, (int, float)) and isinstance(account, str):
                    self.handler.handle_balance(float(balance), account)
                    return True

        elif message.type == "POSITION_UPDATE":
            payload = message.payload
            if "symbol" in payload and "qty" in payload and "avg_entry" in payload:
                symbol = payload["symbol"]
                qty = payload["qty"]
                price = payload["avg_entry"]
                if isinstance(symbol, str) and isinstance(qty, int):
                    self.handler.handle_position(symbol, qty, float(price))
                    return True

        elif message.type == "ORDER_UPDATE":
            self.handler.handle_order(message.payload)
            return True

        elif message.type == "TRADE_ACCOUNT":
            if "account" in message.payload:
                account = message.payload["account"]
                if isinstance(account, str):
                    self.handler.handle_trade_account(account)
                    return True

        elif message.type == "HEARTBEAT":
            return True

        # If we get here, message wasn't handled
        return False


def demonstrate_pattern_matching():
    """
    Demonstration of pattern matching benefits.

    Run this to see pattern matching in action.
    """

    class DemoHandler:
        """Demo handler for testing"""

        def handle_balance(self, balance: float, account: str):
            print(f"  ✓ Balance: ${balance:,.2f} (account: {account})")

        def handle_position(self, symbol: str, qty: int, avg_price: float):
            print(f"  ✓ Position: {symbol} qty={qty} @ ${avg_price:,.2f}")

        def handle_order(self, order_data: dict):
            print(f"  ✓ Order: {order_data.get('Symbol', 'N/A')}")

        def handle_trade_account(self, account: str):
            print(f"  ✓ Account: {account}")

    # Create router
    handler = DemoHandler()
    router = ModernMessageRouter(handler)

    # Test messages
    print("\n🎯 Pattern Matching Demonstration:\n")

    messages = [
        DTCMessage("BALANCE_UPDATE", {"balance": 10500.50, "account": "SIM1"}),
        DTCMessage("POSITION_UPDATE", {"symbol": "ESH25", "qty": 2, "avg_entry": 5000.0}),
        DTCMessage("ORDER_UPDATE", {"Symbol": "ESH25", "Status": "Filled"}),
        DTCMessage("TRADE_ACCOUNT", {"account": "120005"}),
        DTCMessage("HEARTBEAT", {}),
        DTCMessage("UNKNOWN_TYPE", {"data": "test"}),
    ]

    for msg in messages:
        print(f"Message: {msg.type}")
        result = router.route_message(msg)
        if not result:
            print(f"  ✗ Not handled")
        print()

    # Show stats
    stats = router.get_stats()
    print(f"📊 Statistics:")
    print(f"  Total routed: {stats['total_routed']}")
    print(f"  By type: {stats['by_type']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    demonstrate_pattern_matching()
