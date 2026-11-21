# Build and publish a release

musren releases contain an installable Python wheel, a source archive, and a
portable Windows executable. Checksums accompany both package types. User
installation instructions are in [the README](../README.md).

## Prepare a new version

1. Update `MUSIC_RENAMER_VERSION` in `src/musren/constants/info.py`.
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
$releaseVersion = python -c "from musren.constants.info import MUSIC_RENAMER_VERSION; print(MUSIC_RENAMER_VERSION)"
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

The desktop release targets Debian 12 / Ubuntu 22.04+ x86_64, Arch Linux
x86_64, Windows 10+, and macOS 11+.
Build each package on its native operating system after creating the worker
environment and installing the required system libraries, as described in
[`desktop/README.md`](../desktop/README.md).

From `desktop/`, install the locked Bun dependencies and build the matching
native bundle:

```sh
bun install --frozen-lockfile
bun run tauri build --bundles deb   # Debian/Ubuntu package and Arch build input
bun run tauri build --bundles nsis  # Windows
bun run tauri build --bundles dmg   # macOS
```

The Arch recipe is the VCS package `musren-desktop-git`. For a tagged release,
the Release workflow builds it from that exact source revision, installs it in
Arch Linux for a launch smoke check, and attaches the package to the GitHub
release. Users can install it with `sudo pacman -U ./musren-desktop-git-*.pkg.tar.zst`.

Validate the Arch recipe from `packaging/arch/` before changing package metadata:

```sh
makepkg --printsrcinfo > .SRCINFO
makepkg --verifysource
makepkg --syncdeps --cleanbuild
namcap PKGBUILD
```

Update `.SRCINFO` whenever package metadata changes. AUR publication is outside
the current release scope.

The [Tauri desktop workflow](https://github.com/coslatte/musren/actions/workflows/tauri.yml)
builds the Arch package with its declared dependencies, installs and removes
it with `pacman`, and launches it under Xvfb. It also installs the Debian
package on Ubuntu 22.04 and launches it under Xvfb. Native Windows and macOS
jobs install or mount their bundles, launch the app, and run the worker and
credential-store smoke checks. On a version tag, the Release workflow waits for
that exact Tauri run and attaches its Windows NSIS, Debian, Arch, and two macOS
packages to the GitHub release. The successful [validation run for commit
1f36423](https://github.com/coslatte/musren/actions/runs/43051126454) uploaded
Arch, Windows, macOS Intel, and macOS Apple Silicon artifacts. Workflow
artifacts are for validation; they are not signed release packages.

Before publishing, run the Tauri workflow on the final release commit and
confirm all platform builds and artifacts. The workflow can do
these checks on GitHub-hosted Windows and macOS runners; a local Windows
installation is not required. AcoustID requires the `recognition` extra, the
external `fpcalc` executable, and an API key. Shazam requires the `shazam`
extra; lyrics require the `lyrics` extra. The desktop reports missing
credentials and optional dependencies per operation.

The Tauri workflow runs a disposable credential write/read/delete check against
Windows Credential Locker and macOS Keychain. It never uses or prints the
user's AcoustID key.

The Windows installer is currently unsigned and Windows can show a
SmartScreen unknown-publisher warning. macOS builds use an ad-hoc signature so
they can run after the user approves the app in Privacy & Security; they are
not notarized. This allows desktop packages to be distributed without
commercial signing credentials, with OS warnings documented in
[`desktop/README.md`](../desktop/README.md). To remove those warnings, add a
Windows code-signing certificate and Apple Developer signing and notarization
credentials as protected GitHub Actions secrets, then verify signatures before
publishing. Never put signing credentials in the repository. The `.deb` package
is the supported easy-install option for Debian and Ubuntu.

The first history release stores cover-art presence without copying artwork
images. History remains local and excludes credentials and full audio files.

The Phase 6 checklist and current validation status are tracked in
[`tauri-plan.md`](tauri-plan.md).

## Publish the verified revision

Merge the verified change into `main` and push it. Wait for every CI job to pass.
Then tag the revision with the new version:

```powershell
git push origin main
$releaseVersion = python -c "from musren.constants.info import MUSIC_RENAMER_VERSION; print(MUSIC_RENAMER_VERSION)"
git tag -a "v$releaseVersion" -m "musren $releaseVersion"
git push origin "v$releaseVersion"
```

Use a new version tag. Existing published releases remain tied to their original
revision. The Release workflow validates Windows and Linux, builds and tests the
portable Windows executable, waits for the Tauri workflow on the same tag,
verifies its platform assets, and publishes the Python packages, portable
executable, Windows installer, Linux packages, macOS DMGs, and SHA-256 checksums
on GitHub.

Only the publish job receives permission to create a release. Failed validation
prevents publication. PyPI publication is not configured.

## Check published downloads

Download all assets and `SHA256SUMS.txt` into one directory, then run
`sha256sum -c SHA256SUMS.txt`. On Windows, compare each asset with the matching
entry using `Get-FileHash PATH -Algorithm SHA256`.
Run `scripts/verify_windows.py` against the downloaded executable before declaring
the release complete.
