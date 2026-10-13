"""Build a portable Windows executable with the TUI and optional Python features."""

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path


def build(output: Path) -> Path:
    """Run PyInstaller using a clean build environment and emit a checksum."""
    if os.name != "nt":
        raise SystemExit("The Windows executable must be built on Windows.")
    root = Path(__file__).resolve().parents[1]
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",
            "--name",
            "musren-windows-x64",
            "--paths",
            str(root),
            "--distpath",
            str(output),
            "--workpath",
            str(root / "build" / "windows"),
            "--specpath",
            str(root / "build"),
            "--collect-all",
            "textual",
            "--collect-submodules",
            "core",
            "--collect-submodules",
            "mutagen",
            "--collect-submodules",
            "syncedlyrics",
            "--collect-all",
            "shazamio_core",
            str(root / "scripts" / "windows_launcher.py"),
        ],
        cwd=root,
        check=True,
    )
    executable = output / "musren-windows-x64.exe"
    checksum = hashlib.sha256(executable.read_bytes()).hexdigest()
    (output / "WINDOWS-SHA256SUMS.txt").write_text(
        f"{checksum}  {executable.name}\n", encoding="utf-8"
    )
    return executable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist/windows"))
    args = parser.parse_args()
    print(build(args.dist))
