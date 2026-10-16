# Contribute to musren

Use an isolated Python environment and work from the repository root. The TUI
requires Python 3.9+. Use Python 3.13 for portable Windows builds. CLI-only
compatibility is checked on Python 3.8.

## Set up an environment

On Windows:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,tui]"
```

On Linux or macOS:

```shell
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,tui]"
```

Install feature extras when you need them: `lyrics`, `recognition`, `musicbrainz`,
or `shazam`. The [release guide](releases.md) lists standalone build dependencies.

## Run and check a change

```shell
python app.py --tui
python app.py --help
python -c "import app; import core.audio_processor; import core.tui"
python -m pytest -q
python -m ruff format .
python -m ruff check .
```

The tests use temporary tagged audio and controlled service responses. Headless
TUI tests run when Textual is installed. Tests do not validate live API availability
or account credentials. Check those separately using your own files.

Before every commit or PR, follow the mandatory checks in
[AGENTS.md](../AGENTS.md). Keep optional imports lazy and avoid import-time
network calls or mutations.

## Find the code and configuration

| Path | Responsibility |
| --- | --- |
| `app.py` | Public CLI and TUI launchers |
| `core/cli/` | CLI commands and original menu |
| `core/tui/` | Interface, job arguments, and isolated workers |
| `core/audio_processor.py` | Metadata, recognition, lyrics, and file renaming |
| `core/lyrics.py` | Synchronized-lyrics provider chain (LRCLIB, Paxsenix, syncedlyrics) |
| `core/artwork.py` | Artwork retrieval and embedding |
| `core/install_covers.py` | Batch artwork installation |
| `constants/` | Settings and the authoritative package version |
| `utils/` | File discovery and dependency checks |
| `tests/` | Workflow, import, and layout checks |
| `docs/` | User and contributor guides |
| `scripts/` | Installation, builds, and artifact checks |
| `pyproject.toml` | Metadata, dependencies, extras, entry points, and Ruff |
| `uv.lock` | Resolved dependencies for optional uv workflows |
| `MANIFEST.in` | Source archive contents |
| `.github/workflows/` | Cross-platform CI and releases |

The package version comes from `constants/info.py`. Setuptools reads that value
through `pyproject.toml`; there is no second version value to update.

If you use uv, refresh the lock after changing dependencies or the version:

```shell
uv lock
uv lock --check
uv sync --extra dev --extra tui
```

## Use helper scripts

Python installations from a checkout can use `scripts/install.ps1` on Windows
or `scripts/install.sh` on Linux and macOS. Both resolve the project directory
from their own location. Use an activated environment to control the interpreter.

```powershell
.\scripts\install.ps1 -Dev
.\scripts\build.bat
```

```shell
bash scripts/install.sh dev
```

For release builds and the Windows executable, follow [releases.md](releases.md).
