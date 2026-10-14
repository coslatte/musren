# Changelog

## Unreleased

- Move detailed guides into `docs/` and installation helpers into `scripts/`.
- Consolidate metadata, dependency extras, build settings, and Ruff rules in `pyproject.toml`.
- Read the package version from `constants/info.py` and refresh `uv.lock`.
- Add documentation-link checks to CI and release validation.
- Let the TUI accept a typed working directory on Enter and keep the folder browser on that path.
- Add **Browse with fzf** to pick the working directory; it is optional and reports when unavailable.

## 1.3.1

- Publish a portable Windows x64 executable that opens the TUI without a Python installation.
- Keep CLI commands available in the executable, including `--cli` for the original menu.
- Run packaged processing jobs without opening additional console windows.
- Bundle optional Python dependencies for lyrics, artwork, AcoustID, MusicBrainz, and Shazam.
- Build and smoke-test the executable in the release workflow.

AcoustID still requires the external Chromaprint `fpcalc` binary and an API key.

## 1.3.0

- Add an optional Textual interface with all existing audio workflows.
- Keep CLI commands and the original interactive menu available.
- Adapt forms and browsing panels to terminal width; keep job controls visible.
- Move live output into a dedicated tab and reduce competing colors and text.
- Support previews, credential management, themes, pause, cancellation, and rename undo.
- Preserve filename collisions during album organization.
- Fix recursive artwork installation and display per-file processing errors.
- Preserve CLI paths containing spaces and check optional dependencies without blocking TUI jobs.
- Add headless layout tests and offline workflows using disposable tagged audio files.

The TUI requires Python 3.9+. CLI-only installations continue to support Python 3.8.
