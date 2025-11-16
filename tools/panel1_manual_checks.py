"""
Automated aid for the Panel1 manual checklist.

This script instantiates the real Panel1 widget and exercises the
manual-test scenarios (timeframe switching, mode switching, hover label
updates, rapid scope changes). It prints a JSON summary so we can attach
the results to the migration log even when GUI interaction isn't
available.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from panels.panel1 import Panel1  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    panel = Panel1()

    results: dict[str, object] = {"timeframes": [], "modes": [], "hover": {}, "rapid_switch": {}}

    # Timeframe switching
    timeframe_events: list[str] = []

    def on_timeframe(tf: str) -> None:
        timeframe_events.append(tf)

    panel.timeframeChanged.connect(on_timeframe)
    for tf in ["LIVE", "1D", "1W", "1M", "3M", "YTD", "ALL"]:
        panel.set_timeframe(tf)

    results["timeframes"] = timeframe_events

    # Mode switching badge + state verification
    mode_results = []
    for account, mode in zip(["SIM1", "120005", "DEBUG"], ["SIM", "LIVE", "DEBUG"], strict=True):
        panel.set_trading_mode(mode, account)
        mode_results.append(
            {
                "mode": mode,
                "badge": panel.mode_badge.text(),
                "current_account": panel._current_account,  # noqa: SLF001
            }
        )
    results["modes"] = mode_results

    # Hover label updates (directly invoke handlers)
    panel._on_hover_balance_update("$12,345.67")  # noqa: SLF001
    panel._on_hover_pnl_update("+5.25%", "#00FF00")  # noqa: SLF001
    results["hover"] = {"balance_label": panel.lbl_balance.text(), "pnl_label": panel.lbl_pnl.text()}

    # Rapid scope switches to simulate manual stress test
    for idx, mode in enumerate(["SIM", "LIVE", "DEBUG"] * 5):
        panel.set_trading_mode(mode, f"ACC{idx:02d}")
        panel.set_timeframe(["LIVE", "1D", "1W", "1M", "3M", "YTD", "ALL"][idx % 7])

    results["rapid_switch"] = {
        "final_mode": panel._current_mode,  # noqa: SLF001
        "final_account": panel._current_account,  # noqa: SLF001
        "final_timeframe": panel._current_timeframe,  # noqa: SLF001
        "events_recorded": len(timeframe_events),
    }

    panel.close()
    app.quit()

    output_text = json.dumps(results, indent=2)
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "panel1_manual_checks.json").write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
