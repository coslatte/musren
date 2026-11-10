"""Build the host Python worker using the Tauri sidecar naming convention."""

import argparse
import subprocess
import sys
from pathlib import Path


def build() -> Path:
    """Build the worker for the current host and place it beside the Tauri app."""
    root = Path(__file__).resolve().parents[1]
    if sys.version_info < (3, 10):
        raise SystemExit("The desktop worker build requires Python 3.10 or newer.")

    try:
        target = subprocess.run(
            ["rustc", "--print", "host-tuple"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(
            "Install Rust to determine the Tauri sidecar target."
        ) from error

    output = root / "desktop" / "src-tauri" / "binaries"
    output.mkdir(parents=True, exist_ok=True)
    name = f"musren-worker-{target}"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        name,
        "--paths",
        str(root),
        "--distpath",
        str(output),
        "--workpath",
        str(root / "build" / "tauri" / target),
        "--specpath",
        str(root / "build" / "tauri"),
        "--collect-submodules",
        "core",
        "--collect-submodules",
        "mutagen",
        # 2026-11-09: incluye backends nativos para el almacén seguro compartido.
        "--collect-all",
        "keyring",
        "--collect-submodules",
        "keyring.backends",
        "--copy-metadata",
        "keyring",
        str(root / "core" / "desktop_worker.py"),
    ]
    subprocess.run(command, cwd=root, check=True)
    executable = output / name
    if sys.platform == "win32":
        executable = executable.with_suffix(".exe")
    return executable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(build())
