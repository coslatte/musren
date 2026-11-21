"""Shared file movement rules for audio operations."""

import shutil
from pathlib import Path
from typing import Literal


def nonconflicting_destination(
    target: Path, reserved: set[Path], source: Path | None = None
) -> Path:
    """Return a destination path that does not overwrite an existing file."""
    candidate = target
    counter = 1
    while candidate.exists() or (
        candidate.resolve() in reserved
        and (source is None or candidate.resolve() != source.resolve())
    ):
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        counter += 1
    return candidate


def album_folder(album: str, track_count: int) -> str:
    """Choose the destination folder for an album group."""
    normalized = album.lower().strip()
    is_single = normalized in ("single", "singles", "unknown album", "")
    if is_single or track_count == 1:
        return "Singles"
    safe = "".join(char for char in album if char.isalnum() or char in (" ", "-", "_"))
    return safe.rstrip() or "Unknown Album"


def move_file(
    source: Path, target: Path, *, on_conflict: Literal["suffix", "error"] = "suffix"
) -> Path:
    """Move a file to an available destination and return its final path."""
    if source.resolve() == target.resolve():
        return source
    if on_conflict == "error" and target.exists():
        raise FileExistsError(
            "A file appeared at the planned destination. The source was left in place."
        )
    destination = nonconflicting_destination(target, set())
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def plan_revert_moves(directory: Path, files: list[Path]) -> list[tuple[Path, Path]]:
    """Plan root destinations for nested audio files without collisions."""
    reserved: set[Path] = set()
    moves = []
    for source in files:
        target = nonconflicting_destination(directory / source.name, reserved)
        reserved.add(target.resolve())
        moves.append((source, target))
    return moves


def plan_album_moves(
    directory: Path, groups: dict[str, list[Path]]
) -> list[tuple[Path, Path]]:
    """Plan album folders and collision-free destinations for grouped tracks."""
    reserved = {path.resolve() for tracks in groups.values() for path in tracks}
    moves = []
    for album, tracks in groups.items():
        folder = album_folder(album, len(tracks))
        for source in tracks:
            target = nonconflicting_destination(
                directory / folder / source.name, reserved, source
            )
            reserved.add(target.resolve())
            moves.append((source, target))
    return moves
