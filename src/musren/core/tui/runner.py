"""Run existing CLI commands in an isolated process with cooperative controls."""

import sys
from pathlib import Path
from typing import List

from musren.core.tui.command_adapter import EVENT_PREFIX, run_cli_command

__all__ = ["EVENT_PREFIX", "worker_command"]


def worker_command(arguments: List[str]) -> List[str]:
    """Use the packaged launcher for child jobs when Python is embedded."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--_musren-worker", *arguments]
    root = Path(__file__).resolve().parents[4]
    return [sys.executable, "-u", str(root / "app.py"), "--_musren-worker", *arguments]


def main() -> None:
    """Dispatch the TUI's isolated CLI worker adapter."""
    run_cli_command()


if __name__ == "__main__":
    main()
