# Contribute to musren

Use Python 3.10 or newer in an isolated environment from the repository root.
Use Python 3.13 for portable Windows builds.

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
or `shazam`. Install the `desktop` extra to build the Python worker sidecar. The
[release guide](releases.md) lists other standalone build dependencies.

## Run and check a change

```shell
python app.py --tui
python app.py --help
python -c "import app; import musren.core.audio_processor; import musren.core.tui"
python -m pytest -q
python -m ruff format .
python -m ruff check .
```

The tests use temporary tagged audio and controlled service responses. Headless
TUI tests run when Textual is installed. Tests do not validate live API availability
or account credentials. Check those separately using your own files.

For frontend changes, run `bun run format` from `desktop/` to format the UI and
`bun run format:check` to verify its formatting. `bun run build` runs TypeScript
checks and creates the production frontend bundle.

Before every commit or PR, follow the mandatory checks in
[AGENTS.md](../AGENTS.md). Keep optional imports lazy and avoid import-time
network calls or mutations.

## Find the code and configuration

| Path | Responsibility |
| --- | --- |
| `src/musren/entrypoint.py` | Installed CLI and TUI launchers |
| `app.py` | Checkout shim for direct `python app.py` use |
| `src/musren/core/cli/` | CLI commands and original menu |
| `src/musren/core/tui/` | Interface, job arguments, and isolated workers |
| `src/musren/core/audio_processor.py` | Audio processing entry point |
| `src/musren/core/lyrics.py` | Synchronized-lyrics provider chain |
| `src/musren/core/artwork.py` | Artwork retrieval and embedding |
| `src/musren/core/install_covers.py` | Batch artwork installation |
| `src/musren/constants/` | Settings and package version |
| `src/musren/utils/` | Audio file discovery and dependency checks |
| `desktop/src/App.tsx` | Desktop shell and active job lifecycle |
| `desktop/src/features/` | Operation labels and history/settings screens |
| `packaging/arch/` | Arch Linux VCS package recipe and generated metadata |
| `tests/` | Workflow, import, and layout checks |
| `docs/` | User and contributor guides |
| `scripts/` | Installation, builds, and artifact checks |
| `pyproject.toml` | Metadata, dependencies, extras, entry points, and Ruff |
| `desktop/package.json` | Frontend scripts and dependencies, including Prettier |
| `uv.lock` | Resolved dependencies for optional uv workflows |
| `MANIFEST.in` | Source archive contents |
| `.github/workflows/` | Cross-platform CI and releases |

The package version comes from `src/musren/constants/info.py`. Setuptools reads that value
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
