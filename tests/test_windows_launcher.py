import sys

import pytest

from core.tui.runner import worker_command


@pytest.mark.parametrize("frozen", [False, True])
def test_worker_launch_preserves_arguments(monkeypatch, frozen):
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "executable", "musren.exe" if frozen else "python.exe")
    arguments = ["rename", "run", "--directory", "C:\\Music with spaces"]
    expected = (
        ["musren.exe", "--_musren-worker"]
        if frozen
        else ["python.exe", "-u", "-m", "core.tui.runner"]
    )
    assert worker_command(arguments) == expected + arguments


def test_internal_worker_dispatch(monkeypatch):
    import app
    from core.tui import runner

    seen = []
    monkeypatch.setattr(
        sys, "argv", ["musren.exe", "--_musren-worker", "rename", "run"]
    )
    monkeypatch.setattr(runner, "main", lambda: seen.extend(sys.argv[1:]))
    app.main()
    assert seen == ["rename", "run"]


@pytest.mark.parametrize(
    "arguments,mode",
    [
        ([], "tui"),
        (["--help"], "cli"),
        (["--cli"], "cli"),
        (["rename", "--help"], "cli"),
    ],
)
def test_windows_launcher_modes(monkeypatch, arguments, mode):
    from scripts import windows_launcher

    seen = []
    monkeypatch.setattr(sys, "argv", ["musren.exe", *arguments])
    monkeypatch.setattr(
        windows_launcher.multiprocessing, "freeze_support", lambda: None
    )
    monkeypatch.setattr(windows_launcher.app, "main", lambda: seen.append("cli"))
    monkeypatch.setattr(windows_launcher.app, "tui", lambda: seen.append("tui"))
    windows_launcher.main()
    assert seen == [mode]
    assert "--cli" not in sys.argv
