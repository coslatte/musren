"""Forms and job lifecycle for the optional musren terminal interface."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.containers import Grid, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from core.cli.config import ConfigManager, VALID_KEYS
from core.tui.jobs import Job, OPERATIONS
from core.tui.runner import EVENT_PREFIX
from utils.tools import get_audio_files


class Confirmation(ModalScreen[bool]):
    BINDINGS = [("escape", "decline", "Cancel")]

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="dialog"):
            yield Static(self.text, markup=False)
            with Grid(classes="buttons"):
                yield Button("Confirm", id="confirm", variant="warning")
                yield Button("Cancel", id="decline")

    def on_mount(self) -> None:
        self.query_one("#decline", Button).focus()

    @on(Button.Pressed)
    def answer(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_decline(self) -> None:
        self.dismiss(False)


class MusrenApp(App[None]):
    TITLE = "musren"
    SUB_TITLE = "Music library tools"
    CSS = """
    Screen { background: $surface; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; }
    #workspace { height: 1fr; layout: horizontal; }
    #form { width: 42; height: 1fr; padding-right: 2; }
    #browser { width: 1fr; height: 1fr; }
    #browser TabPane { padding: 0; }
    #tree, #files { height: 1fr; }
    Label { margin-top: 1; color: $text-muted; }
    Input, Select { margin-bottom: 0; }
    Checkbox { margin-top: 1; }
    .buttons { layout: grid; grid-size: 2; grid-rows: 3; grid-gutter: 1;
               height: 7; margin-top: 1; }
    Button { width: 1fr; min-width: 10; }
    #job-controls { grid-size: 4; grid-rows: 3; grid-gutter: 0 1;
                    height: 3; margin: 0 2; }
    #log { height: 1fr; border: round $primary; }
    #busy { height: 1; display: none; }
    #status { height: auto; max-height: 3; padding: 0 2; color: $text-muted; }
    #keys { height: 8; margin-top: 1; }
    #config-form { max-width: 76; }
    Confirmation { align: center middle; background: $background 70%; }
    #dialog { width: 65; max-width: 90%; height: auto; max-height: 90%; padding: 1 2;
              border: round $warning; background: $surface; }
    #dialog .buttons { height: 3; }
    #help { padding: 1; }
    .narrow #workspace { layout: vertical; }
    .narrow #form { width: 1fr; height: auto; padding-right: 0; }
    .narrow #browser { width: 1fr; height: 18; margin-top: 1; }
    .small #job-controls { grid-size: 2; height: 6; }
    .small TabPane { padding: 0 1; }
    .small #job-controls { margin: 0 1; }
    .small Footer { display: none; }
    .short TabPane { padding-top: 0; padding-bottom: 0; }
    """
    BINDINGS = [
        ("ctrl+q", "request_quit", "Quit"),
        ("ctrl+r", "preview", "Preview"),
        ("ctrl+p", "pause", "Pause / resume"),
        ("ctrl+x", "cancel_job", "Cancel job"),
        ("f1", "help", "Help"),
    ]

    def __init__(self, config: Optional[ConfigManager] = None) -> None:
        super().__init__()
        self.config = config or ConfigManager()
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running_job = False
        self.paused = False
        self.cancelling = False
        self.quit_after_job = False

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Library", id="library"):
                with VerticalScroll(id="workspace"):
                    with VerticalScroll(id="form"):
                        yield Label("Music directory")
                        yield Input(str(Path.cwd()), id="directory")
                        yield Label("Operation")
                        yield Select(
                            [(v, k) for k, v in OPERATIONS.items()],
                            value="rename",
                            allow_blank=False,
                            id="operation",
                        )
                        yield Checkbox(
                            "Include subdirectories",
                            value=bool(self.config.get_setting("recursive", False)),
                            id="recursive",
                        )
                        yield Label("Rename format", id="format-label")
                        yield Select(
                            [
                                ("Artist - Title", "1"),
                                ("Title", "2"),
                                ("Track - Artist - Title", "3"),
                            ],
                            value="1",
                            allow_blank=False,
                            id="format",
                        )
                        yield Checkbox("Recognize before lyrics", id="recognition")
                        yield Checkbox("Also fetch covers with lyrics", id="covers")
                        yield Checkbox("Use Shazam", id="shazam")
                    with VerticalScroll(id="browser"):
                        with TabbedContent(id="browser-tabs"):
                            with TabPane("Folders", id="folders-pane"):
                                yield DirectoryTree(Path.cwd(), id="tree")
                            with TabPane("Files in scope", id="files-pane"):
                                yield DataTable(id="files")
            with TabPane("Output", id="output-pane"):
                yield RichLog(id="log", wrap=True, markup=False, max_lines=5000)
            with TabPane("Configuration", id="configuration"):
                with VerticalScroll(id="config-form"):
                    yield Label("API credential")
                    yield Select(
                        [(k, k) for k in VALID_KEYS],
                        value="acoustid",
                        allow_blank=False,
                        id="key",
                    )
                    yield Input(
                        placeholder="Credential value", password=True, id="secret"
                    )
                    with Grid(classes="buttons"):
                        yield Button("Save key", id="save-key", variant="primary")
                        yield Button("Load key", id="load-key")
                        yield Button("Delete key", id="delete-key")
                        yield Button("Clear all", id="clear-config")
                    yield DataTable(id="keys")
                    yield Checkbox(
                        "Default recursive scan",
                        value=bool(self.config.get_setting("recursive", False)),
                        id="default-recursive",
                    )
                    yield Checkbox(
                        "Light theme",
                        value=self.config.get_setting("theme", "dark") == "light",
                        id="light-theme",
                    )
                    yield Static(
                        "Credentials are masked here. They are stored as plain text in your local config file.",
                        markup=False,
                    )
            with TabPane("Help", id="help-pane"):
                with VerticalScroll():
                    yield Static(
                        "Choose a folder and operation, then Preview and Run. Run asks before modifying files.\n\n"
                        "Rename supports all three formats and asks whether to keep or revert changes. "
                        "Lyrics can recognize first and fetch artwork. Recognition supports AcoustID and Shazam. "
                        "Albums groups tracks into folders; Revert flattens audio files back to the chosen folder.\n\n"
                        "Pause and cancellation take effect at the next processing checkpoint. "
                        "An in-flight file or network request can finish first. Completed changes remain after cancellation. "
                        "Quit during a job requests cancellation and waits for that checkpoint.\n\n"
                        "AcoustID needs an API key and fpcalc. Optional dependencies are checked by each command. "
                        "The output pane includes per-file errors and summaries; review it after every job.\n\n"
                        "CLI: musren rename --directory PATH, musren --help. Legacy menu: musren with no arguments.\n"
                        "Tab / Shift+Tab moves focus; Enter activates; F1 opens help; Ctrl+Q quits.",
                        id="help",
                        markup=False,
                    )
        yield LoadingIndicator(id="busy")
        yield Static(
            "Choose a folder and operation. Preview files before running.",
            id="status",
            markup=False,
        )
        with Grid(id="job-controls"):
            yield Button("Preview", id="preview")
            yield Button("Run", id="run", variant="primary")
            yield Button("Pause", id="pause", disabled=True)
            yield Button("Cancel job", id="cancel-job", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#files", DataTable).add_columns("File", "Folder")
        self.query_one("#keys", DataTable).add_columns("Credential", "Status")
        self.theme = (
            "textual-light"
            if self.config.get_setting("theme", "dark") == "light"
            else "textual-dark"
        )
        self.refresh_keys()
        self.update_options()
        self.adapt_layout(self.size.width, self.size.height)

    def on_resize(self, event: events.Resize) -> None:
        self.adapt_layout(event.size.width, event.size.height)

    def adapt_layout(self, width: int, height: int) -> None:
        """Stack scrollable panels while keeping job controls reachable."""
        self.set_class(width < 90, "narrow")
        self.set_class(width < 60, "small")
        self.set_class(height < 32, "short")

    def status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def job(self) -> Job:
        return Job(
            str(self.query_one("#operation", Select).value),
            Path(self.query_one("#directory", Input).value.strip()).expanduser(),
            self.query_one("#recursive", Checkbox).value,
            str(self.query_one("#format", Select).value),
            self.query_one("#recognition", Checkbox).value,
            self.query_one("#covers", Checkbox).value,
            self.query_one("#shazam", Checkbox).value,
        )

    @on(Select.Changed, "#operation")
    def update_options(self) -> None:
        operation = self.query_one("#operation", Select).value
        for selector in ("#format", "#format-label"):
            self.query_one(selector).display = operation == "rename"
        for selector in ("#recognition", "#covers"):
            self.query_one(selector).display = operation == "lyrics"
        self.query_one("#shazam").display = operation == "recognize"
        self.query_one("#recursive").disabled = operation == "revert"

    @on(DirectoryTree.DirectorySelected)
    def directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#directory", Input).value = str(event.path)
        self.action_preview()

    @on(Button.Pressed, "#preview")
    def action_preview(self) -> None:
        if not self.running_job:
            self.preview_files()

    @work(exclusive=True, group="preview")
    async def preview_files(self) -> None:
        try:
            job = self.job()
            job.arguments()
            files = await asyncio.to_thread(
                get_audio_files,
                str(job.directory),
                job.recursive or job.operation == "revert",
            )
            if job.operation == "revert":
                files = [f for f in files if Path(f).parent != job.directory.resolve()]
            table = self.query_one("#files", DataTable)
            table.clear()
            for file in files:
                table.add_row(Path(file).name, str(Path(file).parent))
            self.query_one("#browser-tabs", TabbedContent).active = "files-pane"
            self.status(
                f"{len(files)} audio files in scope. Preview does not modify files."
            )
        except (OSError, ValueError) as error:
            self.query_one("#files", DataTable).clear()
            self.status(str(error))

    @on(Button.Pressed, "#run")
    def start_job(self) -> None:
        if self.running_job:
            return
        try:
            job = self.job()
            arguments = job.arguments()
        except (ValueError, OSError) as error:
            self.status(str(error))
            return
        self.running_job = True
        self.cancelling = False
        self.paused = False
        self.set_busy(True)
        self.push_screen(
            Confirmation(
                f"{OPERATIONS[job.operation]}\nDirectory: {job.directory.resolve()}\n"
                f"Include subdirectories: {job.recursive or job.operation == 'revert'}\n"
                "This operation can rename, move or update audio files. Continue?"
            ),
            lambda confirmed: self.launch_confirmed(confirmed, arguments),
        )

    def launch_confirmed(self, confirmed: bool, arguments: list) -> None:
        if confirmed:
            self.execute_job(arguments)
        else:
            self.running_job = False
            self.set_busy(False)
            self.status("Cancelled before processing. No files changed.")
            if self.quit_after_job:
                self.exit()

    def set_busy(self, busy: bool) -> None:
        for selector in (
            "#run",
            "#preview",
            "#save-key",
            "#delete-key",
            "#clear-config",
            "#default-recursive",
            "#light-theme",
        ):
            self.query_one(selector).disabled = busy
        for selector in ("#pause", "#cancel-job"):
            self.query_one(selector).disabled = not busy
        self.query_one("#busy").display = busy

    async def send_control(self, action: str, **values: bool) -> None:
        if self.process and self.process.returncode is None and self.process.stdin:
            try:
                self.process.stdin.write(
                    (json.dumps({"action": action, **values}) + "\n").encode()
                )
                await self.process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass

    @work(group="job")
    async def execute_job(self, arguments: list) -> None:
        log = self.query_one("#log", RichLog)
        log.clear()
        self.query_one(TabbedContent).active = "output-pane"
        self.status("Processing. Review file errors in the output below.")
        try:
            environment = dict(
                os.environ,
                PYTHONIOENCODING="utf-8",
                PYTHONUNBUFFERED="1",
                NO_COLOR="1",
                TERM="dumb",
            )
            environment["PYTHONPATH"] = (
                str(Path(__file__).resolve().parents[2])
                + os.pathsep
                + environment.get("PYTHONPATH", "")
            )
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-m",
                "core.tui.runner",
                *arguments,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=environment,
            )
            if self.cancelling or self.quit_after_job:
                await self.send_control("cancel")
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text.startswith(EVENT_PREFIX):
                    event = json.loads(text[len(EVENT_PREFIX) :])
                    if event["kind"] == "confirm" and not self.cancelling:
                        answer = await self.push_screen_wait(
                            Confirmation(event["text"])
                        )
                        await self.send_control("answer", value=answer)
                    elif event["kind"] == "progress":
                        log.write(
                            f"{event['description']} ({event['completed']:g}/{event['total'] or '?'})"
                        )
                else:
                    log.write(text)
            code = await self.process.wait()
            if code == 130:
                self.status(
                    "Cancelled at a checkpoint. Completed changes remain; review output."
                )
            elif code:
                self.status(
                    f"Command failed with exit code {code}. Review output for details."
                )
            else:
                self.status(
                    "Command finished. Review the summary and any per-file errors below."
                )
        except (OSError, ValueError) as error:
            self.status(f"Unable to run command: {error}")
        finally:
            if self.process and self.process.returncode is None:
                await self.send_control("cancel")
                await self.process.wait()
            self.process = None
            self.running_job = False
            self.paused = False
            self.set_busy(False)
            self.query_one("#pause", Button).label = "Pause"
            if self.quit_after_job:
                self.exit()

    @on(Button.Pressed, "#pause")
    async def action_pause(self) -> None:
        if self.process and not self.cancelling:
            self.paused = not self.paused
            await self.send_control("pause" if self.paused else "resume")
            self.query_one("#pause", Button).label = (
                "Resume" if self.paused else "Pause"
            )
            self.status(
                "Pause requested; waiting for a checkpoint."
                if self.paused
                else "Resumed."
            )

    @on(Button.Pressed, "#cancel-job")
    async def action_cancel_job(self) -> None:
        if self.running_job:
            self.cancelling = True
            await self.send_control("cancel")
            if isinstance(self.screen, Confirmation):
                self.screen.dismiss(False)
            self.status(
                "Cancellation requested. Waiting for the current operation to finish."
            )

    async def action_request_quit(self) -> None:
        if self.running_job:
            self.quit_after_job = True
            if self.process:
                await self.action_cancel_job()
            elif isinstance(self.screen, Confirmation):
                self.screen.dismiss(False)
            else:
                await self.action_cancel_job()
        else:
            self.exit()

    def action_help(self) -> None:
        self.query_one(TabbedContent).active = "help-pane"

    def refresh_keys(self) -> None:
        table = self.query_one("#keys", DataTable)
        table.clear()
        for key in VALID_KEYS:
            table.add_row(key, "Configured" if self.config.get(key) else "Not set")

    @on(Button.Pressed, "#load-key")
    def load_key(self) -> None:
        key = str(self.query_one("#key", Select).value)
        self.query_one("#secret", Input).value = self.config.get(key, "")

    @on(Button.Pressed, "#save-key")
    def save_key(self) -> None:
        value = self.query_one("#secret", Input).value.strip()
        if not value:
            self.notify("Enter a non-empty credential.", severity="warning")
            return
        self.change_config("save", value)

    @on(Button.Pressed, "#delete-key, #clear-config")
    def delete_config(self, event: Button.Pressed) -> None:
        action = "clear" if event.button.id == "clear-config" else "delete"
        key = str(self.query_one("#key", Select).value)
        self.push_screen(
            Confirmation(
                "Clear all configuration?" if action == "clear" else f"Delete {key}?"
            ),
            lambda yes: self.change_config(action, key=key) if yes else None,
        )

    def change_config(
        self, action: str, value: str = "", key: Optional[str] = None
    ) -> None:
        if self.running_job:
            return
        key = key or str(self.query_one("#key", Select).value)
        try:
            if action == "save":
                self.config.set(key, value)
            elif action == "delete":
                self.config.delete(key)
            else:
                self.config.clear()
            self.query_one("#secret", Input).value = ""
            self.refresh_keys()
            self.notify("Configuration updated.")
        except OSError as error:
            self.notify(str(error), severity="error")

    @on(Checkbox.Changed, "#default-recursive, #light-theme")
    def setting_changed(self, event: Checkbox.Changed) -> None:
        if self.running_job:
            return
        try:
            if event.checkbox.id == "light-theme":
                self.config.set_setting("theme", "light" if event.value else "dark")
                self.theme = "textual-light" if event.value else "textual-dark"
            else:
                self.config.set_setting("recursive", event.value)
                self.query_one("#recursive", Checkbox).value = event.value
        except OSError as error:
            self.notify(str(error), severity="error")
