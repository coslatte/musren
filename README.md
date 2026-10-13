# musren

Organize a local music library from a terminal. musren renames audio files from
their metadata, fetches lyrics and artwork, recognizes tracks, and groups albums
into folders. Use the terminal interface or the existing CLI.

## Run on Windows

Download [musren-windows-x64.exe](https://github.com/coslatte/musren/releases/latest/download/musren-windows-x64.exe)
and double-click it to open the TUI. Python and the optional Python dependencies
are bundled. No installer is required.

The executable also accepts CLI commands:

```powershell
.\musren-windows-x64.exe rename --directory "C:\Music"
.\musren-windows-x64.exe --cli
```

Release packages and checksums are available on the
[GitHub Releases page](https://github.com/coslatte/musren/releases).

## Install with Python

The TUI requires Python 3.9 or newer. CLI-only installations support Python 3.8.
From a source checkout, install the interface and launch it:

```shell
python -m pip install ".[tui]"
musren-tui
```

Add the optional features you need:

```shell
python -m pip install ".[tui,lyrics,recognition,musicbrainz]"
python -m pip install ".[tui,shazam]"
```

For an isolated development environment, follow [the contributor guide](docs/contributing.md).

## Use your music library

In the TUI, choose a folder and an operation. Select **Preview** to inspect the
files in scope, then **Run** to confirm the operation. The **Output** tab shows
progress, results, and per-file errors. Rename offers a choice to keep or undo
the changes.

| Operation | Result |
| --- | --- |
| Rename | Names from artist, title, and optional album track numbers |
| Lyrics | Synchronized lyrics embedded in the audio file |
| Covers | Album artwork embedded; existing artwork is skipped |
| Recognize | Metadata from AcoustID or Shazam |
| Albums | Tracks grouped into album folders and Singles |
| Revert albums | Audio files moved from subfolders back to the selected root |

The CLI supports the same workflows:

```shell
musren rename --directory "Music collection" --format 2
musren lyrics --directory "Music collection" --recursive
musren covers --directory "Music collection" --recursive
musren albums revert --directory "Music collection"
musren --help
```

Running `musren` without arguments opens the original interactive menu.

## Configure recognition

AcoustID requires an API key and the external Chromaprint `fpcalc` binary. Set
the key in the TUI's **Configuration** tab or use the CLI:

```shell
musren config set acoustid YOUR_KEY
```

Install `fpcalc` and make it available in PATH. Windows binaries are available
from [Chromaprint releases](https://github.com/acoustid/chromaprint/releases).
On macOS, use `brew install chromaprint`. On Debian or Ubuntu, use
`sudo apt-get install libchromaprint-tools`.

Both interfaces share `~/.musren/config.json`. The TUI masks credentials; the
local configuration file stores them as plain text.

## Documentation

| Guide | Contents |
| --- | --- |
| [Terminal interface](docs/tui.md) | Forms, keyboard controls, previews, and cancellation |
| [CLI reference](docs/cli.md) | Commands, flags, formats, and configuration |
| [Contributing](docs/contributing.md) | Environment setup, repository map, and checks |
| [Releases](docs/releases.md) | Package builds, Windows executable, and publishing |
| [Changelog](docs/changelog.md) | Changes by version |

Project metadata, dependencies, build settings, and Ruff rules live in
`pyproject.toml`. Detailed guides live in `docs/`; helper scripts live in
`scripts/`. The repository's root keeps the application entry point and standard
project files.

Licensed under [MIT](LICENSE).
