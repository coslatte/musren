# Test each interface and operation

Test from a disposable copy of a few tagged audio files, never from your real
library. Remote operations (lyrics, covers, recognition) contact live services,
so results depend on the network and on the credentials you configured. Covered
operations are rename, covers, albums, albums revert, lyrics, and recognize.

Set up an environment with the extras you want to exercise, as described in
[contributing.md](contributing.md):

```shell
python -m pip install -e ".[dev,tui,lyrics,recognition,musicbrainz,shazam]"
```

`fpcalc` is a separate Chromaprint binary, not a Python extra. Install it and
put it on `PATH` for AcoustID; see
[Configure recognition](../README.md#configure-recognition).

## What each operation needs

| Operation | Python extra | External requirement |
| --- | --- | --- |
| Rename | none | none |
| Covers | none | network access; `musicbrainz` improves matching |
| Albums | none | none |
| Albums revert | none | none |
| Lyrics | `lyrics` | network access |
| Recognize (AcoustID) | `recognition` | `fpcalc` on `PATH` and an AcoustID API key |
| Recognize (Shazam) | `shazam` | network access |

Credentials live in the OS credential store and are shared by the CLI, the TUI,
and the desktop app. Set the AcoustID key once with
`musren config set acoustid YOUR_KEY`, or through the TUI **Configuration** tab
or the desktop settings screen. Legacy plaintext values in `~/.musren/config.json`
are migrated after a successful write and read-back.

## Test the CLI

Check the installed launcher, then run an operation against the test folder:

```shell
musren --version
musren --help
musren rename --directory "test music" --format 2
```

For each operation, confirm the file change and not just the exit code:

| Operation | Command | Expected result |
| --- | --- | --- |
| Rename | `musren rename -d "test music" --format 3 --yes` | New names use the chosen format; the interactive run offers keep or undo |
| Covers | `musren covers -d "test music" --recursive` | Files without artwork get a cover; files that already have one are skipped |
| Albums | `musren albums -d "test music" --recursive` | Album groups move into folders; single tracks move into `Singles` |
| Revert albums | `musren albums revert -d "test music"` | Audio files return from subfolders to the chosen root; no file is overwritten |
| Lyrics | `musren lyrics -d "test music" --recursive` | Synchronized lyrics are embedded in the audio tags |
| Recognize | `musren recognize -d "test music"` | Metadata is updated from AcoustID |
| Recognize (Shazam) | `musren recognize -d "test music" --shazam` | Metadata is updated from Shazam |

`lyrics --recognition --covers` exercises lyrics, recognition, and artwork in one
run and therefore needs all three dependencies. Use `--yes` only after you have
inspected the files in scope. The [CLI reference](cli.md) lists every flag.

The automated suite covers the same workflows with temporary fixtures:

```shell
python -m pytest -q
python -m pytest -q tests/test_rename.py tests/test_workflows.py
```

The suite does not prove live service availability or that your credentials
work. Check those manually with your own files.

## Test the TUI

Launch the installed interface or the checkout shim:

```shell
musren-tui
python app.py --tui
```

Enter the test folder and select an operation. Press **Preview** first to confirm
the file list, then **Run**, and read the per-file results in **Output**. Verify
the same operation results listed for the CLI. Rename asks whether to keep or
undo the changes after a completed run.

Also check the surrounding behavior you will rely on: **Pause**/**Resume**,
**Cancel job**, the **Configuration** tab, and **Include subdirectories**. Folder
browsing with **Browse with fzf** needs `fzf` on `PATH` and a real terminal; the
portable Windows executable does not bundle it. See [the terminal interface
guide](tui.md) for keys and layout.

Headless TUI tests run when Textual is installed:

```shell
python -m pytest -q tests/test_tui.py
```

## Test the desktop app

Run the development app with the worker environment active, as described in
[desktop/README.md](../desktop/README.md):

```sh
cd desktop
source .venv/bin/activate
bun run tauri dev
```

Tauri rebuilds the Python worker and the frontend before launching. Select a
test folder and run the same six operations from the desktop screen; verify the
same results and check that **History** records the completed job and that
**Settings** saves credentials.

To test a built worker without the UI, build the sidecar and run its smoke
check from the repository root:

```shell
python scripts/build_tauri_sidecar.py
python scripts/smoke_tauri_worker.py
```

The smoke check uses disposable files and covers preview, a Unicode path, rename,
and the confirmation reply. `python scripts/smoke_credentials.py` checks the
native credential store on Windows and macOS.

The desktop app reports a missing optional dependency or credential per
operation. To ship an operation, install its extra in the worker environment
before building; PyInstaller only bundles what is installed. AcoustID still needs
`fpcalc` on the target machine.

## Build before you test a package

A test of a packaged artifact is only meaningful after a fresh build. Follow
[building.md](building.md) for the worker, frontend, and Tauri commands, and
[releases.md](releases.md) for the Windows executable and release validation.
