import sys
import warnings

from constants.info import MUSIC_RENAMER_VERSION


def main(interactive: bool = True) -> None:
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
        from core.cli.shell import cli as musren_shell

        musren_shell()
    else:
        if len(sys.argv) > 1:
            from core.cli.app import cli

            cli()
        else:
            from core.cli.shell import InteractiveShell

            shell = InteractiveShell()
            shell.run()


def tui() -> None:
    """Launch the optional terminal interface without importing it for CLI use."""
    if sys.version_info < (3, 9):
        raise SystemExit(
            "The TUI requires Python 3.9 or newer. The CLI supports Python 3.8."
        )
    try:
        from core.tui.app import MusrenApp
    except ModuleNotFoundError as error:
        if error.name != "textual":
            raise
        raise SystemExit(
            'TUI dependency missing. Install: pip install ".[tui]"'
        ) from error
    MusrenApp().run()


if __name__ == "__main__":
    main()
