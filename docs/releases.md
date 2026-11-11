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

The [Tauri desktop workflow](https://github.com/coslatte/musren/actions/workflows/tauri.yml)
builds the Arch package with its declared dependencies, installs and removes
it with `pacman`, and launches it under Xvfb. Native Windows and macOS jobs
install or mount their bundles, launch the app, and run the worker and
credential-store smoke checks. The successful [validation run for commit
1f36423](https://github.com/coslatte/musren/actions/runs/43051126454) uploaded
Arch, Windows, macOS Intel, and macOS Apple Silicon artifacts. Workflow
artifacts are for validation; they are not signed release packages.

Before publishing, run the Tauri workflow on the final release commit and
confirm all four jobs and artifacts. Also verify the signed Windows installer
and signed/notarized macOS app on clean native systems. The workflow can do
these checks on GitHub-hosted Windows and macOS runners; a local Windows
installation is not required. AcoustID requires the `recognition` extra, the
external `fpcalc` executable, and an API key. Shazam requires the `shazam`
extra; lyrics require the `lyrics` extra. The desktop reports missing
credentials and optional dependencies per operation.

The Tauri workflow runs a disposable credential write/read/delete check against
Windows Credential Locker and macOS Keychain. It never uses or prints the
user's AcoustID key.

Signing needs owner-provided credentials in protected GitHub Actions
environment secrets, never in the repository: a Windows code-signing
certificate and password; an Apple Developer signing identity, App Store
Connect API key, and notarization credentials. Configure a protected release
environment, then add signing steps to the native Windows/macOS jobs. The jobs
must sign, notarize and staple the Mac app, verify signatures, and only then
upload release packages. No local Windows installation is needed. Do not
publish unsigned desktop artifacts. The current workflow does not yet perform
signing. The Linux `.deb` bundle is an intermediate input to the Arch package,
not a supported Debian release.

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
