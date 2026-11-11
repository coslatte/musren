"""Run existing CLI commands in an isolated process with cooperative controls."""

import json
import queue
import sys
import threading
from typing import Any, List

EVENT_PREFIX = "MUSREN_EVENT "


def worker_command(arguments: List[str]) -> List[str]:
    """Use the packaged launcher for child jobs when Python is embedded."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--_musren-worker", *arguments]
    return [sys.executable, "-u", "-m", "core.tui.runner", *arguments]


def emit(kind: str, **values: Any) -> None:
    print(EVENT_PREFIX + json.dumps({"kind": kind, **values}), flush=True)


class Controls:
    def __init__(self) -> None:
        self.paused = threading.Event()
        self.cancelled = threading.Event()
        self.answers: queue.Queue = queue.Queue()

    def listen(self) -> None:
        for line in sys.stdin:
            try:
                message = json.loads(line)
                action = message["action"]
            except (ValueError, KeyError, TypeError):
                continue
            if action == "pause":
                self.paused.set()
            elif action == "resume":
                self.paused.clear()
            elif action == "cancel":
                self.cancelled.set()
                self.paused.clear()
            elif action == "answer":
                self.answers.put(bool(message.get("value")))
        self.cancelled.set()
        self.paused.clear()

    def start(self) -> None:
        self.wait_if_paused()

    def stop(self) -> None:
        pass

    def wait_if_paused(self, console: Any = None) -> None:
        while self.paused.is_set():
            if self.cancelled.wait(0.1):
                break
        if self.cancelled.is_set():
            raise SystemExit(130)
        emit("checkpoint")

    def confirm(self, text: str, **kwargs: Any) -> bool:
        emit("confirm", text=text)
        while not self.cancelled.is_set():
            try:
                answer = self.answers.get(timeout=0.1)
                if not answer and kwargs.get("abort"):
                    import typer

                    raise typer.Abort()
                return answer
            except queue.Empty:
                continue
        raise SystemExit(130)


def main() -> None:
    """Install adapters only inside the child, then invoke the existing CLI."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    import typer
    from dotenv import load_dotenv
    from typer.main import get_command
    from rich.progress import Progress
    from rich.text import Text

    from utils import tools
    from utils import dependencies
    from functools import partial

    controls = Controls()
    tools._PAUSE_MANAGER = controls
    dependencies.check_dependencies = partial(
        dependencies.check_dependencies, interactive=False
    )
    typer.confirm = controls.confirm
    original_update = Progress.update

    def report_progress(progress: Progress, task_id: int, **kwargs: Any) -> None:
        controls.wait_if_paused()
        original_update(progress, task_id, **kwargs)
        task = next(task for task in progress.tasks if task.id == task_id)
        emit(
            "progress",
            description=Text.from_markup(task.description).plain,
            completed=task.completed,
            total=task.total,
        )

    Progress.update = report_progress
    threading.Thread(target=controls.listen, daemon=True).start()
    load_dotenv()
    from core.cli.app import app

    try:
        get_command(app).main(args=sys.argv[1:], prog_name="musren")
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
