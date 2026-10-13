# Terminal interface

The TUI is an optional interface over the existing commands. The command line
and original interactive menu remain available.

## Install and launch

The TUI requires Python 3.9 or newer. CLI installations still support Python 3.8.

```powershell
py -3 -m pip install -e ".[tui]"
musren-tui
# Or launch from the checkout:
py -3 app.py --tui
```

Install the extras you need for network workflows:

```powershell
py -3 -m pip install -e ".[tui,lyrics,recognition,musicbrainz]"
# Shazam is an alternative to AcoustID:
py -3 -m pip install -e ".[tui,shazam]"
```

AcoustID requires an API key and the Chromaprint `fpcalc` binary. Missing
dependencies appear in the job output with an installation command. The TUI
does not install them during a job.

## Use the library screen

1. Enter a directory, or select a folder in the directory tree.
2. Choose an operation and its options.
3. Select **Preview** to list audio files in scope. Preview only scans filenames.
4. Select **Run** and confirm the directory and operation.
5. Review the output summary and per-file errors when the command finishes.

| Operation | Options and behavior |
| --- | --- |
| Rename | Artist/title, title only, or track/artist/title; recursive scanning; dialog to keep or undo changes |
| Lyrics | Recursive scanning; optional recognition first; optional artwork |
| Covers | Recursive scanning; existing artwork is skipped |
| Recognize | Recursive scanning; AcoustID or Shazam |
| Albums | Recursive scanning; groups albums and singles; preserves files when names collide |
| Revert albums | Finds audio files in subfolders and moves them to the root; preserves filename collisions |

Track numbers are included by the existing rename engine when at least three
tracks share an album. Preview does not predict new names or network matches.

Pause and cancellation are cooperative. They take effect at a processing
checkpoint. A current file or network request may finish first. Batched network
jobs can finish already submitted files before stopping. Cancellation keeps
completed changes; it does not roll back a job. Rename's keep/undo dialog is
available after a normally completed rename job.

Quit during a job requests cancellation and waits for the child process to
finish. The application does not forcibly terminate a process writing audio.

| Key | Action |
| --- | --- |
| Tab / Shift+Tab | Move focus |
| Enter / Space | Activate a focused control |
| Ctrl+R | Preview files |
| Ctrl+P | Pause or resume |
| Ctrl+X | Cancel the running job |
| Ctrl+Q | Quit safely |
| F1 | Open help |
| Escape | Decline a confirmation |

The layout is tested from 40×20 to 160×50 terminals and during live resizing.
Below 90 columns the form and browser stack in a scrollable workspace. Below
60 columns the persistent job controls use two rows. Larger terminals show the
form and browser side by side. Output has its own tab and opens when a job starts.
Preview opens the browser's file list. Configuration and help scroll independently.

## Configuration

The Configuration tab uses the same `~/.musren/config.json` file as the CLI.
Save, load, and delete individual API credentials, or confirm **Clear all**.
Credentials remain masked in the input field and are not printed in the TUI.
The local configuration file stores them as plain text.

The default recursive scan and light/dark theme persist between sessions.
Configuration writes are disabled while a job runs.

## CLI compatibility

```powershell
musren                              # Original interactive menu
musren --help                       # Command-line help
musren rename --directory "C:\Music collection" --format 2 --yes
musren albums revert --directory "C:\Music collection" --yes
```

Both interfaces use `core/cli/commands/`. The TUI builds argument lists in
`core/tui/jobs.py`, runs an isolated child through `core/tui/runner.py`, and
owns widgets and the job lifecycle in `core/tui/app.py`. JSON messages carry
confirmations and cooperative pause/resume/cancel commands. CLI code and the
audio engine have no dependency on Textual. Textual loads only when launching
the TUI.

A thread calling CLI handlers in the UI process was considered. It would share
global console output and the keyboard listener with the UI. The child process
keeps those resources separate while preserving the existing command behavior.

## Verification

```powershell
py -3 -c "import app; import core.tui; import core.audio_processor"
py -3 -m pytest -q
py -3 -m ruff format .
py -3 -m ruff check .
```

Install the `tui` extra to run the headless widget tests. Without that extra,
widget tests skip; command and engine tests still run. Tests create disposable
tagged MP3 fixtures, verify actual filenames and metadata, and replace remote
services with controlled responses. They do not contact recognition, lyrics,
or artwork services. Live service availability and account credentials require
a separate check with your own files and credentials.
