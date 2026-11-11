# Repository refactoring plan

Status: complete on `refactor/repository-architecture`. All six planned stages
are complete and validated on the current Linux environment.

Refactor musren incrementally so that CLI, Textual TUI, and Tauri desktop use the
same audio operations. Keep the current commands, supported formats, optional
features, worker controls, and distribution targets. Each stage must leave a
usable application and a locally verifiable result.

## Current responsibilities and problems

The existing system already has useful boundaries. Reuse the rename preview
service, credential store, history store, lyrics provider chain, and Rust worker
supervisor. The main problem is that these boundaries are not consistent across
the interfaces.

| Evidence in the current checkout | Maintenance consequence | Planned correction |
| --- | --- | --- |
| `src/musren/core/audio_processor.py` combines provider lookup, metadata writes, and batch execution in `AudioProcessor`. | A change to one operation requires understanding several unrelated paths. | Continue extracting cohesive operations, audio I/O, and provider calls. |
| `src/musren/core/jobs.py` provides shared rename requests and previews, while CLI commands previously constructed `AudioProcessor` directly. | Frontends once coordinated the same operation differently. | Migrate every rename caller to one application contract. |
| CLI and desktop previously planned or executed album moves separately. | Collision handling and grouping policies could diverge. | Give album planning and movement one owner. |
| `src/musren/core/tui/runner.py` still adapts CLI prompts and Rich progress inside its child process. | TUI processing depends on CLI presentation internals. | Keep process isolation and replace runtime patching with explicit job callbacks and controls. |
| Desktop previously called the private `AudioProcessor._process_file` method. | Desktop depended on engine implementation details. | Expose an application operation used by every frontend. |
| `ConfigManager` lives in `core/cli/config.py` and is imported by the TUI. | Shared preferences appear to belong to a particular interface. | Move configuration ownership outside the CLI. |
| `utils/tools.py` contains file discovery, keyboard pause handling, network checks, and presentation helpers. | Unrelated dependencies travel together. | Move each responsibility to its actual consumer or owner. |
| `core/cli.py`, `core/cli_typer.py`, and `core/cli/` coexist. The first declares itself deprecated. | The supported entry path is harder to identify. | Verify callers, imports, installers, and documented invocations before deleting obsolete implementations. |
| `desktop/src/App.tsx` contains operation interaction, history, and settings screens. | Screen changes share a large stateful component. | Extract screens and job state where they have distinct responsibilities. |
| The sidecar builder collects `musren.core` from `src/` and uses the packaged worker entry file. | Moving Python directories can break installed applications even when checkout imports work. | Keep artifact verification tied to the installed package layout. |

These findings describe inspected paths, not a proof that every duplicate or
legacy caller has been found. Repeat caller searches before each removal.
See the existing [desktop plan](tauri-plan.md) for protocol and control decisions
that this refactor must preserve.

## Proposed structure

Use one Python package under `src/`, retain `desktop/` as the desktop application,
and retain the current documentation and distribution directories.
This tree is a target, not the current layout. Add files only when their extracted
responsibility exists.

```text
src/musren/
  __init__.py
  __main__.py
  version.py
  config.py
  credentials.py
  history.py
  dependencies.py
  operations/
    models.py
    jobs.py
    rename.py
    albums.py
    enrichment.py
  audio/
    files.py
    metadata.py
    artwork.py
  providers/
    recognition.py
    shazam.py
    lyrics.py
    artwork.py
  interfaces/
    cli/
    tui/
    worker/
      protocol.py
      main.py
desktop/
  src/
    App.tsx
    api/
    features/
      jobs/
      history/
      settings/
  src-tauri/
tests/
  unit/
  integration/
  contracts/
  ui/
docs/
scripts/
packaging/
.github/workflows/
```

Leave project metadata, lockfiles, license, README, and `AGENTS.md` at the root.
Keep build scripts in `scripts/` and native packaging definitions in `packaging/`.
Do not introduce a workspace tool or move `desktop/` merely to create an `apps/`
directory. Classify tests by behavior as they change, rather than moving all tests
for visual symmetry.

`operations/` owns requests, planning, execution, progress, cancellation
checkpoints, and results. `audio/` owns local file discovery and audio reads and
writes. `providers/` owns remote lookups and provider-specific responses.
Configuration, credentials, and history remain concrete modules with one owner.
`interfaces/` owns parsing, rendering, process communication, and UI interaction.

Keep one module per cohesive responsibility. Split a provider or audio format
only when its code or dependencies justify a separate file. Avoid a class per
command, generic repositories, dependency-injection containers, and wrappers that
only forward calls.

### Allowed dependencies

```text
CLI / TUI / Python worker -> operations -> audio / providers
                                    -> config / credentials / history as needed
React -> typed Tauri API -> Rust supervisor -> Python worker
```

Audio and provider modules must not import Typer, Rich, Textual, or interface
modules. Remote lookups return metadata or content; they do not decide where to
move files. The application owns when to consult preferences, retrieve secrets,
record history, and execute an operation. Rust owns child processes and IPC.
React owns interaction and rendering. Neither duplicates Python processing rules.

### Shared application contract

Start from the existing `RenameRequest`, preview token, operation parser, and
worker events. Define operation-specific request variants instead of expanding
an unvalidated options dictionary.

```text
request = RenameRequest(directory, recursive, rename_format)
preview = prepare_operation(request, context)
result = execute_operation(request, preview, context)
```

The names are design sketches. During extraction, preserve existing public
commands and wire payloads while choosing precise internal signatures.

| Concept | Owner and contract |
| --- | --- |
| Operation request | `operations/models.py`. Validated rename, lyrics, covers, recognition, albums, and revert variants with their actual options. |
| Preview | An ordered plan of file actions plus the existing review token. Define which operations can predict exact mutations and which require remote results. |
| Job context | Explicit event callback, checkpoint, and confirmation callback. No terminal widgets or transport messages. Default synchronous controls support ordinary CLI execution. |
| File result | Explicit changed, unchanged, skipped, or failed result with the affected paths and reason. |
| Job result | Existing supported outcomes, counts, retained changes, and rename undo information. Preserve protocol distinctions such as `reverted`. |
| History | `history.py` persists sessions. Shared orchestration decides lifecycle timing while retaining current interface behavior until history parity is an explicit decision. |
| Worker protocol | `interfaces/worker/protocol.py` translates versioned JSONL messages and application events. Existing Rust types and Zod schemas remain boundary validators. |

For rename, the interface presents a preview, obtains the required decision, and
passes the reviewed token to execution. The operation checks for stale input,
applies collision policy, emits file results, and returns the undo mapping.
The interface renders the keep/revert question, while the application owns undo.
For enrichment, providers return recognized metadata, lyrics, or artwork and the
audio module writes the supported tags.

Keep mandatory file-change confirmation distinct from the later keep/revert
decision. Adapt current CLI and TUI prompts explicitly during migration. Do not
silently impose desktop-only interaction on noninteractive commands.

### Alternatives considered

| Design | Tradeoff | Decision |
| --- | --- | --- |
| Move current files into named folders without changing callers. | Small mechanical change, but retains separate frontend orchestration and private-method coupling. | Useful only as a later package-move step. |
| One shared operations package with concrete audio, provider, and interface modules. | Requires caller migration, but processing rules have one owner without a framework of abstractions. | Recommended. |
| Separate domain, application, ports, infrastructure, and adapter packages for every feature. | Makes boundaries explicit but adds interfaces and forwarding layers before this application needs them. | Defer additional layers until a real second implementation requires them. |

## Delivery sequence

Use `refactor/repository-architecture` for local integration. Keep changes focused
and reviewable. Do not combine policy changes, directory moves, and UI redesign
in one patch. Finish validation for each slice before starting the next.

| Stage | Work and affected paths | Exit criteria |
| --- | --- | --- |
| 1. Establish the baseline | Inventory CLI aliases, shell behavior, TUI controls, desktop protocol, optional extras, stored data paths, and release artifacts. Inspect `tests/`, smoke scripts, and build definitions. Record differences between frontend behavior. | Reproducible local test environment, import checks, full suite, representative worker smoke test, and recorded skips or failures. Add characterization tests only for behavior exposed to migration risk. |
| 2. Separate shared support | Extract configuration from `core/cli/config.py`. Separate audio discovery, terminal controls, connectivity checks, progress formatting, and provider logging from `utils/tools.py`. Keep credentials and history concrete. | Complete. Shared configuration lives in `core/config.py`. `utils/tools.py` has been removed. CLI pause and progress helpers, connectivity checks, logging policy, and audio discovery live with their consumers. Imports, suite, Ruff, and documentation links pass. |
| 3. Consolidate operations | Extend the current `core/jobs.py` service and extract reusable logic from CLI commands and `core/desktop_operations.py`. Deliver rename first, albums/revert second, and lyrics/covers/recognition third. Migrate all three frontends for each operation. | Complete for current behavior. Rename execution and undo use `core/jobs.py`. CLI and desktop share enrichment entry points, cover processing, album folder selection, album and revert destination plans, and physical moves. Interfaces retain confirmation, controls, and presentation. The worker no longer calls a private audio-processing method. |
| 4. Separate engine and interface internals | Extract metadata I/O, filename rules, and remote providers from `AudioProcessor`. Isolate TUI controls from the process launcher. Keep desktop lifecycle decisions out of JSON serialization. Retain process isolation and protocol v1. | Complete. Metadata writes, lyrics tag writes, filename rules, and AcoustID recognition live outside `AudioProcessor`. The worker uses the public `process_file()` method and shared enrichment request. The TUI command adapter now owns child-only CLI prompt and Rich progress hooks separately from worker command construction. |
| 5. Move to the Python package | Move the established modules to `src/musren/`. Update imports, setuptools discovery, launchers, dynamic version lookup, uv cache keys, PyInstaller collection, worker module commands, installers, workflows, and artifact verification. Audit legacy CLI callers before deletion. | Complete. Python packages live under `src/musren/`; setuptools discovery, entry-point imports, worker launch, CI imports, release verification, contributor docs, and PyInstaller collection use the new layout. Wheel and source archive build, wheel imports in a clean environment, and the release verifier checks both artifacts. |
| 6. Organize desktop and close the migration | Extract the history/settings screens from `desktop/src/App.tsx`. Keep Zod parsing and Tauri calls under `api/`. Keep active job lifecycle in the app shell while it remains the single owner of worker protocol state. Update the root map and contributor guide. | Complete. History and settings screens live under `desktop/src/features/`, and operation labels have one owner. App retains worker lifecycle and confirmation state because those are shared across its operation view. Prettier is configured for the frontend; Ruff and Prettier formatting, Python tests, frontend build, release artifact checks, and sidecar smoke checks pass. |

Stage 5 is deliberately mechanical. Internal boundaries must be established before
renaming every import, so a packaging failure is distinguishable from a behavior
regression. For each moved internal API, migrate its callers and delete the old
implementation together. Keep a launcher shim only if an audited user-facing
invocation such as `python app.py` still requires it.

## Behavior to preserve

Use disposable fixtures and controlled remote responses to verify these cases:

- Rename formats, recursive scope, Unicode paths, collisions, unchanged names,
  stale previews, rename undo, and the keep/revert decision.
- Album grouping, singles, recursive revert, existing destinations, and failures
  after some files have already moved. Compare CLI and desktop policies before
  choosing a shared implementation. Record intentional differences separately.
- Real supported tag writes, existing artwork and lyrics, malformed audio,
  missing provider extras, unavailable credentials, and per-file provider errors.
- Cancellation during preview, processing, and confirmation. Pause remains
  cooperative, and completed changes remain visible after cancellation.
- Invalid protocol versions, mismatched job or confirmation IDs, worker exit,
  JSON-only desktop stdout, and secrets excluded from events and history.
- Existing config and SQLite history remain readable at the same locations.
  Preserve keyring migration behavior and avoid schema changes in this refactor.

Architecture checks should enforce a few useful boundaries, such as preventing
`audio/` and `providers/` from importing interfaces. They should not require every
module to match a prescribed file count or class structure.

## Local validation and completion

Follow [contributing](contributing.md) and [releases](releases.md). At each stage,
run imports first, relevant tests next, and the full suite before integration.
Run Ruff formatting and linting before every commit. Use Prettier for frontend
formatting and checks. Tests must exercise observable behavior rather than
preserve the old internal organization.

Use the selected environment's Python executable for these current-layout checks:

```shell
python -c "import app; import musren.core.audio_processor; import musren.core.tui"
python -m pytest -q
python -m ruff format .
python -m ruff check .
python scripts/check_docs.py
```

Build wheel and source distributions, then install the wheel in a fresh
environment outside the repository. Exercise the packaged sidecar with
`scripts/smoke_tauri_worker.py` using its documented executable argument. Run
`bun run build` from `desktop/` for the TypeScript check
and frontend build. Validate native artifacts on their supported host platforms;
a Linux build does not establish Windows or macOS compatibility.

Completion means all six operations share their processing rules across the
interfaces, installed artifacts run independently of the checkout, old internal
implementations are removed, and the repository map describes the actual layout.
Keep feature additions and changes to user policy in separate work.

The baseline was established after creating the project environment. Stage 4
keeps the TUI's compatibility hooks inside its isolated child adapter; stage 6
keeps protocol state in the app shell and separates screens by responsibility.
