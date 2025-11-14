#!/usr/bin/env python3
"""Development file watcher for APPSIERRA.

Watches Python files and runs development tasks on change:
    - ruff (lint)
    - pytest (tests)
    - mypy (type checking)
    - optional: restart app (placeholder)
"""

import argparse
from pathlib import Path
import subprocess
import sys
import time

from typing import Optional

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    print("ERROR: watchdog is not installed.")
    print("Install it with: poetry add --group dev watchdog")
    sys.exit(1)


class DevelopmentWatcher(FileSystemEventHandler):
    """File system event handler for development workflow."""

    def __init__(self, mode: str = "lint", debounce_seconds: float = 1.0):
        self.mode = mode
        self.debounce_seconds = debounce_seconds
        self.last_run_time = 0.0
        self.project_root = Path(__file__).parent

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        if not event.src_path.endswith(".py"):
            return

        current_time = time.time()
        if current_time - self.last_run_time < self.debounce_seconds:
            return
        self.last_run_time = current_time

        try:
            rel_path = Path(event.src_path).relative_to(self.project_root)
        except ValueError:
            rel_path = Path(event.src_path)

        print(f"\n{'=' * 70}")
        print(f"[FILE] File changed: {rel_path}")
        print(f"{'=' * 70}\n")

        if self.mode == "lint":
            self.run_lint()
        elif self.mode == "test":
            self.run_tests()
        elif self.mode == "full":
            self.run_full_check()
        elif self.mode == "restart":
            self.restart_app()

    def _run_subprocess(
        self,
        args: list[str],
        timeout: int,
        success_label: str,
        failure_label: str,
    ) -> None:
        try:
            result = subprocess.run(
                args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                print(success_label)
            else:
                print(failure_label)
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
        except subprocess.TimeoutExpired:
            print("Command timed out")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Error running command: {exc}")

    def run_lint(self) -> None:
        print("Running ruff linter...")
        self._run_subprocess(
            ["poetry", "run", "ruff", "check", "."],
            timeout=30,
            success_label="Linting passed.",
            failure_label="Linting issues found:",
        )

    def run_tests(self) -> None:
        print("Running tests...")
        self._run_subprocess(
            ["poetry", "run", "pytest", "-v", "--tb=short"],
            timeout=60,
            success_label="All tests passed.",
            failure_label="Some tests failed:",
        )

    def run_mypy(self) -> None:
        print("Running mypy type checker...")
        self._run_subprocess(
            ["poetry", "run", "mypy", "."],
            timeout=30,
            success_label="Type checking passed.",
            failure_label="Type checking issues found:",
        )

    def run_full_check(self) -> None:
        self.run_lint()
        print()
        self.run_mypy()
        print()
        self.run_tests()

    def restart_app(self) -> None:
        print("App restart mode activated")
        print("Note: actual restart logic depends on your app architecture.")
        print("Consider using a process manager like supervisor or systemd.")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Watch Python files and run development tasks on changes"
    )
    parser.add_argument(
        "--mode",
        choices=["lint", "test", "full", "restart"],
        default="lint",
        help="Watch mode: lint, test, full, restart",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=1.0,
        help="Debounce time in seconds between runs (default: 1.0)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Path to watch (default: current directory)",
    )

    args = parser.parse_args(argv)

    event_handler = DevelopmentWatcher(mode=args.mode, debounce_seconds=args.debounce)
    observer = Observer()

    watch_path = Path(args.path).resolve()
    observer.schedule(event_handler, str(watch_path), recursive=True)

    print(f"Watching for changes in: {watch_path}")
    print(f"Mode: {args.mode}")
    print(f"Debounce: {args.debounce}s")
    print("Press Ctrl+C to stop\n")

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping watcher...")
        observer.stop()
        observer.join()
        print("Watcher stopped")


if __name__ == "__main__":
    main()
