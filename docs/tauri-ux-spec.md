# Tauri UX specification

**Status:** approved UX specification; Phase 3 complete. Implementation details
for secret transport and history persistence are tracked for Phases 4–5.

## Product scope

The first desktop release targets Arch Linux x86_64, Windows 10+, and macOS
11+. It exposes the existing six operations through a Tauri desktop shell:
rename, lyrics, covers, recognize, albums, and revert. Python remains the
source of operation behavior and credential access. The desktop interface
shows progress, results, and non-secret configuration status.

The primary user task is to select a folder, choose an operation, inspect the
planned effects, confirm changes, and review the result. Users may repeat this
workflow across folders; the interface does not need to present a permanent,
indexed music library.

## Layout options

### Option A: Task workbench (recommended)

```text
┌ Musren ───────────────────── Selected folder: /Music/Album  [Choose] [⚙] ┐
│ Operations     │ Rename files                                             │
│  Rename        │ Format [Artist - Title      ▾]  [ ] Include subfolders    │
│  Lyrics        │                                                           │
│  Covers        │ Preview                                                   │
│  Recognize     │ Current name                 → New name                    │
│  Albums        │ 01 track.mp3                 → Artist - Track.mp3           │
│  Revert        │ 02 track.mp3                 → Artist - Track 2.mp3         │
│  History       │                                                           │
│                │                                                           │
└────────────────┴──────────────────────────────────── [Preview] [Run Rename]┘
```

The operation list stays available while the selected folder, options, and
preview remain in the main work area. A persistent action row makes the
preview and execution steps easy to find.

### Option B: Guided wizard

```text
┌ Step 2 of 4: Choose operation ───────────────────────────────────────────┐
│ Folder  ✓       Operation  ●       Options  ○       Review  ○             │
│ Select one operation, then continue to its settings.                      │
│ [Rename] [Lyrics] [Covers] [Recognize] [Albums] [Revert]                  │
│                                                   [Back] [Continue]       │
└───────────────────────────────────────────────────────────────────────────┘
```

This makes first-time use explicit, but adds steps to a repeatable batch task.

### Option C: Music library dashboard

```text
┌ Library ─────────────────────────────── [Add folder] [Search] [Settings] ┐
│ Recently processed                 Albums                                │
│ Folder A · 128 files                Cover  Artist  Album                 │
│ Folder B · 42 files                 ...                                   │
│                                                                      ... │
└───────────────────────────────────────────────────────────────────────────┘
```

This prioritizes browsing and a persistent collection. It suggests library
management and indexing behavior beyond the current operations.

### Decision proposal

Choose Option A. It matches the folder-based batch workflow and keeps each
operation's preview close to its settings. The wizard remains a possible
first-run guide, and the dashboard is out of scope unless persistent library
management becomes a requirement.

## Workbench structure

- **Header:** app name, selected folder path, `Choose folder`, and settings.
- **Operation navigation:** Rename, Lyrics, Covers, Recognize, Albums, Revert,
  and History.
- **Main panel:** operation name and short explanation, operation-specific
  options, then the preview or current job activity.
- **Action row:** `Preview` and an operation-specific action such as
  `Run Rename`. Disable actions when the folder or required inputs are invalid.
- **Window:** target a comfortable default around 1000 × 700 CSS pixels. At
  narrow sizes, collapse the operation list into a selector and stack the
  options and preview. Do not hide essential actions behind hover.

Use visible keyboard focus, logical tab order, accessible names for controls,
and reduced-motion-aware transitions. Status and errors must be conveyed with
text and not color alone.

## Shared interaction flow

1. **No folder:** prompt the user to choose a folder. Do not start a scan.
2. **Folder selected:** show the full path and allow changing it.
3. **Operation selected:** show only relevant options and preserve other
   operation settings while navigating within the current session.
4. **Preview requested:** show a loading state; keep the user able to cancel
   the scan. If the scan fails, explain the failure and offer a retry.
5. **Preview ready:** show the affected-file count and concrete planned changes
   where applicable. An empty preview explains why there is nothing to do.
6. **Run requested:** show a confirmation containing the operation, folder,
   affected count, and representative effects. Starting a job requires explicit
   confirmation.
7. **Running:** show current phase, file when available, completed/total count,
   and pause/resume/cancel controls where supported. Explain that an in-flight
   file or network request may finish and completed changes remain after
   cancellation.
8. **Finished:** show success, partial success, cancellation, or failure with
   counts and per-file errors. Do not describe partial success as total success.

The preview and execution must use the same scope rules. Preserve paths with
spaces and Unicode as path data throughout the workflow.

### State model and edge cases

```text
No folder → Ready → Previewing → Preview ready → Confirming → Running
                         ↘ Preview error             ↙        ↘
                                                   Cancelled  Completed
                                                              Partial / Failed
```

- Changing the folder or any option invalidates the current preview. The run
  action stays disabled until a fresh preview succeeds.
- A zero-item preview explains the reason when known and disables execution.
- While previewing, allow the user to cancel. Do not present scan cancellation
  as cancellation of a running file operation.
- During a job, disable changing the folder and operation. Keep job state
  visible if the user navigates to settings or another view.
- Pause and resume are shown only when the worker supports them. Cancellation
  is available at safe checkpoints; clearly label work already completed.
- Rename has a second decision after processing: keep the new names or revert
  the completed renames. Do not imply that closing the window automatically
  chooses either outcome.
- If the app closes or the worker exits unexpectedly, report that the final
  state may be incomplete and show the last known completed-file count on the
  next launch if job recovery is supported. Otherwise, do not promise recovery.

## Local change history

History is a first-release workflow, not only a temporary completion screen.
Each processed job creates a local session record that the user can open later.
It is an audit and preview of changes; it does not imply that every operation
can be undone. Rename keeps its explicit keep/revert choice.

### History list and session detail

The History view lists sessions newest first. Each row shows the exact start
date and time in the user's local timezone, operation, folder, outcome, and
counts. Session detail shows start and finish times, the options used, and a
complete per-file list grouped by changed, unchanged/skipped, and failed.
Provide filtering by date, operation, outcome, and folder; opening a session
must not rerun it.

Show the timezone with the timestamp and provide an ISO 8601 timestamp in
details so the event is unambiguous. Distinguish the original preview from the
actual result: a planned change can be skipped or fail, and both must remain
visible in the history.

For each changed item, show the before and after values relevant to the
operation: old/new path or filename, metadata fields, lyrics content, cover
presence, or album destination. Preserve the values as they were at the time of
the job so later edits do not rewrite the historical view. Do not duplicate
full audio files or artwork images. The first release records whether cover
art was present; it does not preserve an image preview.

Keep records and artwork snapshots on the device. Never include credentials in
history. Show the storage location in settings and provide a clear-history
action with confirmation. Clearing history does not change the processed
files. A history entry for a revert is a new session linked to the original
rename session, not deletion of the original record.

### History acceptance criteria

- Every job that starts creates a session record, including cancelled, failed,
  and partially successful jobs; if startup fails before any work begins, show
  that outcome consistently.
- A session preserves exact local start/finish timestamps plus timezone and
  ISO 8601 details.
- The stored preview and per-file result make planned and actual changes
  distinguishable, including skips, failures, and partial completion.
- History shows the before/after values and cover-art presence as they existed
  when the operation ran, without storing audio files, artwork images, or
  secrets.
- History stays local, is browsable after restarting the application, and can
  be cleared without modifying audio files.
- A rename revert appears as a linked session while preserving the original
  operation record.

## Operation-specific screens

| Operation | Options and preview | Result details |
| --- | --- | --- |
| Rename | Format (`artist_title`, `title`, or `track_artist_title`), recursive toggle; show current and proposed names, including numbered suffixes for destination collisions. | Preserve existing files, summarize renamed and failed files, then ask whether to keep the changes or revert them. |
| Lyrics | Recursive toggle, recognize-first, fetch-covers options; show file count and dependency/key readiness. | Summarize lyrics added, skipped, and failed; identify missing optional dependencies or credentials with a next step. |
| Covers | Recursive toggle; show eligible files and existing-cover handling. | Report covers added, skipped, and failed separately. |
| Recognize | Recursive toggle and provider (`acoustid` or `shazam`); show required `fpcalc`, key, or optional-extra readiness. | Report recognized, skipped, and failed files, including actionable prerequisite errors. |
| Albums | Recursive toggle; preview destination folders and name collisions. | Report moved/organized and failed files; never overwrite filename collisions. |
| Revert | Scan nested folders; preview audio files that will move to the selected root and any collisions. | Report moved and failed files, and keep collisions in place. |

## Credentials and settings

Provide a dedicated password-style input for each supported secret, with an
optional brief reveal action while the user is entering it. After saving,
display only a masked value or “Configured”; never retrieve a saved value just
to show it again. A user may keep their own private TXT notes outside the app,
but the app does not read those files or store secrets in ordinary text files.

On save, send the secret only through the in-memory credential command to the
Python credential adapter, which stores it in the native OS credential store
(Windows Credential Locker, macOS Keychain, or Linux Secret Service/KWallet).
The operating system protects the stored value locally. Do not implement a
custom encryption scheme or use the app config file as a fallback. Clear the
input after the save result. Do not put secret values in webview persistence,
Rust logs, worker events, job history, crash messages, or analytics. Show only
the configured/missing status and actionable storage errors.

Settings may show non-secret preferences and dependency status. Clearly
separate optional-feature prerequisites from errors that prevent all use.

## Acceptance criteria

- Each of the six operations has its own options, preview content, and result
  summary as described above.
- The user sees the selected folder and affected-file count before confirming
  any file-changing job.
- An invalid folder prevents preview and execution with a clear explanation.
- Preview scope matches execution scope, including recursive selection and
  collision rules.
- Paths with spaces and Unicode work from folder selection through completion.
- Running jobs expose progress and supported controls; completion and
  cancellation report completed work and per-file errors accurately.
- Missing optional dependencies and credentials show actionable guidance.
- Secret entry uses dedicated masked inputs; saved values are not retrievable
  through the interface and never appear in configuration, events, logs, error
  text, or history.
- Credentials are stored through the native OS credential store; failure to
  access it blocks saving and never falls back to plaintext.
- History records every job locally with exact timestamps and a complete,
  durable per-file preview of actual changes.
- All workflows can be operated with a keyboard, have visible focus, and remain
  understandable with reduced motion and without color cues.
- The layout remains usable in a narrow window without clipping essential
  actions or status.

## Decisions recorded for Phase 3

- **Approved:** Option A, the task workbench.
- **Approved:** explicit confirmation before all six operations.
- **Approved:** ask after rename whether to keep or revert the changes.
- **Approved:** explain safe-checkpoint cancellation and that completed work
  remains.
- **Specified:** dedicated secret inputs; store locally via the native OS
  credential store, show masked status after saving, and never persist secrets
  in ordinary files or expose them in logs/events/history.
- **Added to scope:** persistent local history with exact timestamps and a
  complete before/after preview of per-file changes.

The UX requirements are complete. Secret transport and history persistence
remain implementation work for Phases 4–5. Phase 2 platform checks remain
deferred to Phase 6.
