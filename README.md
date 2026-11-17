# musren

Organize a local music library with musren's desktop app, terminal interface, or
CLI. musren renames audio files from their metadata, fetches lyrics and artwork,
recognizes tracks, and groups albums into folders.

## Preview

![preview](assets/demo-image-2026.jpg)

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

## Desktop app

The Tauri desktop app provides the same six operations with a folder picker,
preview, confirmation, progress, pause and cancel controls, per-file results, and
local history. Rename keeps the keep-or-undo decision. Settings stores the
AcoustID key in the OS credential store, and Appearance switches between the
Kanagawa Lotus (light) and Wave (dark) themes, or follows the system theme.

Build it from a source checkout:

```shell
python3 -m venv desktop/.venv
desktop/.venv/bin/python -m pip install -e '.[desktop,lyrics,recognition,musicbrainz,shazam]'
source desktop/.venv/bin/activate
cd desktop
bun install --frozen-lockfile
bun run tauri build --bundles deb   # Windows: nsis, macOS: dmg
```

The PyInstaller worker bundles only the extras installed in that environment;
`fpcalc` remains an external requirement for AcoustID. The worker, frontend,
native executable, and installer paths are listed in
[Building from source](docs/building.md).

### Install on Arch Linux

The AUR package `musren-desktop-git` is prepared but not published yet. Until it
is available, build the pacman package from the recipe in `packaging/arch`:

```shell
cd packaging/arch
makepkg -si
```

The recipe builds from the upstream `main` branch. Review the
[`PKGBUILD`](packaging/arch/PKGBUILD) before installing it. Windows and macOS
desktop packages are built on their native systems; see the
[desktop guide](desktop/README.md).

## Install with Python

The CLI and TUI require Python 3.10 or newer.
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
the key in the TUI's **Configuration** tab, the desktop **Settings** screen, or
the CLI:

```shell
musren config set acoustid YOUR_KEY
```

Install `fpcalc` and make it available in PATH. Windows binaries are available
from [Chromaprint releases](https://github.com/acoustid/chromaprint/releases).
On macOS, use `brew install chromaprint`. On Debian or Ubuntu, use
`sudo apt-get install libchromaprint-tools`.

The CLI, TUI, and desktop app share the OS credential store: Secret Service or
KWallet on Linux, Windows Credential Locker, and macOS Keychain. The TUI and
desktop settings mask the value after entry. Legacy plaintext values in
`~/.musren/config.json` are removed only after a successful write and read-back.

## Documentation

| Guide | Contents |
| --- | --- |
| [Terminal interface](docs/tui.md) | Forms, keyboard controls, previews, and cancellation |
| [CLI reference](docs/cli.md) | Commands, flags, formats, and configuration |
| [Testing](docs/testing.md) | Checks for the CLI, TUI, and desktop app, per operation |
| [Building from source](docs/building.md) | CLI/TUI install, desktop worker, frontend, Tauri, and artifact paths |
| [Contributing](docs/contributing.md) | Environment setup, repository map, and checks |
| [Releases](docs/releases.md) | Package builds, Windows executable, and publishing |
| [Changelog](docs/changelog.md) | Changes by version |

Project metadata, dependencies, build settings, and Ruff rules live in
`pyproject.toml`. Detailed guides live in `docs/`; helper scripts live in
`scripts/`. The repository's root keeps the application entry point and standard
project files.

Licensed under [MIT](LICENSE).
