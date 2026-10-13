# Agent and contributor guide

musren organizes local audio files through a CLI and an optional Textual TUI.
Use English for generated messages, documentation, and commit messages.

## Repository map

- `app.py`: CLI and TUI entry points, including packaged worker dispatch.
- `core/cli/`: command parsing, the original menu, and shared audio commands.
- `core/tui/`: widgets, validated jobs, and the isolated processing runner.
- `core/audio_processor.py`, `core/artwork.py`, and `core/install_covers.py`: audio operations.
- `constants/` and `utils/`: settings, version, file discovery, and dependency checks.
- `tests/`: import checks, disposable audio fixtures, workflows, and headless UI tests.
- `docs/`: user guides, contributor instructions, release steps, and changelog.
- `scripts/`: installers, package validation, and portable Windows builds.
- `pyproject.toml`: package metadata, extras, launchers, build backend, and Ruff settings.

The CLI supports Python 3.8+. The TUI requires Python 3.9+. Portable Windows
builds use Python 3.13 and PyInstaller. AcoustID also needs the external `fpcalc`
binary. Optional Python features use extras in `pyproject.toml`.

## Working rules

- Keep docstrings short, usually one to three lines. Annotate new functions explicitly.
- Import optional third-party libraries inside the functions that need them.
- Avoid network calls, subprocesses, and filesystem mutations at module import time.
- Catch errors explicitly and report them. Never swallow errors with a bare `except:`.
- Keep CLI and TUI behavior in the shared commands and audio engine.
- Keep patches focused and reversible. Preserve existing work in the checkout.
- Keep `AGENTS.md` at the repository root. Use hidden files for machine metadata.

## Workflow

1. Outline two to six concrete steps and identify affected files.
2. Search with `rg` and inspect the actual callers before editing.
3. Make focused patches, one file at a time where practical.
4. Check imports, then run the relevant tests and the full suite.
5. Verify the real artifact or behavior. Include commands and results in the final report or PR.

For environment setup, use [docs/contributing.md](docs/contributing.md).

```powershell
py -3 -m pip install -e ".[dev,tui]"
py -3 -c "import app; import core.audio_processor; import core.tui"
py -3 -m pytest -q
```

Use an isolated environment. If the launcher selects an unintended interpreter,
select the project's supported Python installation before running these commands.

## Mandatory checks before a commit or pull request

Run both commands and fix every reported issue:

```powershell
py -3 -m ruff format .
py -3 -m ruff check .
```

Do not commit or open a PR until both commands pass. CI uses Ruff 0.15.0 and the
rules declared in `pyproject.toml`.

## Tests and packaging

Use disposable files for audio tests and controlled responses for remote services.
Optional feature tests must skip when their dependency is absent or install the
corresponding extra in CI. Import checks must remain non-invasive.

Verify `fpcalc` in PATH and supported project locations before reporting it
missing. Document installation requirements in the user guides.

When moving documentation or configuration, update Markdown links, `MANIFEST.in`,
release workflows, and artifact verification together. When changing metadata,
refresh `uv.lock` and verify wheel and source builds.

The release procedure is in [docs/releases.md](docs/releases.md).
