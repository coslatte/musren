"""Windows launcher: TUI by default, with CLI and internal worker modes."""

import multiprocessing
import sys

import app


def main() -> None:
    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--_musren-smoke-test"]:
        import asyncio
        from scripts.verify_windows import smoke_tui

        asyncio.run(smoke_tui())
    elif len(sys.argv) == 1:
        app.tui()
    else:
        if sys.argv[1] == "--cli":
            del sys.argv[1]
        app.main()


if __name__ == "__main__":
    main()
