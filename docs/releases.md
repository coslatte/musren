# Build and publish a release

musren releases contain an installable Python wheel, a source archive, and a
portable Windows executable. Checksums accompany both package types. User
installation instructions are in [the README](../README.md).

## Prepare a new version

1. Update `MUSIC_RENAMER_VERSION` in `constants/info.py`.
2. Add the changes to [changelog.md](changelog.md).
3. Refresh `uv.lock` with `uv lock`.
4. Run the checks in [contributing.md](contributing.md).

`pyproject.toml` reads the version from the constant. Update the constant once;
package metadata and CLI output use the same value.

## Build Python packages

Use an activated environment with the `dev` extra installed. Run from the
repository root:

```powershell
python -m build --outdir dist/release
python -m twine check dist/release/*.whl dist/release/*.tar.gz
$releaseVersion = python -c "from constants.info import MUSIC_RENAMER_VERSION; print(MUSIC_RENAMER_VERSION)"
python scripts/verify_release.py --tag "v$releaseVersion" --dist dist/release
```

The verifier checks versions, entry points, TUI modules, documentation, project
configuration, and exclusion of `.env`. It writes `SHA256SUMS.txt` beside the
wheel and source archive.

## Build the Windows executable

Use a separate Windows x64 environment with Python 3.13:

```powershell
py -3.13 -m venv .venv/windows-build
.\.venv\windows-build\Scripts\Activate.ps1
python -m pip install --only-binary=shazamio-core,pydantic-core ".[tui,recognition,lyrics,musicbrainz,shazam]" pyinstaller==6.22.0
python scripts/build_windows.py
python scripts/verify_windows.py dist/windows/musren-windows-x64.exe
```

The result is `dist/windows/musren-windows-x64.exe` with a separate
`WINDOWS-SHA256SUMS.txt`. The executable opens the TUI by default and accepts
CLI commands. `--cli` opens the original menu. Python dependencies are bundled;
AcoustID still needs the external `fpcalc` binary and an API key.

The verifier checks version, CLI help, TUI preview, packaged child processing,
rename, and rollback from outside the source checkout. The executable is unsigned.

## Build the Tauri desktop packages

The desktop release targets Arch Linux x86_64, Windows 10+, and macOS 11+.
Build each package on its native operating system after creating the worker
environment and installing the required system libraries, as described in
[`desktop/README.md`](../desktop/README.md).

From `desktop/`, install the locked Bun dependencies and build the matching
native bundle:

```sh
bun install --frozen-lockfile
bun run tauri build --bundles deb   # Linux bundle used by the Arch PKGBUILD
bun run tauri build --bundles nsis  # Windows
bun run tauri build --bundles dmg   # macOS
```

Build the Arch package from a clean checkout with `makepkg -si`; inspect its
contents and verify install, launch, and removal on a disposable Arch system.
On Windows and macOS, install the NSIS and DMG artifacts on clean native
systems. For all targets, verify startup, file permissions, credential storage,
the worker smoke path, and the expected failure message when the credential
service or an optional dependency is unavailable. AcoustID requires external
`fpcalc` and an API key.

The Tauri workflow runs a disposable credential write/read/delete check against
Windows Credential Locker and macOS Keychain. It never uses or prints the
user's AcoustID key.

The current Tauri workflow does not configure installer signing or macOS
notarization. Do not publish the desktop artifacts until the Windows installer
is signed and the macOS app is signed and notarized. The Linux `.deb` bundle
produced during the packaging spike is an intermediate input to the Arch
package, not a supported Debian release.

The first history release stores cover-art presence without copying artwork
images. History remains local and excludes credentials and full audio files.

The Phase 6 checklist and current validation status are tracked in
[`tauri-plan.md`](tauri-plan.md).

## Publish the verified revision

Merge the verified change into `main` and push it. Wait for every CI job to pass.
Then tag the revision with the new version:

```powershell
git push origin main
$releaseVersion = python -c "from constants.info import MUSIC_RENAMER_VERSION; print(MUSIC_RENAMER_VERSION)"
git tag -a "v$releaseVersion" -m "musren $releaseVersion"
git push origin "v$releaseVersion"
```

Use a new version tag. Existing published releases remain tied to their original
revision. The Release workflow validates Windows and Linux, builds and tests the
Windows executable, then publishes the assets on GitHub.

Only the publish job receives permission to create a release. Failed validation
prevents publication. PyPI publication is not configured.

## Check published downloads

Download the published assets and compare them with their SHA-256 files. On
Windows, `Get-FileHash PATH -Algorithm SHA256` prints an asset's checksum.
Run `scripts/verify_windows.py` against the downloaded executable before declaring
the release complete.
