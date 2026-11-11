# Tauri desktop plan

## Goal and constraints

- Add a Tauri desktop interface for Arch Linux x86_64, Windows 10+, and macOS 11+.
- Keep audio processing in the existing Python core.
- Preserve the CLI and Textual TUI during the desktop rollout.
- Support the six current operations: rename, lyrics, covers, recognize, albums, and revert.
- Keep directory paths intact, including spaces and non-ASCII characters.
- Show preview, progress, per-file errors, and the final process result.
- Ask before file-changing work. Explain that cancellation takes effect at processing checkpoints and completed changes remain.
- Keep service-dependent operations subject to their current optional dependencies and credentials.
- Use one OS-backed credential store through a shared Python CredentialStore for CLI, TUI, and Tauri.

## Phase 0: CLI and TUI audit

Static review identified these issues. The current branch now contains repairs;
runtime regression checks remain pending because the environment lacks the CLI
dependencies.

| Priority | Area | Finding | Repair |
| --- | --- | --- | --- |
| P2 | Interactive CLI | Quoted paths with spaces were split into multiple arguments. | Parse shell input with `shlex`; report unclosed quotes. |
| P2 | Interactive CLI | Non-zero Typer `SystemExit` codes were suppressed. | Keep the menu open and show the failed command and status. |
| P2 | Shared configuration | Invalid JSON could be silently overwritten by the next save. | Preserve the file, report the load error, and require repair or explicit clear before saving. |
| P2 | Shared configuration | Unreadable config files could prevent TUI startup. | Allow startup with a warning; block writes until the file is repaired or explicitly cleared. |

The TUI source and existing tests cover directory selection, preview, operation
arguments, confirmation, process launch errors, and worker controls. Runtime
checks for pause/cancel during real file and network operations remain necessary.
No automated tests were run. A manual shell reproduction could not import the
CLI because the environment lacks `typer`.

## Phase 1: Requirements and engine boundary

### Proposed architecture

Keep the audio and file operations in Python. Add a small application service
that accepts typed job requests and returns structured previews and results.
The CLI, Textual TUI, and Tauri worker become adapters around that service; none
of the frontends parse Rich output or reimplement file-processing policy.

For Tauri, use a Rust job supervisor to launch and control a packaged Python
sidecar. Expose typed Rust commands to the frontend and stream typed job events
back through Tauri events. Rust owns process lifetime and IPC only; Python owns
directory scanning, audio processing, configuration compatibility, and job
results. The frontend should not receive arbitrary shell execution capability.

The current worker already uses JSON messages on stdin/stdout, but combines
machine events with Rich text. The new protocol will reserve stdout for JSONL
and send diagnostics to stderr.

### Python service sketch

```text
JobRequest = RenameRequest | LyricsRequest | CoversRequest |
             RecognitionRequest | AlbumsRequest | RevertRequest

Preview = { directory, operation, total_files, files[] }
JobEvent = Accepted | Progress | ConfirmationRequired | FileResult |
           Warning | Error | Completed
JobResult = { outcome: success | partial | cancelled | failed,
              counts, file_results[], error? }

preview_job(request: PreviewRequest) -> Preview
run_job(request: JobRequest, context: JobContext) -> JobResult
```

`JobContext` provides only progress reporting, confirmation, checkpoint,
pause/resume, and cancellation. Existing `AudioProcessor` and album/artwork
functions remain implementation details of the service.

### Protocol v1 sketch

Rust sends one versioned request per worker process. The request type is
`preview` or `start`, with the selected operation and its validated options:

```json
{"v":1,"type":"start","job_id":"…","request":{"operation":"rename","directory":"…","options":{"recursive":false,"rename_format":"title"}}}
```

Worker stdout events use the same `v` and `job_id`. Event types are `accepted`,
`preview`, `progress`, `confirmation_required`, `file_result`, `warning`,
`error`, and `completed`. Rust sends `pause`, `resume`, `cancel`, or
`confirmation_response` controls over stdin. Credential saving uses a separate
typed one-shot request and never emits the supplied value in a worker event.
Unknown protocol versions fail before any files are changed. Only one active
job is supported in the first release.

Completion distinguishes a successful job, per-file partial failures,
cancellation with completed changes retained, and a process-level failure.
Per-file failures must not be hidden by a zero process exit code. Every
confirmation carries an ID so stale or duplicate answers cannot affect another
operation. A rename job retains the current post-rename keep/revert decision.

### Proposed module map

- `core/jobs.py`: request/result types, preview rules, shared job orchestration,
  and the `JobContext` protocol.
- `core/desktop_worker.py`: JSONL validation, worker events, and controls;
  no Rich formatting.
- `desktop/src-tauri/src/jobs.rs`: sidecar lifecycle, protocol version checks,
  job IDs, controls, and event forwarding.
- `desktop/src/api/jobs.ts`: typed frontend command/event helpers.
- `desktop/src/`: React screens and user interaction only.

The existing Typer commands and Textual runner migrate to the shared Python
service in focused slices so CLI and TUI remain usable throughout.

### Credential storage

All three interfaces use the same Python credential adapter backed by the OS credential store (keyring). The desktop may send a secret once through a typed, in-memory save request to Python; the value is never returned, logged, added to job events/history, or persisted in frontend/config state. Python remains the credential-store boundary. Non-secret preferences remain in the existing config file.

On first use, migrate supported legacy credentials from the JSON config to the OS store. Verify each stored value can be read back before removing its plaintext copy; if migration fails, preserve the source and report the issue. Do not fall back to plaintext storage when the OS store is unavailable or locked. Linux support requires an available Secret Service or KWallet session; show a clear setup error if neither is available.

The selected keyring version requires Python 3.10+ and documents macOS Keychain support on macOS 11+. This raises the supported Python floor for CLI and TUI as well as the desktop worker. Confirm package metadata and user documentation during implementation. See the official [keyring compatibility notes](https://keyring.readthedocs.io/en/stable/) and [project metadata](https://github.com/jaraco/keyring/blob/main/pyproject.toml).

### Operation requirements

| Operation | Inputs | Special behavior |
| --- | --- | --- |
| Rename | directory, recursive, format `artist_title` / `title` / `track_artist_title` | Preview source and destination names; suffix collisions without overwriting or deleting sources; ask whether to keep or revert completed renames. |
| Lyrics | directory, recursive, recognize first, fetch covers | Requires the lyrics extra; recognition and artwork keep their current optional dependencies. |
| Covers | directory, recursive | Report added, skipped, and failed files separately. |
| Recognize | directory, recursive, provider `acoustid` / `shazam` | AcoustID requires `fpcalc` and a key; Shazam keeps its optional extra. |
| Albums | directory, recursive | Resolve filename collisions without overwriting. |
| Revert | directory | Scan nested folders and move audio files to the selected root; report collisions and errors. |

All operations receive an explicit preflight confirmation in Tauri. Preview
uses the exact same scope rules as execution. Pause and cancel take effect at
the next safe checkpoint; an in-flight file or network request can finish, and
completed changes remain after cancellation. Paths stay Unicode strings and
are passed as data, never shell-interpolated arguments.

### Alternatives considered

1. **Frontend launches the sidecar directly with Tauri's Shell plugin.** This
   has less Rust code, but pushes process lifetime, job IDs, confirmation
   routing, and control validation into the webview.
2. **Rust owns a typed job supervisor and launches the sidecar.** This adds a
   small Rust adapter but centralizes process ownership and keeps the frontend
   away from arbitrary command execution.

Choose option 2. It gives the frontend one stable typed API and keeps the
Python worker protocol behind a narrow boundary. Tauri's Shell plugin supports
sidecars and scoped executable/argument permissions; the design will scope it
to the bundled worker. See the official [Shell plugin guide](https://v2.tauri.app/reference/javascript/shell/)
and [Rust command guide](https://v2.tauri.app/develop/calling-rust/).

### Decisions and remaining release defaults

- Frontend: React + TypeScript; keep Tauri commands and event payloads typed.
- First release: all six current operations, delivered in smaller vertical slices.
- Platforms: Arch Linux x86_64, Windows 10+, and macOS 11+.
- Python: 3.10+ for CLI, TUI, and Tauri worker, matching the selected credential
  library's current minimum.
- Credentials: a shared OS-backed store for CLI, TUI, and Tauri, with safe
  migration from legacy plaintext configuration as described above.
- Packages: NSIS installer for Windows, signed/notarized DMG for macOS, and an
  Arch PKGBUILD/pacman package. Decide whether to publish the PKGBUILD to AUR
  during release planning. Debian, Fedora, .deb, .rpm, and AppImage are outside
  the initial support scope; existing artifacts are spike experiments only.

The Tauri spike also produced experimental Debian, Fedora, and AppImage
artifacts. Those are not supported first-release targets. Arch uses a PKGBUILD
that produces a pacman package. See Tauri's [distribution guide](https://v2.tauri.app/distribute/),
[bundle targets](https://v2.tauri.app/reference/config/), and Arch's
[package creation guide](https://wiki.archlinux.org/title/Creating_packages).

**Phase 1 decisions recorded:** service and protocol boundary, shared OS credential
policy, Arch Linux x86_64/Windows 10+/macOS 11+ targets, Python 3.10+, all six
operations, and package targets: NSIS, signed/notarized DMG, and Arch PKGBUILD.

**Deferred to release planning:** whether to publish the Arch PKGBUILD to AUR.
Phase 1 is complete; Phase 2 can begin.

## Phase 2: Cross-platform packaging spike

- Package the Python sidecar and Rust job supervisor for Windows, macOS, and
  Arch Linux.
- Install and launch on the supported operating systems; verify required
  system libraries and credential-store behavior.
- Prototype preview and one reversible file operation on each platform.
- Verify process startup, structured output, cancellation, and packaged paths.

### Current spike results (2026-11-09)

- Created the Bun-managed React/TypeScript and Tauri shell in `desktop/`.
  `bun.lock` is the frontend lockfile; the frontend build passes with
  `bun run build`.
- Added a Rust-owned sidecar supervisor and a versioned JSONL Python worker.
  The current vertical slice intentionally covers rename only; the other five
  operations are not implemented in this spike.
- Built the Linux x86_64 PyInstaller worker and ran
  `desktop/.venv/bin/python ../scripts/smoke_tauri_worker.py`. Preview, a path
  containing Unicode and spaces, rename, and the keep/undo confirmation passed.
- Built Linux `.deb`, `.rpm`, and AppImage bundles on Arch Linux x86_64. The
  AppImage was extracted and its bundled worker passed the Unicode rename smoke.
  This host build is not the glibc compatibility baseline for distribution;
  the workflow builds Linux artifacts on Ubuntu 22.04.
- Added a CI build matrix for Ubuntu 22.04, Windows NSIS, macOS 15 Apple Silicon,
  and macOS 15 Intel. Its Debian 12 and Fedora container jobs install experimental
  packages, smoke the bundled worker, and check that the desktop process stays
  open under Xvfb. These jobs are not support claims for Debian or Fedora. The
  workflow has not run yet, so platform results remain unverified.
- Added an Arch `PKGBUILD` and generated `.SRCINFO`. The package recipe has not
  been built from a clean source checkout. AUR publication remains deferred.
- Added the shared `keyring` credential adapter for CLI, TUI, and the packaged
  Python boundary. It permits native Windows Credential Locker, macOS Keychain,
  Linux Secret Service, and KWallet backends; it rejects fallback/plaintext
  backends. Legacy JSON secrets are removed only after a write/read-back
  succeeds. The local host has no active Linux keyring session, so only the
  clear failure path is available here; successful Secret Service/KWallet,
  Windows, and macOS storage checks still require those sessions/platforms.
- Set the bundle's macOS minimum to 11.0 and aligned the Python entry point with
  the agreed 3.10 minimum.
- Updated project metadata and docs to Python 3.10+, and regenerated `uv.lock`.
- Use Bun for frontend install/build/dev commands. Do not use npm or create an
  npm lockfile.

**Status:** the packaging spike and Linux-host prototype are complete. The
cross-platform release checks are deliberately deferred to Phase 6 and do not
block Phases 3–5.

**Carried to Phase 6:** run the native workflow; build the Arch package from a
clean checkout and install it; verify credential writes on Arch, Windows, and
macOS; confirm packaged startup and operation behavior on all three targets.

**Phase 2 deliverable:** a working Linux-host rename prototype, worker protocol,
and experimental package/build recipes. Windows, macOS, and clean Arch installs
remain unverified until the deferred release checks.

## Phase 3: UX specification

- Define the task-workbench layout and the six operation flows in
  [the UX specification](tauri-ux-spec.md).
- Specify selection, options, preview, configuration, output, confirmation,
  cancellation, and partial-failure states, with keyboard and narrow-window
  behavior. Include dedicated masked secret inputs and persistent local session
  history with exact timestamps and complete per-file change previews.
- Decisions received: workbench layout; pre-run confirmation for all six
  operations; post-rename keep/revert question; safe-checkpoint cancellation
  wording; local OS credential storage through dedicated secret inputs; and
  complete local change history.
- Carry the history data model and credential-entry transport details into
  implementation design; do not expose values in logs, events, or history.

**Status:** complete. The layout, shared flow, all six operation screens,
credential-entry experience, local history, accessibility expectations, and
acceptance criteria are specified in `tauri-ux-spec.md`. The user approved the
workbench, pre-run confirmation, rename keep/revert prompt, and cancellation
behavior; the credential and history requirements are recorded.

**Exit criteria:** approved flows, screen states, and acceptance criteria.
All Phase 3 exit criteria are met. Phase 4 is next; Phase 2 release checks
remain deferred to Phase 6.

## Phase 4: Vertical slice

- Add the Tauri shell and typed frontend-to-Rust commands.
- Connect the worker protocol, directory picker, preview, and one reversible
  operation.
- Verify errors and progress events in the development build.

**Delivered vertical slice:** the React workbench now has a native folder picker,
rename options, a worker-backed source/destination preview, a confirmation
dialog, progress and pause/cancel controls, the post-rename keep/revert decision,
and per-file results. The worker validates a preview token before starting so
changed files require a new preview. Duplicate destination names receive a
numbered suffix; source files are preserved. The Tauri shell permission scopes
`spawn` to the packaged `musren-worker` sidecar with no arguments.

The TypeScript production build, Rust development check, Linux worker build, and
local Linux release application compile pass. The release compile used
`tauri build --no-bundle`, which validated the app without producing unsupported
Debian/RPM/AppImage artifacts. The user confirmed that the initial `tauri dev`
window rendered correctly and the application works well. On the follow-up run,
`bun run tauri dev` started Vite successfully (`localhost:1420` returned HTTP
200) and created the native window. Later direct launches of the Rust executable
did not start Vite and therefore were not valid frontend checks.

**Status:** complete. The user confirmed the application is working well, and
the development launch, frontend server, worker build, and local app compilation
were verified. Cross-platform package checks remain deferred to Phase 6.

**Exit criteria:** the rename vertical slice is available in the development
app with preview, confirmation, progress, cancellation, and keep/revert handling.
The user confirmed the app works well. Phase 4 is complete; Phase 5 can begin.

## Phase 5: Feature completion

Implement the agreed features as reviewable vertical slices, keeping Python as
the owner of operation policy and using the typed Rust/worker boundary for
process control and events.

**Status:** complete for the agreed development-app scope. Python owns the
validated operation plans and execution policy; the Rust shell supervises the
worker and forwards typed events. All six operations have preview, a fresh-plan
check before execution, confirmation, progress, safe cancellation, results,
and durable local history.

1. **Shared job and history model:** all six operations now share a validated
   request/event/result contract. Versioned SQLite history records UTC
   microsecond timestamps, operation options, outcomes, counts, and ordered
   before/planned/actual snapshots. Starting a job recalculates its preview and
   rejects stale plans. History and secret values are excluded from job events.
2. **Credential settings:** Settings has a password-style AcoustID input and
   explicit reveal control while typing. Save and delete use the existing
   system credential store shared with CLI/TUI. After save the UI shows only
   configured/masked status; there is no plaintext fallback.
3. **Filesystem operations:** Albums previews safe destination paths and adds
   numbered names for conflicts; Revert scans nested folders, previews root
   destinations, and leaves conflicting files where they are.
4. **Service-backed operations:** Covers, Recognize (AcoustID or Shazam), and
   Lyrics (optional recognize-first and cover-fetch steps) run through the same
   worker contract with per-file results and dependency errors.
5. **History experience and integration:** History lists sessions newest first,
   filters by local date, operation, outcome, and folder, and shows exact local
   time plus ISO timestamp. Session detail shows options and each file's before,
   planned, and actual state. A rename undo is a separate linked `revert`
   session. History can be cleared without changing audio.

After each slice, check its frontend types/build, worker protocol, and affected
Python behavior before starting the next one. Keep release packaging checks for
Arch Linux, Windows, and macOS in Phase 6.

**Exit criteria:** met for the development app. Cross-platform packaging and
credential-store behavior on Arch Linux, Windows, and macOS remain in Phase 6.

**Carried decisions for Phase 6:** history currently records cover presence,
not image thumbnails. The first release will retain this behavior: it will not
copy artwork into history. This avoids duplicate local image storage; history
shows whether artwork was present, while the processed audio file remains the
source for the current cover. CLI/TUI behavior was not changed by the desktop
operation adapters.

## Phase 6: Release readiness

- Build the Arch package with all declared `makepkg` dependencies installed and
  verify pacman installation/removal on a clean Arch system.
- Build and install the Windows NSIS and macOS DMG packages on their native
  systems; verify startup, permissions, credential storage, and failure paths.
- Verify that macOS signing/notarization and Windows installer signing are
  configured before publishing public release artifacts.
- Exercise packaged optional operations and document their external
  dependencies, including `fpcalc` for AcoustID.
- Publish platform-specific installation instructions and release checks.

**Progress:** workflow run 43046242659 passed for commit 1dfa845. The Arch job
resolved all declared build dependencies in a clean Arch Linux container,
built the pacman package from that exact commit, installed it with `pacman`,
kept the installed app running for the 15-second smoke interval under Xvfb and
removed it. The Windows NSIS installer and macOS DMGs for Apple Silicon and
Intel also installed or mounted on native runners and their apps stayed open
for the smoke interval. All three targets passed the worker smoke path and a
disposable native credential write/read/delete check where supported. The
workflow uploaded all four artifacts (Arch, Windows, macOS Apple Silicon, and
macOS Intel); see the [workflow run](https://github.com/coslatte/musren/actions/runs/43046242659).
The first macOS Intel DMG attempt hit a transient `hdiutil: Resource busy`
while ejecting its temporary image; retrying that job passed. General CI passed
across Windows/Linux with Python 3.10, 3.11, and 3.13 (run 43038822244). The
release matrix contains only the agreed Arch, Windows, and macOS targets;
Debian, Fedora, and AppImage are outside the supported scope.

Still needed before a public release: exercise packaged optional operations and
failure paths, configure Windows installer signing and macOS signing/notarization,
and publish platform-specific installation instructions. No signing Actions
secrets are configured. Artifacts from the workflow are validation outputs and
are not yet signed release deliverables.

**Exit criteria:** verified release artifacts and user-facing installation docs.
