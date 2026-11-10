# musren desktop

This is the React + TypeScript desktop shell for musren, built with Tauri and Vite.

## Development

Install Bun, then run:

```sh
bun install
source .venv/bin/activate
bun run tauri dev
```

Create the Python environment from the repository root first with
`python3 -m venv desktop/.venv` and
`desktop/.venv/bin/pip install -e '.[desktop]'`. The environment must be
active because Tauri builds the bundled Python worker before the frontend.
On Windows, use the equivalent activation command for PowerShell.

Build the frontend and native application with:

```sh
bun run tauri build
```

All frontend dependencies and scripts use Bun; keep `bun.lock` committed and
do not generate npm lockfiles.

## Supported platforms

The first desktop release targets Arch Linux x86_64, Windows 10+, and macOS
11+. The Arch `PKGBUILD` builds a temporary Linux bundle and packages its files
for pacman; it does not make Debian a supported target. AUR publication remains
a separate release decision.

The existing CI also creates Debian, RPM, and AppImage artifacts from the
packaging spike. They are experimental and outside the supported release scope.

## Arch package

`packaging/arch/PKGBUILD` builds and installs the Arch package locally. Keep
`pkgver` aligned with the repository release tag. AUR publication remains a
separate release decision.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
