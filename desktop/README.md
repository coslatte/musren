# musren desktop

This is the React + TypeScript desktop shell for musren, built with Tauri and Vite.

## Install

Use the signed packages attached to a GitHub release on Windows or macOS. The
current CI artifacts are for validation and are not signed for public distribution.

- **Windows 10+:** download and run the signed NSIS installer.
- **macOS 11+:** download the DMG for Apple Silicon or Intel, open it, and drag
  musren to Applications. Open it normally after notarization.
- **Arch Linux x86_64:** after the AUR package is published, run
  `yay -S musren-desktop-git`.

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

The first desktop release targets Arch Linux x86_64, Windows 10+, and macOS
11+. The Arch `PKGBUILD` builds a temporary Linux bundle and packages its files
for pacman; it does not make Debian a supported target. The AUR recipe is
`musren-desktop-git` and builds from the upstream `main` branch.

The initial packaging spike also produced Debian, RPM, and AppImage artifacts.
They are experimental and are not built or published for the supported release.

## Arch package

`packaging/arch/PKGBUILD` builds the `musren-desktop-git` VCS package from the
upstream `main` branch. After publication, install it with `yay -S
musren-desktop-git` or clone the AUR repository and run `makepkg -si`.

AcoustID recognition requires the `recognition` extra, `fpcalc` on `PATH`, and
an API key. Shazam recognition requires the `shazam` extra; lyrics require the
`lyrics` extra. Linux
credential storage requires a working Secret Service or KWallet session;
the Tauri CI checks Windows Credential Locker and macOS Keychain on their native
systems using a disposable random credential. The first history release records
cover-art presence but does not copy artwork images. Desktop packages are not
release-ready until native install, credential-store, and signing/notarization
checks pass on Windows and macOS.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
