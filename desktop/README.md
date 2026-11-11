# musren desktop

This is the React + TypeScript desktop shell for musren, built with Tauri and Vite.

## Install

- **Arch Linux x86_64:** download the `musren-arch-x86_64-pacman` artifact
  from a successful Tauri workflow run, extract the `.pkg.tar.zst`, then run
  `sudo pacman -U ./musren-desktop-*.pkg.tar.zst`.
- **Windows 10+:** download and run the NSIS installer from a successful
  workflow run. The current installer is unsigned, so Windows may show a
  security prompt.
- **macOS 11+:** download the DMG matching Apple Silicon or Intel, open it,
  then drag `musren` to Applications. Current builds are unsigned and
  unnotarized; Gatekeeper may block them. Do not bypass this for public use.

These CI artifacts are for validation. Wait for signed Windows/macOS release
packages before distributing them to users.

## Development

Install Python 3.10+, Bun, and stable Rust. Create the worker environment from
the repository root:

```sh
python3 -m venv desktop/.venv
desktop/.venv/bin/python -m pip install -e '.[desktop]'
```

On Arch Linux, install the Tauri system libraries and package build tools from
`packaging/arch/PKGBUILD` (including `gtk3`, `webkit2gtk-4.1`,
`libappindicator-gtk3`, and `patchelf`). Then, from `desktop/`, run:

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

The first desktop release targets Arch Linux x86_64, Windows 10+, and macOS
11+. The Arch `PKGBUILD` builds a temporary Linux bundle and packages its files
for pacman; it does not make Debian a supported target. AUR publication remains
a separate release decision.

The initial packaging spike also produced Debian, RPM, and AppImage artifacts.
They are experimental and are not built or published for the supported release.

## Arch package

`packaging/arch/PKGBUILD` builds and installs the Arch package locally. Keep
`pkgver` aligned with the repository release tag. AUR publication remains a
separate release decision.

AcoustID requires the `recognition` extra, `fpcalc` on `PATH`, and an API key.
Shazam requires the `shazam` extra; lyrics require the `lyrics` extra. Linux
credential storage requires a working Secret Service or KWallet session;
the Tauri CI checks Windows Credential Locker and macOS Keychain on their native
systems using a disposable random credential. The first history release records
cover-art presence but does not copy artwork images. Desktop packages are not
release-ready until native install, credential-store, and signing/notarization
checks pass on Windows and macOS.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
