"""Smoke-test the actual portable executable and its TUI worker lifecycle."""

import argparse
import subprocess
import tempfile
from pathlib import Path


async def smoke_tui() -> None:
    """Launch the packaged TUI headlessly and verify a real rename and rollback."""
    from mutagen.id3 import ID3, TIT2, TPE1
    from textual.widgets import Input, Select, Static

    from core.cli.config import ConfigManager
    from core.tui.app import Confirmation, MusrenApp

    with tempfile.TemporaryDirectory(prefix="musren-smoke-") as temporary:
        folder = Path(temporary)
        source = folder / "original.mp3"
        source.write_bytes((b"\xff\xfb\x90\x00" + bytes(413)) * 8)
        tags = ID3()
        tags.add(TPE1(encoding=3, text=["Smoke artist"]))
        tags.add(TIT2(encoding=3, text=["Smoke title"]))
        tags.save(source)
        original = source.read_bytes()
        app = MusrenApp(ConfigManager(folder / "config.json"))
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#directory", Input).value = str(folder)
            app.query_one("#format", Select).value = "2"
            await app.preview_files().wait()
            app.start_job()
            await pilot.pause()
            app.screen.dismiss(True)
            for _ in range(600):
                await pilot.pause(0.05)
                if isinstance(app.screen, Confirmation):
                    break
                if not app.running_job:
                    raise AssertionError(str(app.query_one("#status", Static).render()))
            assert isinstance(app.screen, Confirmation), (
                "Packaged worker did not return a confirmation"
            )
            assert "keep" in app.screen.text
            assert (folder / "Smoke title.mp3").exists(), (
                "Packaged worker did not rename the file"
            )
            await pilot.pause()
            app.screen.dismiss(False)
            for _ in range(600):
                if not app.running_job:
                    break
                await pilot.pause(0.05)
            assert not app.running_job, "Packaged worker did not finish"
            assert source.read_bytes() == original, (
                "Rename rollback did not preserve audio"
            )
            assert not (folder / "Smoke title.mp3").exists()
    print("Portable TUI preview, child worker, rename and rollback passed")


def verify(executable: Path, version: str) -> None:
    """Run CLI and headless TUI checks without using the source checkout."""
    executable = executable.resolve()
    with tempfile.TemporaryDirectory(prefix="musren-portable-") as temporary:
        for arguments in (["--version"], ["--help"], ["--_musren-smoke-test"]):
            result = subprocess.run(
                [str(executable), *arguments],
                cwd=temporary,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            if arguments == ["--version"]:
                assert result.stdout.strip() == f"musren {version}"
            print(result.stdout.strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--version")
    args = parser.parse_args()
    if args.version is None:
        from importlib.metadata import version

        args.version = version("musren")
    verify(args.executable, args.version)
