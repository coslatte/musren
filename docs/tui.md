# Use the terminal interface

Run the portable Windows executable, or launch `musren-tui` from a Python
installation. The [README](../README.md) covers installation. The CLI and
original interactive menu remain available.

## Process a folder

1. Enter a music directory and press Enter, select **Browse with fzf**, or
   select a folder in the browser.
2. Choose an operation and its options.
3. Select **Preview** to inspect the audio files in scope.
4. Select **Run** and confirm the folder and operation.
5. Read the results and per-file errors in **Output**.

Typing a path and pressing Enter moves the **Folders** panel to that path and
runs a preview. **Browse with fzf** hands the terminal to [fzf](https://github.com/junegunn/fzf)
so you can fuzzy-search and pick a folder; it needs `fzf` in PATH, lists the
subfolders of the current directory three levels deep, and the status line
explains what to do when it is missing. Install it with `winget install
junegunn.fzf`, `scoop install fzf`, `choco install fzf`, or your package manager.
The button is unavailable without a real terminal, and the portable Windows
build does not bundle fzf.

Preview scans filenames without modifying files. A preview does not predict
new names or remote matches. To include nested folders, enable **Include
subdirectories**. Album revert always scans subdirectories.

For rename, select the filename format before running. After processing, choose
whether to keep or undo the changes. Track numbers apply when at least three
tracks share an album.

For lyrics, you can enable recognition before the search and fetch artwork at
the same time. Recognition offers AcoustID or Shazam. Covers skips existing
artwork. Albums groups tracks into album folders and Singles; Revert moves audio
files from subfolders back into the chosen root.

## Pause, cancel, or quit

Use **Pause** to suspend processing and **Resume** to continue. **Cancel job**
requests cancellation at the next checkpoint. A current file or network request
can finish first. Batch jobs can finish already submitted files before stopping.

Cancellation keeps completed changes. It does not roll back the job. Rename's
keep or undo dialog appears after a normally completed rename.

Quit during a job requests cancellation and waits for the child process to finish.
The application does not forcibly terminate a process writing audio.

## Manage credentials and preferences

Open **Configuration** to save, load, or delete API credentials. **Clear all**
asks before removing the complete configuration. Credentials remain masked in
the input; the status table indicates which services are configured.

Both interfaces use `~/.musren/config.json`. That local file stores credentials
as plain text. Configuration writes are disabled while a job runs.

Enable **Default recursive scan** to persist the scan preference. **Light theme**
switches between the light and dark themes and persists between sessions.

AcoustID needs an API key and `fpcalc` in PATH. Python installations also need
the corresponding feature extras. Missing dependencies appear in the output
with an installation command; the TUI does not install them during a job.

## Navigate the layout

The form and browser appear side by side on wide terminals. Below 90 columns,
the panels stack in a scrollable workspace. Below 60 columns, job controls use
two rows. The layout is tested from 40×20 to 160×50 and during resizing.

**Folders** browses the filesystem, following the directory you enter. **Files
in scope** lists the preview results. **Output** opens when processing starts.
Configuration and help scroll separately. Job controls remain visible below the
tabs.

| Key | Action |
| --- | --- |
| Tab or Shift+Tab | Move focus |
| Enter or Space | Activate the focused control |
| Ctrl+R | Preview files |
| Ctrl+P | Pause or resume |
| Ctrl+X | Cancel the running job |
| Ctrl+Q | Quit safely |
| F1 | Open help |
| Escape | Decline a confirmation |

See [the CLI reference](cli.md) for command flags and
[the contributor guide](contributing.md) for tests and the code map.
