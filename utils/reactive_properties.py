"""
Reactive Properties with PyQt6 QProperty

Modern reactive programming for PyQt6 widgets.
Properties automatically notify observers when changed.

Benefits:
- Automatic UI updates when data changes
- Less boilerplate code (no manual signal connections)
- Type-safe property bindings
- Clear data flow (model → view)

Example:
    >>> class TradingPanel(QWidget):
    ...     def __init__(self):
    ...         self.balance = ReactiveProperty(0.0)
    ...         self.balance.changed.connect(self.update_ui)
    ...
    ...     def update_balance(self, value):
    ...         self.balance.value = value  # Automatically triggers update_ui()
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Optional
from decimal import Decimal

from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty

from utils.logger import get_logger

log = get_logger(__name__)

T = TypeVar('T')


class ReactiveProperty(QObject, Generic[T]):
    """
    Generic reactive property with automatic change notifications.

    Wraps a value and emits signals when changed.
    Can be bound to UI elements for automatic updates.

    Type Parameters:
        T: Type of value stored (int, float, str, etc.)

    Example:
        >>> balance = ReactiveProperty(10000.0)
        >>> balance.changed.connect(lambda v: print(f"New balance: {v}"))
        >>> balance.value = 10500.0  # Prints: "New balance: 10500.0"
    """

    # Signal emitted when value changes
    changed = pyqtSignal(object)  # new_value

    def __init__(self, initial_value: T, name: str = "property"):
        """
        Initialize reactive property.

        Args:
            initial_value: Starting value
            name: Property name for debugging
        """
        super().__init__()
        self._value: T = initial_value
        self._name = name
        self._change_count = 0

    @property
    def value(self) -> T:
        """Get current value"""
        return self._value

    @value.setter
    def value(self, new_value: T) -> None:
        """
        Set new value and emit change signal.

        Args:
            new_value: New value to set
        """
        # Only emit if value actually changed
        if new_value != self._value:
            old_value = self._value
            self._value = new_value
            self._change_count += 1

            log.debug(f"[ReactiveProperty:{self._name}] {old_value} → {new_value}")

            # Emit change signal
            self.changed.emit(new_value)

    def bind_to(self, callback: Callable[[T], None], emit_initial: bool = True) -> None:
        """
        Bind property to callback function.

        Args:
            callback: Function to call when value changes
            emit_initial: Whether to call callback with current value immediately
        """
        self.changed.connect(callback)

        if emit_initial:
            callback(self._value)

    def get_change_count(self) -> int:
        """Get number of times value has changed"""
        return self._change_count

    def __repr__(self) -> str:
        return f"ReactiveProperty({self._name}={self._value}, changes={self._change_count})"


class TradingModel(QObject):
    """
    Example: Trading data model with reactive properties.

    Demonstrates clean separation between data (model) and UI (view).
    When model properties change, UI automatically updates.

    Usage:
        >>> model = TradingModel()
        >>> model.balance.changed.connect(panel.update_balance_display)
        >>> model.balance.value = 10500.0  # UI updates automatically
    """

    def __init__(self):
        super().__init__()

        # Reactive properties
        self.balance = ReactiveProperty(0.0, "balance")
        self.unrealized_pnl = ReactiveProperty(0.0, "unrealized_pnl")
        self.position_qty = ReactiveProperty(0, "position_qty")
        self.current_mode = ReactiveProperty("SIM", "current_mode")
        self.is_connected = ReactiveProperty(False, "is_connected")

        # Computed property (derives from others)
        self.total_equity = ReactiveProperty(0.0, "total_equity")

        # Auto-update total equity when balance or unrealized_pnl changes
        self.balance.changed.connect(self._update_total_equity)
        self.unrealized_pnl.changed.connect(self._update_total_equity)

    def _update_total_equity(self, _=None):
        """Update total equity (computed property)"""
        self.total_equity.value = self.balance.value + self.unrealized_pnl.value

    def update_from_balance_message(self, balance: float) -> None:
        """
        Update model from DTC balance message.

        All observers automatically notified.

        Args:
            balance: New balance value
        """
        self.balance.value = balance

    def update_from_position_message(self, qty: int, unrealized_pnl: float) -> None:
        """
        Update model from DTC position message.

        Args:
            qty: Position quantity
            unrealized_pnl: Unrealized P&L
        """
        self.position_qty.value = qty
        self.unrealized_pnl.value = unrealized_pnl

    def set_mode(self, mode: str) -> None:
        """
        Switch trading mode.

        Args:
            mode: New mode ("SIM", "LIVE", "DEBUG")
        """
        self.current_mode.value = mode

    def set_connection_status(self, connected: bool) -> None:
        """
        Update connection status.

        Args:
            connected: True if connected to DTC
        """
        self.is_connected.value = connected


# Comparison: Traditional vs Reactive approach

class TraditionalPanel:
    """
    OLD APPROACH - Manual signal connections (for comparison)

    Notice how much boilerplate is needed for simple updates.
    """

    def __init__(self):
        self._balance = 0.0
        self._unrealized_pnl = 0.0
        self._position_qty = 0

        # Must manually track dependencies for computed values
        self._total_equity = 0.0

    def set_balance(self, balance: float):
        """Manual setter with explicit UI update"""
        if balance != self._balance:
            self._balance = balance
            self._update_balance_ui()  # Manual call
            self._update_total_equity()  # Manual call

    def set_unrealized_pnl(self, pnl: float):
        """Another manual setter"""
        if pnl != self._unrealized_pnl:
            self._unrealized_pnl = pnl
            self._update_pnl_ui()  # Manual call
            self._update_total_equity()  # Manual call

    def _update_balance_ui(self):
        """Manual UI update"""
        print(f"  Updating balance UI: ${self._balance:,.2f}")

    def _update_pnl_ui(self):
        """Manual UI update"""
        print(f"  Updating P&L UI: ${self._unrealized_pnl:+,.2f}")

    def _update_total_equity(self):
        """Manual computed value update"""
        self._total_equity = self._balance + self._unrealized_pnl
        print(f"  Updating total equity UI: ${self._total_equity:,.2f}")


class ReactivePanel:
    """
    MODERN APPROACH - Reactive properties

    Much cleaner with automatic updates.
    """

    def __init__(self):
        # Create model with reactive properties
        self.model = TradingModel()

        # Bind properties to UI update methods
        self.model.balance.bind_to(self._update_balance_ui)
        self.model.unrealized_pnl.bind_to(self._update_pnl_ui)
        self.model.total_equity.bind_to(self._update_total_equity_ui)

    def set_balance(self, balance: float):
        """Clean setter - updates happen automatically"""
        self.model.balance.value = balance
        # That's it! UI updates automatically

    def set_unrealized_pnl(self, pnl: float):
        """Clean setter - updates happen automatically"""
        self.model.unrealized_pnl.value = pnl
        # That's it! Total equity recalculates automatically

    def _update_balance_ui(self, balance: float):
        """Callback - called automatically when balance changes"""
        print(f"  Updating balance UI: ${balance:,.2f}")

    def _update_pnl_ui(self, pnl: float):
        """Callback - called automatically when P&L changes"""
        print(f"  Updating P&L UI: ${pnl:+,.2f}")

    def _update_total_equity_ui(self, equity: float):
        """Callback - called automatically when total equity changes"""
        print(f"  Updating total equity UI: ${equity:,.2f}")


def demonstrate_reactive_properties():
    """
    Demonstration comparing traditional vs reactive approaches.

    Run this to see the difference in code clarity and maintainability.
    """
    print("\n" + "="*70)
    print("REACTIVE PROPERTIES DEMONSTRATION")
    print("="*70)

    print("\n❌ Traditional Approach (Manual Updates):\n")
    traditional = TraditionalPanel()
    traditional.set_balance(10000.0)
    traditional.set_unrealized_pnl(250.0)
    print("  → 6 lines of manual update logic needed")

    print("\n✅ Reactive Approach (Automatic Updates):\n")
    reactive = ReactivePanel()
    reactive.set_balance(10000.0)
    reactive.set_unrealized_pnl(250.0)
    print("  → Updates happen automatically via property bindings!")

    print("\n📊 Benefits of Reactive Properties:")
    print("  ✓ Less boilerplate code")
    print("  ✓ Automatic dependency tracking (total equity)")
    print("  ✓ Type-safe with generics")
    print("  ✓ Clear data flow (model → view)")
    print("  ✓ Easier to test (model is pure data)")

    # Show change tracking
    print(f"\n📈 Change Tracking:")
    print(f"  Balance changed: {reactive.model.balance.get_change_count()} times")
    print(f"  Total equity changed: {reactive.model.total_equity.get_change_count()} times (auto-computed!)")


if __name__ == "__main__":
    demonstrate_reactive_properties()
