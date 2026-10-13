"""Exercise shared workflows on disposable tagged audio with offline services."""

import importlib
import sys

import pytest
from typer.testing import CliRunner

from core.audio_processor import AudioProcessor
from core.cli.app import app
from core.cli.config import ConfigManager
from core.tui.jobs import Job
from utils.tools import PauseManager


@pytest.fixture
def tagged_mp3(tmp_path):
    from mutagen.id3 import ID3, TALB, TIT2, TPE1, TRCK

    def create(name="original.mp3", title="Title", album="Album", track="1"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # Valid MPEG-1 layer III frame headers, with silent placeholder payloads.
        path.write_bytes((b"\xff\xfb\x90\x00" + bytes(413)) * 8)
        tags = ID3()
        for frame in (
            TPE1(encoding=3, text=["Artist"]),
            TIT2(encoding=3, text=[title]),
            TALB(encoding=3, text=[album]),
            TRCK(encoding=3, text=[track]),
        ):
            tags.add(frame)
        tags.save(path)
        from mutagen import File

        assert File(path, easy=True)["title"] == [title]
        return path

    return create


@pytest.fixture(autouse=True)
def offline_commands(monkeypatch, tmp_path):
    config = ConfigManager(tmp_path / "config.json")
    for name in ("rename", "lyrics", "covers", "recognize", "albums"):
        module = importlib.import_module(f"core.cli.commands.{name}")
        if hasattr(module, "check_dependencies"):
            monkeypatch.setattr(module, "check_dependencies", lambda **kwargs: True)
        if hasattr(module, "get_config_manager"):
            monkeypatch.setattr(module, "get_config_manager", lambda: config)
        pause = PauseManager()
        monkeypatch.setattr(pause, "start", lambda: None)
        monkeypatch.setattr(module, "get_pause_manager", lambda: pause)
    # External services must never be called in this suite.
    monkeypatch.setattr(
        AudioProcessor,
        "_recognize_song",
        lambda self, path: {"status": False, "message": "No match"},
    )
    monkeypatch.setattr(
        AudioProcessor,
        "_fetch_synced_lyrics",
        lambda self, artist, title: {"status": False, "message": "No lyrics"},
    )


@pytest.mark.parametrize(
    "format,expected",
    [("1", "Artist - Title.mp3"), ("2", "Title.mp3"), ("3", "01 - Artist - Title.mp3")],
)
@pytest.mark.parametrize("keep", [True, False])
def test_rename_formats_keep_and_undo(tagged_mp3, tmp_path, format, expected, keep):
    source = tagged_mp3()
    tagged_mp3("second.mp3", title="Second", track="2")
    tagged_mp3("third.mp3", title="Third", track="3")
    before = source.read_bytes()
    result = CliRunner().invoke(
        app,
        Job("rename", tmp_path, rename_format=format).arguments(),
        input="y\n" if keep else "n\n",
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / expected).exists() == keep
    assert source.exists() == (not keep)
    assert (tmp_path / expected if keep else source).read_bytes() == before


def test_albums_organize_revert_and_collisions(tagged_mp3, tmp_path):
    source = tagged_mp3()
    tagged_mp3("second.mp3", title="Second")
    existing = tagged_mp3("Album/original.mp3", title="Existing")
    before = existing.read_bytes()
    result = CliRunner().invoke(app, Job("albums", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert not source.exists()
    assert existing.read_bytes() == before
    assert (tmp_path / "Album" / "original (1).mp3").exists()
    result = CliRunner().invoke(
        app, Job("albums", tmp_path, recursive=True).arguments()
    )
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / "Album").glob("*.mp3"))) == 3
    result = CliRunner().invoke(app, Job("revert", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert len(list(tmp_path.glob("*.mp3"))) == 3
    assert not (tmp_path / "Album").exists()


def test_lyrics_embeds_real_tags(tagged_mp3, tmp_path, monkeypatch):
    from mutagen.id3 import ID3

    source = tagged_mp3()
    monkeypatch.setattr(
        AudioProcessor,
        "_fetch_synced_lyrics",
        lambda *args: {"status": True, "lyrics": "[00:01.00]Hello"},
    )
    result = CliRunner().invoke(app, Job("lyrics", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert any("Hello" in frame.text for frame in ID3(source).getall("USLT"))


@pytest.mark.parametrize("success", [True, False])
def test_recognition_updates_real_tags(tagged_mp3, tmp_path, monkeypatch, success):
    from mutagen import File

    source = tagged_mp3()
    monkeypatch.setattr(
        AudioProcessor,
        "_recognize_song",
        lambda *args: {
            "status": success,
            "artist": "Recognized artist",
            "title": "Recognized title",
            "album": "Recognized album",
            "message": "No match",
        },
    )
    result = CliRunner().invoke(app, Job("recognize", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert File(source, easy=True)["title"] == [
        "Recognized title" if success else "Title"
    ]
    if not success:
        assert "No match" in result.output


def test_recursive_covers_real_embedding_and_skip(tagged_mp3, tmp_path, monkeypatch):
    from mutagen.id3 import ID3
    from core.artwork import AlbumArtManager

    source = tagged_mp3("nested/track.mp3")
    monkeypatch.setattr(
        AlbumArtManager, "fetch_album_cover", lambda *args: "offline-image"
    )
    monkeypatch.setattr(
        AlbumArtManager,
        "fetch_cover_image",
        lambda *args: b"\xff\xd8\xff\xe0" + b"image",
    )
    args = Job("covers", tmp_path, recursive=True).arguments()
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert len(ID3(source).getall("APIC")) == 1
    assert "1 added" in result.output
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "1 skipped" in result.output


def test_missing_dependencies_noninteractive(monkeypatch, capsys):
    from utils import dependencies

    monkeypatch.setattr(dependencies.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("Must not prompt"))
    assert not dependencies.check_dependencies(require_lyrics=True, interactive=False)
    assert "pip install mutagen requests syncedlyrics" in capsys.readouterr().out


def test_shazam_does_not_require_acoustid(monkeypatch):
    from utils import dependencies

    seen = []
    monkeypatch.setattr(
        dependencies.importlib.util,
        "find_spec",
        lambda name: seen.append(name) or object(),
    )
    assert dependencies.check_dependencies(
        use_recognition=True, use_shazam=True, interactive=False
    )
    assert "shazamio" in seen
    assert "acoustid" not in seen


def test_app_preserves_argument_boundaries(monkeypatch, tmp_path):
    import app as entry

    cli_module = importlib.import_module("core.cli.app")
    folder = tmp_path / "Music with spaces"
    folder.mkdir()
    monkeypatch.setattr(
        sys, "argv", ["musren", "rename", "--directory", str(folder), "--yes"]
    )
    seen = []
    monkeypatch.setattr(cli_module, "cli", lambda: seen.extend(sys.argv[1:]))
    entry.main()
    assert seen == ["rename", "--directory", str(folder), "--yes"]


def test_cli_help_and_unknown_command(monkeypatch):
    from core.cli.app import cli

    monkeypatch.setattr(sys, "argv", ["musren", "rename", "--help"])
    with pytest.raises(SystemExit) as result:
        cli()
    assert result.value.code == 0
    monkeypatch.setattr(sys, "argv", ["musren", "unknown"])
    with pytest.raises(SystemExit) as result:
        cli()
    assert result.value.code == 2


def test_lyrics_recognition_and_covers_combined(tagged_mp3, tmp_path, monkeypatch):
    from mutagen import File
    from mutagen.id3 import ID3
    from core.artwork import AlbumArtManager

    source = tagged_mp3()
    monkeypatch.setattr(
        AudioProcessor,
        "_recognize_song",
        lambda *args: {
            "status": True,
            "artist": "New artist",
            "title": "New title",
            "album": "New album",
        },
    )
    monkeypatch.setattr(
        AudioProcessor,
        "_fetch_synced_lyrics",
        lambda *args: {
            "status": True,
            "lyrics": "[00:02.00]Combined lyrics",
        },
    )
    monkeypatch.setattr(
        AlbumArtManager, "fetch_album_cover", lambda *args: "offline-image"
    )
    monkeypatch.setattr(
        AlbumArtManager, "fetch_cover_image", lambda *args: b"\xff\xd8\xff\xe0image"
    )
    result = CliRunner().invoke(
        app, Job("lyrics", tmp_path, recognition=True, covers=True).arguments()
    )
    assert result.exit_code == 0, result.output
    assert File(source, easy=True)["title"] == ["New title"]
    tags = ID3(source)
    assert tags.getall("USLT")
    assert tags.getall("APIC")


def test_covers_failure_and_lyrics_failure_are_reported(
    tagged_mp3, tmp_path, monkeypatch
):
    from core.artwork import AlbumArtManager

    tagged_mp3()
    monkeypatch.setattr(AlbumArtManager, "fetch_album_cover", lambda *args: None)
    result = CliRunner().invoke(app, Job("covers", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert "1 failed" in result.output
    assert "No cover found" in result.output
    result = CliRunner().invoke(app, Job("lyrics", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert "No lyrics" in result.output


def test_shazam_backend(tagged_mp3, tmp_path, monkeypatch):
    from core.shazam_processor import ShazamProcessor
    from mutagen import File

    source = tagged_mp3()
    monkeypatch.setattr(ShazamProcessor, "__init__", lambda self: None)
    monkeypatch.setattr(
        ShazamProcessor,
        "recognize",
        lambda *args: {
            "status": True,
            "artist": "Shazam artist",
            "title": "Shazam title",
            "album": "Shazam album",
        },
    )
    monkeypatch.setattr(
        AudioProcessor, "_recognize_song", lambda *args: pytest.fail("Wrong backend")
    )
    result = CliRunner().invoke(
        app, Job("recognize", tmp_path, shazam=True).arguments()
    )
    assert result.exit_code == 0, result.output
    assert File(source, easy=True)["title"] == ["Shazam title"]


def test_invalid_audio_is_reported(tmp_path):
    (tmp_path / "broken.mp3").write_bytes(b"invalid audio")
    result = CliRunner().invoke(app, Job("rename", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert "Missing metadata" in result.output
    result = CliRunner().invoke(app, Job("lyrics", tmp_path).arguments())
    assert result.exit_code == 0, result.output
    assert "can't sync" in result.output


@pytest.mark.parametrize("keep", [True, False])
def test_tui_actual_rename_and_undo(tagged_mp3, tmp_path, keep):
    pytest.importorskip("textual")
    import asyncio
    from textual.widgets import Input, Select
    from core.tui.app import Confirmation, MusrenApp

    source = tagged_mp3()
    before = source.read_bytes()

    async def scenario():
        tui = MusrenApp(ConfigManager(tmp_path / "config.json"))
        async with tui.run_test(size=(120, 45)) as pilot:
            tui.query_one("#directory", Input).value = str(tmp_path)
            tui.query_one("#format", Select).value = "2"
            tui.start_job()
            await pilot.pause()
            await pilot.click("#confirm")
            for _ in range(150):
                await pilot.pause(0.03)
                if isinstance(tui.screen, Confirmation):
                    break
            assert isinstance(tui.screen, Confirmation)
            assert "keep" in tui.screen.text
            await pilot.pause()
            await pilot.click("#confirm" if keep else "#decline")
            for _ in range(150):
                if not tui.running_job:
                    break
                await pilot.pause(0.03)
            assert not tui.running_job
            target = tmp_path / "Title.mp3" if keep else source
            assert target.read_bytes() == before
            assert source.exists() == (not keep)

    asyncio.run(scenario())


def test_child_cancel_at_rename_confirmation(tagged_mp3, tmp_path):
    import json
    import queue
    import subprocess
    import threading
    from core.tui.runner import EVENT_PREFIX

    source = tagged_mp3()
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "core.tui.runner",
            *Job("rename", tmp_path, rename_format="2").arguments(),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    lines = queue.Queue()
    reader = threading.Thread(
        target=lambda: [lines.put(line) for line in process.stdout], daemon=True
    )
    reader.start()
    try:
        for _ in range(100):
            line = lines.get(timeout=10)
            if (
                line.startswith(EVENT_PREFIX)
                and json.loads(line[len(EVENT_PREFIX) :])["kind"] == "confirm"
            ):
                break
        else:
            pytest.fail("No keep/undo confirmation received")
        process.stdin.write(json.dumps({"action": "cancel"}) + "\n")
        process.stdin.flush()
        process.wait(timeout=10)
        assert process.returncode == 130
        assert not source.exists()
        assert (tmp_path / "Title.mp3").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        reader.join(timeout=2)
        process.stdin.close()
        process.stdout.close()


def test_child_missing_dependency_never_prompts(tmp_path):
    import subprocess

    arguments = Job("lyrics", tmp_path).arguments()
    code = """
import importlib.util
import sys
original = importlib.util.find_spec
importlib.util.find_spec = lambda name: None if name == 'syncedlyrics' else original(name)
from core.tui.runner import main
main()
"""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", code, *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    try:
        process.wait(timeout=10)
        output = process.stdout.read()
        assert process.returncode == 1, output
        assert "pip install syncedlyrics" in output
        assert "Do you want to install" not in output
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
