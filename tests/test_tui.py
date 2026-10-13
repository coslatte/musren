import asyncio
import importlib.util
import json
import subprocess
import sys
import threading

import pytest

from core.cli.config import ConfigManager
from core.tui.jobs import Job, OPERATIONS
from core.tui.runner import Controls


@pytest.mark.parametrize("operation", OPERATIONS)
def test_job_arguments(operation, tmp_path):
    folder = tmp_path / "Music with spaces"
    folder.mkdir()
    args = Job(
        operation, folder, recursive=True, recognition=True, covers=True, shazam=True
    ).arguments()
    assert args[args.index("--directory") + 1] == str(folder.resolve())
    assert ("--recursive" in args) == (operation != "revert")
    assert ("--recognition" in args) == (operation == "lyrics")
    assert ("--covers" in args) == (operation == "lyrics")
    assert ("--shazam" in args) == (operation == "recognize")


@pytest.mark.parametrize("operation,format", [("invalid", "1"), ("rename", "4")])
def test_invalid_job(operation, format, tmp_path):
    with pytest.raises(ValueError):
        Job(operation, tmp_path, rename_format=format).arguments()


def test_missing_directory(tmp_path):
    with pytest.raises(ValueError):
        Job("rename", tmp_path / "missing").arguments()


def test_controls_pause_resume_cancel():
    controls = Controls()
    controls.paused.set()
    completed = threading.Event()
    thread = threading.Thread(
        target=lambda: (controls.wait_if_paused(), completed.set())
    )
    thread.start()
    assert not completed.wait(0.15)
    controls.paused.clear()
    thread.join(timeout=2)
    assert completed.is_set()
    controls.cancelled.set()
    with pytest.raises(SystemExit) as error:
        controls.wait_if_paused()
    assert error.value.code == 130


def test_controls_answers_and_cancel():
    controls = Controls()
    controls.answers.put(False)
    assert controls.confirm("Keep changes?") is False
    controls.answers.put(True)
    assert controls.confirm("Keep changes?") is True
    controls.cancelled.set()
    with pytest.raises(SystemExit):
        controls.confirm("Keep changes?")


def test_config_custom_path_roundtrip(tmp_path):
    path = tmp_path / "config folder" / "config.json"
    config = ConfigManager(path)
    config.set("acoustid", "secret")
    config.set_setting("theme", "light")
    reloaded = ConfigManager(path)
    assert reloaded.get("acoustid") == "secret"
    assert reloaded.get_setting("theme") == "light"
    assert reloaded.delete("acoustid")
    reloaded.clear()
    assert not path.exists()


@pytest.mark.parametrize("operation", ["rename", "covers", "albums", "revert"])
def test_child_process_empty_directory(operation, tmp_path):
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "core.tui.runner",
            *Job(operation, tmp_path).arguments(),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    # Keep stdin open until the child completes, as the TUI does.
    try:
        process.wait(timeout=15)
        output = process.stdout.read()
        assert process.returncode == 0, output
        assert "No audio files" in output
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


HAS_TEXTUAL = importlib.util.find_spec("textual") is not None


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_tui_mount_preview_config_help(tmp_path, size):
    from textual.widgets import Checkbox, DataTable, Input, Select, TabbedContent
    from core.tui.app import MusrenApp

    async def scenario():
        config = ConfigManager(tmp_path / "settings" / "config.json")
        app = MusrenApp(config)
        async with app.run_test(size=size) as pilot:
            app.query_one("#directory", Input).value = str(tmp_path)
            (tmp_path / "audio.mp3").write_bytes(b"placeholder")
            sub = tmp_path / "nested"
            sub.mkdir()
            (sub / "other.FLAC").write_bytes(b"placeholder")
            await app.preview_files().wait()
            assert app.query_one("#files", DataTable).row_count == 1
            app.query_one("#recursive", Checkbox).value = True
            await app.preview_files().wait()
            assert app.query_one("#files", DataTable).row_count == 2
            app.query_one("#operation", Select).value = "revert"
            await pilot.pause()
            await app.preview_files().wait()
            assert app.query_one("#files", DataTable).row_count == 1
            assert app.query_one("#recursive", Checkbox).disabled
            app.query_one(TabbedContent).active = "configuration"
            await pilot.pause()
            app.query_one("#secret", Input).value = "private key"
            app.save_key()
            assert ConfigManager(config.config_path).get("acoustid") == "private key"
            assert app.query_one("#secret", Input).value == ""
            app.load_key()
            assert app.query_one("#secret", Input).password
            assert app.query_one("#secret", Input).value == "private key"
            app.change_config("delete")
            assert not config.get("acoustid")
            app.query_one("#light-theme", Checkbox).value = True
            await pilot.pause()
            assert app.theme == "textual-light"
            app.action_help()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "help-pane"

    asyncio.run(scenario())


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
def test_tui_run_and_decline(tmp_path):
    from textual.widgets import Input, Static
    from core.tui.app import Confirmation, MusrenApp

    async def scenario():
        app = MusrenApp(ConfigManager(tmp_path / "config.json"))
        async with app.run_test(size=(120, 45)) as pilot:
            app.query_one("#directory", Input).value = str(tmp_path)
            app.start_job()
            await pilot.pause()
            assert isinstance(app.screen, Confirmation)
            await pilot.click("#decline")
            await pilot.pause()
            assert not app.running_job
            assert not list(tmp_path.iterdir())
            app.start_job()
            await pilot.pause()
            await pilot.click("#confirm")
            for _ in range(100):
                if not app.running_job:
                    break
                await pilot.pause(0.05)
            assert not app.running_job
            assert "Command finished" in str(app.query_one("#status", Static).render())
            assert not list(tmp_path.iterdir())

    asyncio.run(scenario())


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
def test_tui_invalid_directory(tmp_path):
    from textual.widgets import Input, Static
    from core.tui.app import MusrenApp

    async def scenario():
        app = MusrenApp(ConfigManager(tmp_path / "config.json"))
        async with app.run_test() as pilot:
            app.query_one("#directory", Input).value = str(tmp_path / "missing")
            app.start_job()
            await pilot.pause()
            assert not app.running_job
            assert "existing directory" in str(
                app.query_one("#status", Static).render()
            )

    asyncio.run(scenario())


def test_runner_protocol(monkeypatch):
    import io

    controls = Controls()
    messages = [
        {"action": "pause"},
        {"action": "answer", "value": True},
        {"action": "resume"},
        {"action": "cancel"},
    ]
    monkeypatch.setattr(
        sys, "stdin", io.StringIO("\n".join(json.dumps(m) for m in messages))
    )
    controls.listen()
    assert controls.cancelled.is_set()
    assert not controls.paused.is_set()
    assert controls.answers.get_nowait() is True


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
def test_tui_quit_at_initial_confirmation(tmp_path):
    from core.tui.app import MusrenApp
    from textual.widgets import Input

    async def scenario():
        tui = MusrenApp(ConfigManager(tmp_path / "config.json"))
        async with tui.run_test() as pilot:
            tui.query_one("#directory", Input).value = str(tmp_path)
            tui.start_job()
            await pilot.pause()
            await tui.action_request_quit()
            await pilot.pause()
            assert not tui.running_job
            assert tui.quit_after_job
            assert not list(tmp_path.iterdir())

    asyncio.run(scenario())


def test_tui_launch_missing_dependency(monkeypatch):
    import app as entry
    import builtins

    original = builtins.__import__

    def without_textual(name, *args, **kwargs):
        if name == "core.tui.app":
            raise ModuleNotFoundError("No module named 'textual'", name="textual")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_textual)
    expected = "Python 3.9" if sys.version_info < (3, 9) else "pip install"
    with pytest.raises(SystemExit, match=expected):
        entry.tui()


def test_optional_imports_have_no_side_effects():
    code = """
import importlib.abc
import sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'textual', 'shazamio', 'mutagen', 'requests', 'acoustid', 'syncedlyrics'}:
            raise ModuleNotFoundError(fullname, name=fullname)
sys.meta_path.insert(0, BlockOptional())
import app
import core.tui
import core.tui.jobs
import core.tui.runner
import core.audio_processor
import core.shazam_processor
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout


def test_entrypoints_keep_cli_and_add_tui(monkeypatch):
    import app as entry
    import core.cli.shell as shell

    seen = []
    monkeypatch.setattr(shell, "cli", lambda: seen.append("cli"))
    monkeypatch.setattr(entry, "tui", lambda: seen.append("tui"))
    monkeypatch.setattr(sys, "argv", ["musren"])
    entry.main()
    monkeypatch.setattr(sys, "argv", ["musren", "--tui"])
    entry.main()
    assert seen == ["cli", "tui"]
    monkeypatch.setattr(sys, "argv", ["musren", "--tui", "rename"])
    with pytest.raises(SystemExit, match="Use --tui alone"):
        entry.main()


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
def test_tui_config_confirmation_and_settings(tmp_path):
    from core.tui.app import MusrenApp
    from textual.widgets import Checkbox, TabbedContent

    async def scenario():
        config = ConfigManager(tmp_path / "config.json")
        config.set("acoustid", "secret")
        tui = MusrenApp(config)
        async with tui.run_test(size=(120, 45)) as pilot:
            tui.query_one(TabbedContent).active = "configuration"
            await pilot.pause()
            await pilot.click("#clear-config")
            await pilot.pause()
            await pilot.click("#decline")
            assert config.get("acoustid") == "secret"
            await pilot.click("#delete-key")
            await pilot.pause()
            await pilot.click("#confirm")
            assert not ConfigManager(config.config_path).get("acoustid")
            tui.query_one("#default-recursive", Checkbox).value = True
            await pilot.pause()
            assert ConfigManager(config.config_path).get_setting("recursive") is True
            assert tui.query_one("#recursive", Checkbox).value

    asyncio.run(scenario())


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
def test_tui_child_launch_failure_recovers(tmp_path, monkeypatch):
    from core.tui.app import MusrenApp
    from textual.widgets import Input, Button, Static

    async def fail_launch(*args, **kwargs):
        raise OSError("Process launch denied")

    async def scenario():
        tui = MusrenApp(ConfigManager(tmp_path / "config.json"))
        async with tui.run_test(size=(120, 45)) as pilot:
            monkeypatch.setattr(asyncio, "create_subprocess_exec", fail_launch)
            tui.query_one("#directory", Input).value = str(tmp_path)
            tui.start_job()
            await pilot.pause()
            await pilot.click("#confirm")
            await pilot.pause()
            assert not tui.running_job
            assert not tui.query_one("#run", Button).disabled
            assert "Process launch denied" in str(
                tui.query_one("#status", Static).render()
            )

    asyncio.run(scenario())


@pytest.mark.skipif(not HAS_TEXTUAL, reason="Install the tui extra for UI tests")
@pytest.mark.parametrize("size", [(40, 20), (60, 20), (80, 24), (100, 30), (160, 50)])
def test_responsive_layout_keeps_controls_visible(tmp_path, size):
    from core.tui.app import Confirmation, MusrenApp
    from textual.widgets import Button, Input, TabbedContent

    async def scenario():
        tui = MusrenApp(ConfigManager(tmp_path / "config.json"))
        async with tui.run_test(size=size) as pilot:
            await pilot.pause()
            regions = [
                tui.query_one(selector, Button).region
                for selector in ("#preview", "#run", "#pause", "#cancel-job")
            ]
            for region in regions:
                assert region.width >= 10
                assert region in tui.screen.region
            for index, region in enumerate(regions):
                assert all(not region.overlaps(other) for other in regions[index + 1 :])
            tui.query_one("#directory", Input).value = str(tmp_path)
            tui.start_job()
            await pilot.pause()
            assert isinstance(tui.screen, Confirmation)
            assert tui.query_one("#confirm", Button).region in tui.screen.region
            assert tui.query_one("#decline", Button).region in tui.screen.region
            await pilot.press("escape")
            await pilot.pause()
            tui.query_one(TabbedContent).active = "configuration"
            await pilot.pause()
            for selector in ("#save-key", "#load-key", "#delete-key", "#clear-config"):
                button = tui.query_one(selector, Button)
                button.scroll_visible(immediate=True)
                await pilot.pause()
                assert button.region in tui.screen.region
            await pilot.resize_terminal(120, 45)
            await pilot.pause()
            assert not tui.has_class("narrow")
            await pilot.resize_terminal(50, 24)
            await pilot.pause()
            assert tui.has_class("narrow") and tui.has_class("small")

    asyncio.run(scenario())
