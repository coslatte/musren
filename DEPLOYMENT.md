# Release musren

musren is a local Python application. Deployment means publishing an installable
wheel and source archive on GitHub Releases. There is no server to deploy.

## Portable Windows app

Download `musren-windows-x64.exe` from release 1.3.1 or newer and double-click it
to open the TUI. Python and the optional Python dependencies are bundled.
No installer is required. Keep the executable wherever you prefer.

From a terminal:

```powershell
.\musren-windows-x64.exe                 # TUI
.\musren-windows-x64.exe --cli           # Original CLI menu
.\musren-windows-x64.exe rename --help   # CLI commands
```

AcoustID still requires `fpcalc` in PATH and an API key. User settings are shared
with Python installations in `~/.musren/config.json`. The executable is unsigned.

## Install the Python package

Download the wheel from the GitHub release, then install the TUI extra:

```powershell
py -3 -m pip install ".\musren-1.3.1-py3-none-any.whl[tui]"
musren-tui
```

For lyrics or recognition, add the corresponding extras, such as
`[tui,lyrics,recognition]` or `[tui,shazam]`. AcoustID also needs `fpcalc` and an API
key. `musren` opens the original menu; `musren --help` lists CLI commands.

## Build and verify

```powershell
py -3 -m pip install build twine pytest ruff
py -3 -m ruff format .
py -3 -m ruff check .
py -3 -m pytest -q
py -3 -m build
py -3 -m twine check dist/*.whl dist/*.tar.gz
py -3 scripts/verify_release.py --tag v1.3.1 --dist dist
```

The verifier checks the package version, both launchers, all TUI modules,
documentation, and exclusion of `.env`. It produces `dist/SHA256SUMS.txt`.

## Publish

Merge the validated feature branch into `main`, then push `main` and the version
tag. The Release workflow runs the complete suite on Windows and Linux before
publishing the verified wheel, source archive, and checksums.

```powershell
git tag v1.3.1
git push origin main
git push origin v1.3.1
```

Only the publish job gets permission to create a release. A failed validation
prevents publication. CI also checks Python 3.8 for the CLI and Python 3.9,
3.11, and 3.13 for the TUI. PyPI publication is not configured.

Build the executable on Windows using an isolated Python 3.13 environment:

```powershell
py -3.13 -m pip install --only-binary=shazamio-core,pydantic-core ".[tui,recognition,lyrics,musicbrainz,shazam]" pyinstaller==6.22.0
py -3.13 scripts/build_windows.py
py -3.13 scripts/verify_windows.py dist/windows/musren-windows-x64.exe --version 1.3.1
```

The release workflow tests the standalone executable before publishing it with
its separate `WINDOWS-SHA256SUMS.txt` alongside the Python packages.
