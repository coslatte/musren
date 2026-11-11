"""Public CLI and TUI launch functions for installed environments."""

import sys
import warnings

from musren.constants.info import MUSIC_RENAMER_VERSION


def main(interactive: bool = True) -> None:
    """Dispatch CLI, TUI, interactive shell, and isolated worker modes."""
    if sys.argv[1:2] == ["--_musren-worker"]:
        from musren.core.tui.runner import main as run_worker

        del sys.argv[1]
        run_worker()
        return
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"musren {MUSIC_RENAMER_VERSION}")
        return

    warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")

    if "--tui" in sys.argv[1:]:
        if sys.argv[1:] != ["--tui"]:
            raise SystemExit(
                "Use --tui alone; choose processing options inside the TUI."
            )
        tui()
    elif interactive and len(sys.argv) == 1:
        from musren.core.cli.shell import cli as musren_shell

        musren_shell()
    elif len(sys.argv) > 1:
        from musren.core.cli.app import cli

        cli()
    else:
        from musren.core.cli.shell import InteractiveShell

        InteractiveShell().run()


def tui() -> None:
    """Launch the optional terminal interface without importing it for CLI use."""
    if sys.version_info < (3, 10):
        raise SystemExit("musren requires Python 3.10 or newer.")
    try:
        from musren.core.tui.app import MusrenApp
    except ModuleNotFoundError as error:
        if error.name != "textual":
            raise
        raise SystemExit(
            'TUI dependency missing. Install: pip install ".[tui]"'
        ) from error
    MusrenApp().run()
