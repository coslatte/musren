"""Check distributable contents and version before publishing a release."""

import argparse
import ast
import hashlib
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path


def verify(dist: Path, tag: str) -> None:
    """Validate the actual wheel and source archive, then write checksums."""
    version = tag[1:] if tag.startswith("v") else tag
    wheel = dist / f"musren-{version}-py3-none-any.whl"
    source = dist / f"musren-{version}.tar.gz"
    required = {f"core/tui/{name}.py" for name in ("__init__", "app", "jobs", "runner")}
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert required <= names, "TUI modules missing from the wheel"
        info = f"musren-{version}.dist-info"
        metadata = Parser().parsestr(archive.read(f"{info}/METADATA").decode())
        assert metadata["Version"] == version, "Tag and package version differ"
        constants = ast.parse(archive.read("constants/info.py").decode())
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
        assert "musren = app:main" in entries and "musren-tui = app:tui" in entries
        assert "tui" in metadata.get_all("Provides-Extra", [])
        assert not any(Path(name).name == ".env" for name in names), (
            "Environment file included"
        )
    with tarfile.open(source) as archive:
        names = set(archive.getnames())
        root = f"musren-{version}/"
        assert all(root + name in names for name in required)
        assert root + "TUI.md" in names and root + "CHANGELOG.md" in names
        assert not any(Path(name).name == ".env" for name in names), (
            "Environment file included"
        )
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (wheel, source)
    ]
    (dist / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8")
    print(f"Verified musren {version}: wheel, source archive, launchers and checksums")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag", required=True)
    arguments = parser.parse_args()
    verify(arguments.dist, arguments.tag)
