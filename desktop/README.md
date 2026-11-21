# musren desktop

This is the React + TypeScript desktop shell for musren, built with Tauri and Vite.

## Install

Installers for Windows and macOS are attached to each GitHub release. They have
not been signed by a commercial developer identity yet.

- **Windows 10+:** download and run the NSIS installer. SmartScreen may show an
  unknown-publisher prompt because the installer is unsigned.
- **macOS 11+:** download the DMG for Apple Silicon or Intel, open it, and drag
  musren to Applications. The app is ad-hoc signed but not notarized. On first
  launch, control-click it, choose **Open**, and approve the security prompt.
- **Debian 12 / Ubuntu 22.04+ x86_64:** download the `.deb` from the
  [latest release](https://github.com/coslatte/musren/releases/latest) and run
  `sudo apt install ./*amd64.deb` from its download directory. APT
  installs the required system libraries automatically.
- **Arch Linux x86_64:** download the package from the
  [latest release](https://github.com/coslatte/musren/releases/latest) and run
  `sudo pacman -U ./musren-desktop-git-*.pkg.tar.zst`.

## Development

Install Python 3.10+, Bun, and stable Rust. Create the worker environment from
the repository root:

```sh
python3 -m venv desktop/.venv
desktop/.venv/bin/python -m pip install -e '.[desktop]'
```

On Arch Linux, install the Tauri system libraries and package build tools from
`packaging/arch/PKGBUILD` (including `gtk3`, `webkit2gtk-4.1`,
`libappindicator`, and `patchelf`). Then, from `desktop/`, run:

```sh
bun install
source .venv/bin/activate
bun run tauri dev
```

Keep the Python environment active because Tauri builds the bundled worker
before the frontend. On Windows, activate `desktop/.venv` with the equivalent
PowerShell command before building.

Build the frontend and native application with:

```sh
bun run tauri build --bundles deb   # Linux bundle, including on Arch
bun run tauri build --bundles nsis  # Windows only
bun run tauri build --bundles dmg   # macOS only
```

All frontend dependencies and scripts use Bun; keep `bun.lock` committed and
do not generate npm lockfiles.

## Supported platforms

The desktop release targets Debian 12 / Ubuntu 22.04+ x86_64, Arch Linux
x86_64, Windows 10+, and macOS 11+. Linux packages include the Python worker.
The Arch package is built from each tagged release and attached to the GitHub
release. AUR publication is not required.

RPM and AppImage artifacts from the initial packaging spike are experimental
and are not built or published for the supported release.

## Arch package

`packaging/arch/PKGBUILD` builds the `musren-desktop-git` package from the
tagged release source. Install the package downloaded from the latest GitHub
release with `sudo pacman -U ./musren-desktop-git-*.pkg.tar.zst`.

AcoustID recognition requires the `recognition` extra, `fpcalc` on `PATH`, and
an API key. Shazam recognition requires the `shazam` extra; lyrics require the
`lyrics` extra. Linux
credential storage requires a working Secret Service or KWallet session;
the Tauri CI checks Windows Credential Locker and macOS Keychain on their native
systems using a disposable random credential. The first history release records
cover-art presence but does not copy artwork images.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
