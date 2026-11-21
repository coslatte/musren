# Build musren from source

Three artifacts are built separately: the Python CLI/TUI, the PyInstaller worker
that the desktop app calls, and the Tauri desktop application. Build each on its
native operating system. Release-specific steps live in
[releases.md](releases.md); the desktop development guide lives in
[desktop/README.md](../desktop/README.md).

## Python CLI and TUI

Use Python 3.10 or newer in an isolated environment. The editable install
provides the `musren` and `musren-tui` launchers:

```shell
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,tui]"
musren --version
musren-tui
```

Add `lyrics`, `recognition`, `musicbrainz`, or `shazam` when the built interface
must include those operations. `python app.py --tui` runs the checkout without
installing the launchers.

To produce installable Python packages, install the `dev` extra and run:

```shell
python -m build --outdir dist/release
python -m twine check dist/release/*.whl dist/release/*.tar.gz
python scripts/verify_release.py --tag "v<version>" --dist dist/release
```

Replace `<version>` with the current value from `src/musren/constants/info.py`. The
verifier writes `SHA256SUMS.txt` beside the wheel and source archive. The full
procedure is in [releases.md](releases.md).

## Desktop worker (PyInstaller sidecar)

The desktop app launches a Python worker named with the Rust target triple. Build
it with Rust installed and the worker environment active:

```shell
desktop/.venv/bin/python -m pip install -e '.[desktop]'
desktop/.venv/bin/python scripts/build_tauri_sidecar.py
```

`scripts/build_tauri_sidecar.py` asks `rustc --print host-tuple` for the target,
then runs PyInstaller in one-file, console mode and writes:

```text
desktop/src-tauri/binaries/musren-worker-<target>
```

On Windows the file ends in `.exe`, for example
`musren-worker-x86_64-pc-windows-msvc.exe`. Build the worker inside the same
environment that will ship, because PyInstaller bundles only the extras that are
installed there. Run the smoke check before packaging:

```shell
python scripts/smoke_tauri_worker.py
```

From `desktop/`, `bun run build:worker` runs the same script through
`python ../scripts/build_tauri_sidecar.py`, so activate the worker environment
first.

## Desktop frontend

Install the locked Bun dependencies once, then build the production bundle:

```sh
cd desktop
bun install --frozen-lockfile
bun run build
```

`bun run build` runs the TypeScript checks and Vite, writing the frontend to
`desktop/dist/`, the `frontendDist` directory in `src-tauri/tauri.conf.json`.
`bun run format` and `bun run format:check` handle Prettier formatting.

## Tauri application and installers

Tauri's build hook rebuilds the worker and frontend before compiling, so the
simplest full build is:

```sh
cd desktop
source .venv/bin/activate
bun run tauri build --bundles deb   # Linux bundle, including on Arch
bun run tauri build --bundles nsis  # Windows only
bun run tauri build --bundles dmg   # macOS only
```

`bun run build:desktop` runs the worker build followed by `bun run tauri build`
with the default bundle targets. The Tauri CLI produces the native executable and
the platform installers. Install the system libraries listed in
[desktop/README.md](../desktop/README.md) and the [Arch
PKGBUILD](../packaging/arch/PKGBUILD) before the first build.

To compile only the Rust binary, without producing installers, build the worker
and frontend first and then run Cargo:

```sh
cd desktop/src-tauri
cargo build --release
```

This writes `desktop/src-tauri/target/release/musren-desktop` (`.exe` on Windows).
It does not create the `bundle/` installers; use `bun run tauri build` for those.
Cargo needs the frontend in `desktop/dist/` and the worker in
`desktop/src-tauri/binaries/` already present.

## Portable Windows executable

The standalone Windows build uses Python 3.13 on Windows x64 and bundles the
Python dependencies:

```powershell
py -3.13 -m venv .venv/windows-build
.\.venv\windows-build\Scripts\Activate.ps1
python -m pip install --only-binary=shazamio-core,pydantic-core ".[tui,recognition,lyrics,musicbrainz,shazam]" pyinstaller==6.22.0
python scripts/build_windows.py
python scripts/verify_windows.py dist/windows/musren-windows-x64.exe
```

`fpcalc` is not bundled. See [releases.md](releases.md) for the full release
checklist.

## Where the artifacts are

Published downloads are on the
[GitHub Releases page](https://github.com/coslatte/musren/releases): the Python
wheel and source archive, `SHA256SUMS.txt`, and `musren-windows-x64.exe`. Signed
desktop installers and DMGs are attached when signing is available; workflow
artifacts are unsigned validation builds.

Local build outputs, relative to the repository root:

| Artifact | Path |
| --- | --- |
| Python wheel and source archive | `dist/release/` (or `dist/` when `--outdir` is omitted) |
| Python checksums | `dist/release/SHA256SUMS.txt` |
| Portable Windows executable | `dist/windows/musren-windows-x64.exe` |
| Windows executable checksums | `dist/windows/WINDOWS-SHA256SUMS.txt` |
| Desktop frontend bundle | `desktop/dist/` |
| Python worker sidecar | `desktop/src-tauri/binaries/musren-worker-<target>` (`.exe` on Windows) |
| Native desktop executable | `desktop/src-tauri/target/release/musren-desktop` (`.exe` on Windows) |
| Debian bundle | `desktop/src-tauri/target/release/bundle/deb/*.deb` |
| Windows NSIS installer | `desktop/src-tauri/target/release/bundle/nsis/*.exe` |
| macOS DMG | `desktop/src-tauri/target/release/bundle/dmg/*.dmg` |
| Experimental Linux bundles | `desktop/src-tauri/target/release/bundle/appimage/`, `bundle/rpm/` |
| Arch package | `packaging/arch/musren-desktop-git-*.pkg.tar.zst` |

The Linux `.deb` is an intermediate input to the Arch package, not a supported
Debian release. The experimental AppImage and RPM bundles are not published. To
verify an artifact, follow [releases.md](releases.md) and test it with
[testing.md](testing.md).
