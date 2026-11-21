import hashlib
import importlib.util
from pathlib import Path

import pytest

release_script = Path(__file__).resolve().parents[1] / "scripts" / "verify_release.py"
module_spec = importlib.util.spec_from_file_location("verify_release", release_script)
assert module_spec is not None and module_spec.loader is not None
release_module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(release_module)
write_checksums = release_module.write_checksums


def test_write_checksums_includes_nested_desktop_assets(tmp_path: Path) -> None:
    wheel = tmp_path / "musren.whl"
    package = tmp_path / "desktop" / "musren-linux.deb"
    wheel.write_bytes(b"python package")
    package.parent.mkdir()
    package.write_bytes(b"desktop package")
    (tmp_path / ".gitignore").write_text("ignored build output", encoding="utf-8")

    assert write_checksums(tmp_path) == 2
    manifest = (tmp_path / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert f"{hashlib.sha256(wheel.read_bytes()).hexdigest()}  musren.whl" in manifest
    assert (
        f"{hashlib.sha256(package.read_bytes()).hexdigest()}  musren-linux.deb"
        in manifest
    )


def test_write_checksums_rejects_duplicate_asset_names(tmp_path: Path) -> None:
    (tmp_path / "windows").mkdir()
    (tmp_path / "macos").mkdir()
    (tmp_path / "windows" / "musren.zip").write_bytes(b"windows")
    (tmp_path / "macos" / "musren.zip").write_bytes(b"macos")

    with pytest.raises(AssertionError, match="filenames must be unique"):
        write_checksums(tmp_path)
