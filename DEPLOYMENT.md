# Release musren

musren is a local Python application. Deployment means publishing an installable
wheel and source archive on GitHub Releases. There is no server to deploy.

## Install version 1.3.0

Download the wheel from the GitHub release, then install the TUI extra:

```powershell
py -3 -m pip install ".\musren-1.3.0-py3-none-any.whl[tui]"
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
py -3 -m twine check dist/*
py -3 scripts/verify_release.py --tag v1.3.0 --dist dist
```

The verifier checks the package version, both launchers, all TUI modules,
documentation, and exclusion of `.env`. It produces `dist/SHA256SUMS.txt`.

## Publish

Merge the validated feature branch into `main`, then push `main` and the version
tag. The Release workflow runs the complete suite on Windows and Linux before
publishing the verified wheel, source archive, and checksums.

```powershell
git tag v1.3.0
git push origin main
git push origin v1.3.0
```

Only the publish job gets permission to create a release. A failed validation
prevents publication. CI also checks Python 3.8 for the CLI and Python 3.9,
3.11, and 3.13 for the TUI. PyPI publication is not configured.
