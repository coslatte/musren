"""Check distributable contents and version before publishing a release."""

import argparse
import ast
import hashlib
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path


def write_checksums(dist: Path) -> int:
    """Write checksums for every release asset under the distribution directory."""
    checksum_file = dist / "SHA256SUMS.txt"
    release_files = sorted(
        path
        for path in dist.rglob("*")
        if path.is_file() and path != checksum_file and not path.name.startswith(".")
    )
    basenames = [path.name for path in release_files]
    assert len(basenames) == len(set(basenames)), (
        "Release asset filenames must be unique"
    )
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in release_files
    ]
    checksum_file.write_text("".join(lines), encoding="utf-8")
    return len(release_files)


def verify(dist: Path, tag: str, require_desktop_assets: bool = False) -> None:
    """Validate the actual wheel and source archive, then write checksums."""
    version = tag[1:] if tag.startswith("v") else tag
    wheel = dist / f"musren-{version}-py3-none-any.whl"
    source = dist / f"musren-{version}.tar.gz"
    required = {
        f"musren/core/tui/{name}.py" for name in ("__init__", "app", "jobs", "runner")
    }
    required.add("musren/entrypoint.py")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert required <= names, "TUI modules missing from the wheel"
        assert "app.py" not in names, "Checkout shim must not be a wheel entry point"
        info = f"musren-{version}.dist-info"
        metadata = Parser().parsestr(archive.read(f"{info}/METADATA").decode())
        assert metadata["Version"] == version, "Tag and package version differ"
        constants = ast.parse(archive.read("musren/constants/info.py").decode())
        runtime_version = next(
            ast.literal_eval(node.value)
            for node in constants.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "MUSIC_RENAMER_VERSION"
                for target in node.targets
            )
        )
        assert runtime_version == version, "CLI and package version differ"
        entries = archive.read(f"{info}/entry_points.txt").decode()
        assert "musren = musren.entrypoint:main" in entries
        assert "musren-tui = musren.entrypoint:tui" in entries
        assert "tui" in metadata.get_all("Provides-Extra", [])
        assert not any(Path(name).name == ".env" for name in names), (
            "Environment file included"
        )
    with tarfile.open(source) as archive:
        names = set(archive.getnames())
        root = f"musren-{version}/"
        assert all(root + "src/" + name in names for name in required)
        assert root + "app.py" in names, "Source archive missing checkout launcher"
        assert root + "docs/tui.md" in names and root + "docs/changelog.md" in names
        assert root + "pyproject.toml" in names, (
            "Source archive missing project settings"
        )
        assert not any(Path(name).name == ".env" for name in names), (
            "Environment file included"
        )
    if require_desktop_assets:
        desktop = dist / "desktop"
        required_assets = {
            "Windows NSIS installer": "musren-windows-latest-nsis-*.exe",
            "Debian package": "musren-ubuntu-22.04-deb-*.deb",
            "Arch package": "musren-arch-x86_64-pacman-*.pkg.tar.zst",
            "macOS Apple Silicon DMG": "musren-macos-15-dmg-*.dmg",
            "macOS Intel DMG": "musren-macos-15-intel-dmg-*.dmg",
        }
        for description, pattern in required_assets.items():
            assert any(desktop.glob(pattern)), f"Missing {description} ({pattern})"
    asset_count = write_checksums(dist)
    print(f"Verified musren {version}: {asset_count} assets and checksums")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--require-desktop-assets", action="store_true")
    arguments = parser.parse_args()
    verify(arguments.dist, arguments.tag, arguments.require_desktop_assets)
