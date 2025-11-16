"""
Panel1 integration tests.

These tests validate that the decomposed Panel1 orchestrator wires the
state manager, chart, and public API together in ways expected by the
migration guide.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_set_trading_mode_updates_scope_and_badge(mock_panel1):
    """Panel1 should relay trading mode/account to the equity state manager."""
    panel = mock_panel1
    equity_state = panel._equity_state

    original_set_scope = equity_state.set_scope
    equity_state.set_scope = MagicMock(side_effect=original_set_scope)
    equity_state.get_equity_curve = MagicMock(return_value=[(0.0, 10000.0), (1.0, 10100.0)])

    panel.set_trading_mode("LIVE", "120005")

    equity_state.set_scope.assert_called_once_with("LIVE", "120005")
    assert panel.mode_badge.text() == "LIVE"


def test_timeframe_change_emits_signal(mock_panel1):
    """Changing timeframe should emit the signal so pills/observers update."""
    panel = mock_panel1
    emitted = []
    panel.timeframeChanged.connect(lambda tf: emitted.append(tf))

    panel.set_timeframe("1D")

    assert emitted == ["1D"]


def test_update_equity_series_adds_point_and_refreshes(mock_panel1):
    """Balance updates should call into equity state and refresh the chart."""
    panel = mock_panel1
    equity_state = panel._equity_state

    equity_state.add_balance_point = MagicMock()
    equity_state.get_active_curve = MagicMock(return_value=[(1.0, 10000.0), (2.0, 10150.0)])
    panel._equity_chart.replot = MagicMock()
    if panel._hover_handler:
        panel._hover_handler.set_data = MagicMock()

    panel.update_equity_series_from_balance(10200.0, mode="SIM")

    equity_state.add_balance_point.assert_called_once()
    panel._equity_chart.replot.assert_called_once()


def test_set_account_balance_formats_label(mock_panel1):
    """Account balance label should display currency-formatted text."""
    panel = mock_panel1
    panel.set_account_balance(54321.12)
    assert panel.lbl_balance.text() == "$54,321.12"
