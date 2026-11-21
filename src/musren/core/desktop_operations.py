"""Validated operation plans and execution adapters for the desktop worker."""

import hashlib
import json
import contextlib
import importlib.util
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from musren.core.jobs import (
    EnrichmentRequest,
    RenameRequest,
    preview_rename_job,
    process_enrichment_file,
)
from musren.core.file_operations import (
    move_file,
    plan_album_moves,
    plan_revert_moves,
)
from musren.utils.audio_files import get_audio_files

Operation = Literal["rename", "lyrics", "covers", "recognize", "albums", "revert"]


@dataclass(frozen=True)
class DesktopRequest:
    """Operation options after validation at the worker boundary."""

    operation: Operation
    directory: Path
    recursive: bool
    options: dict[str, Any]


def parse_operation_request(payload: Any) -> DesktopRequest:
    """Validate the JSON job payload and normalize its supported options."""
    if not isinstance(payload, dict):
        raise ValueError("A job request is required.")
    operation = payload.get("operation")
    if operation not in ("rename", "lyrics", "covers", "recognize", "albums", "revert"):
        raise ValueError("Choose a supported operation.")
    directory = payload.get("directory")
    recursive = payload.get("recursive", False)
    options = payload.get("options", {})
    if not isinstance(directory, str) or not directory:
        raise ValueError("A directory path is required.")
    path = Path(directory).expanduser()
    if not path.is_dir():
        raise ValueError("Choose an existing directory.")
    if not isinstance(recursive, bool) or not isinstance(options, dict):
        raise ValueError("Invalid operation options.")
    if operation == "revert":
        recursive = True

    allowed_options = {
        "rename": {"rename_format"},
        "recognize": {"provider"},
        "lyrics": {"recognize_first", "fetch_covers"},
        "covers": set(),
        "albums": set(),
        "revert": set(),
    }[operation]
    if set(options) - allowed_options:
        raise ValueError("This operation contains unsupported options.")

    normalized: dict[str, Any] = {"recursive": recursive}
    if operation == "rename":
        rename_format = options.get("rename_format", "artist_title")
        if rename_format not in ("artist_title", "title", "track_artist_title"):
            raise ValueError("Choose a supported rename format.")
        normalized["rename_format"] = rename_format
    elif operation == "recognize":
        provider = options.get("provider", "acoustid")
        if provider not in ("acoustid", "shazam"):
            raise ValueError("Choose a supported recognition provider.")
        normalized["provider"] = provider
    elif operation == "lyrics":
        for key in ("recognize_first", "fetch_covers"):
            if key in options and not isinstance(options[key], bool):
                raise ValueError(f"Invalid {key.replace('_', ' ')} option.")
            normalized[key] = options.get(key, False)
    return DesktopRequest(operation, path.resolve(), recursive, normalized)


def prepare_operation(
    request: DesktopRequest,
    on_scan: Optional[Callable[[str, int, int], None]] = None,
) -> dict[str, Any]:
    """Create a stable file plan and token for preview confirmation."""
    if request.operation == "recognize" and request.options.get("provider") == "shazam":
        try:
            shazam_available = importlib.util.find_spec("shazamio") is not None
        except (ImportError, ValueError):
            shazam_available = False
        if not shazam_available:
            raise RuntimeError(
                "Shazam recognition requires the optional dependency. Install it with pip install 'musren[shazam]'."
            )
    if request.operation == "rename":
        preview = preview_rename_job(
            RenameRequest(
                request.directory, request.recursive, request.options["rename_format"]
            ),
            on_scan=on_scan,
        )
        result = preview.to_dict()
        result["preview_token"] = preview.token
        return result

    files = _files(request)
    if request.operation == "albums":
        entries = _album_plan(request, files, on_scan)
    elif request.operation == "revert":
        entries = _revert_plan(request, files, on_scan)
    else:
        entries = []
        for index, path in enumerate(files, start=1):
            if on_scan:
                on_scan(path, index, len(files))
            entries.append(_service_plan(request, Path(path)))
    token_source = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    token = hashlib.sha256(token_source.encode("utf-8")).hexdigest()
    actions = [entry["action"] for entry in entries]
    return {
        "preview_token": token,
        "total_files": len(entries),
        "planned_changes": sum(
            action in ("rename", "move", "process") for action in actions
        ),
        "skipped_files": sum(action == "skipped" for action in actions),
        "unchanged_files": sum(action == "unchanged" for action in actions),
        "files": entries,
    }


def history_preview_files(preview: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a preview into durable per-file before and planned states."""
    records = []
    for entry in preview["files"]:
        path = entry["path"]
        before = entry.get("before", {"path": path})
        after = entry.get("planned_after", {"path": entry.get("target_path") or path})
        records.append(
            {
                "path": path,
                "before": before,
                "planned_after": after,
                "action": entry["action"],
                "reason": entry.get("reason"),
            }
        )
    return records


def execute_operation(
    request: DesktopRequest,
    preview: dict[str, Any],
    *,
    on_file: Callable[[str, dict[str, Any], Optional[dict[str, Any]]], None],
    checkpoint: Callable[[], None],
    progress: Callable[[str, int, int], None],
    acoustid_key: Optional[str] = None,
) -> tuple[int, int]:
    """Run one confirmed plan, reporting each result and safe cancellation point."""
    if request.operation == "rename":
        return _execute_rename(request, preview, on_file, checkpoint, progress)

    total = len(preview["files"])
    changed = errors = 0
    processor = None
    if request.operation in ("lyrics", "recognize"):
        from musren.core.audio_processor import AudioProcessor

        if request.options.get("provider") == "shazam":
            try:
                import shazamio  # noqa: F401
            except ImportError as error:
                raise RuntimeError(
                    "Shazam recognition requires the optional Shazam dependency."
                ) from error

        with contextlib.redirect_stdout(sys.stderr):
            processor = AudioProcessor(
                str(request.directory),
                acoustid_api_key=acoustid_key,
                max_workers=1,
                recursive=request.recursive,
                use_shazam=request.options.get("provider") == "shazam",
            )
    for index, entry in enumerate(preview["files"], start=1):
        checkpoint()
        path = entry["path"]
        if entry["action"] in ("skipped", "unchanged"):
            result = {
                "skipped": entry["action"] == "skipped",
                "reason": entry.get("reason"),
            }
            after = entry.get("before", {"path": path})
        else:
            try:
                result, after = _process_file(
                    request, Path(path), entry, {"processor": processor}
                )
            except Exception as error:
                result, after = (
                    {"error": str(error)},
                    entry.get("before", {"path": path}),
                )
        if (
            result.get("error")
            or result.get("status") is False
            or result.get("metadata_error")
            or result.get("embed_error")
            or result.get("cover_error")
        ):
            errors += 1
            outcome = "failed"
        elif result.get("recognition") is False or result.get("lyrics_found") is False:
            outcome = "skipped"
        elif result.get("skipped"):
            outcome = "skipped"
        else:
            outcome = "processed"
            changed += int(
                after != entry.get("before", {"path": path})
                or request.operation == "covers"
            )
        result["outcome"] = outcome
        if outcome == "skipped" and not result.get("reason"):
            result["reason"] = result.get("recognition_error") or result.get(
                "lyrics_error"
            )
        on_file(path, {**result, "outcome": outcome}, after)
        progress(path, index, total)
        checkpoint()
    return changed, errors


def _execute_rename(request, preview, on_file, checkpoint, progress):
    from musren.core.jobs import run_rename_job

    changes: dict[str, str] = {}
    errors = 0
    processed = 0
    total = len(preview["files"])

    def on_result(path: str, result: dict[str, Any]) -> None:
        nonlocal errors, processed
        checkpoint()
        processed += 1
        after_path = (
            str(Path(path).with_name(result["new_name"]))
            if result.get("renamed")
            else path
        )
        if result.get("renamed"):
            changes[after_path] = path
        if result.get("error"):
            errors += 1
        on_file(path, result, {"path": after_path})
        progress(path, processed, total)

    run_rename_job(
        RenameRequest(
            request.directory, request.recursive, request.options["rename_format"]
        ),
        on_file=on_result,
        expected_preview_token=preview["preview_token"],
    )
    return len(changes), errors


def _process_file(request, path: Path, entry: dict[str, Any], local: dict[str, Any]):
    before = entry.get("before", {"path": str(path)})
    if request.operation == "covers":
        from musren.core.install_covers import process_file
        from musren.core.artwork import AlbumArtManager

        result = process_file(str(path), AlbumArtManager())
        return result, {
            **before,
            "cover": "present"
            if result.get("status") and not result.get("skipped")
            else before.get("cover", "missing"),
        }

    if request.operation in ("lyrics", "recognize"):
        processor = local["processor"]
        recognize = request.operation == "recognize" or request.options.get(
            "recognize_first", False
        )
        lyrics = request.operation == "lyrics"
        with contextlib.redirect_stdout(sys.stderr):
            result = process_enrichment_file(
                processor,
                str(path),
                EnrichmentRequest(
                    recognition=recognize,
                    lyrics=lyrics,
                    covers=request.options.get("fetch_covers", False),
                ),
            )
        after = _metadata_snapshot(path)
        return result, after

    if request.operation in ("albums", "revert"):
        destination = Path(entry["target_path"])
        if destination.resolve() == path.resolve():
            return {
                "skipped": True,
                "reason": "The file is already in its planned location.",
            }, before
        destination = move_file(path, destination, on_conflict="error")
        return {"moved": True, "new_path": str(destination)}, {
            **before,
            "path": str(destination),
        }
    raise ValueError("Unsupported operation.")


def _files(request: DesktopRequest) -> list[str]:
    files = get_audio_files(str(request.directory), recursive=request.recursive)
    if request.operation == "revert":
        return [path for path in files if Path(path).parent != request.directory]
    return files


def _album_plan(
    request: DesktopRequest, files: list[str], on_scan=None
) -> list[dict[str, Any]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for index, raw_path in enumerate(files, start=1):
        if on_scan:
            on_scan(raw_path, index, len(files))
        path = Path(raw_path)
        album = _metadata_snapshot(path).get("album") or "Unknown Album"
        groups[str(album)].append(path)

    moves_by_source = dict(plan_album_moves(request.directory, groups))
    entries = []
    for track, target in moves_by_source.items():
        if target.resolve() == track.resolve():
            snapshot = _metadata_snapshot(track)
            entries.append(
                {
                    "path": str(track),
                    "current_name": track.name,
                    "target_path": str(track),
                    "target_name": track.name,
                    "action": "unchanged",
                    "reason": None,
                    "before": snapshot,
                    "planned_after": snapshot,
                }
            )
        else:
            entries.append(_move_entry(track, target))
    return entries


def _revert_plan(
    request: DesktopRequest, files: list[str], on_scan=None
) -> list[dict[str, Any]]:
    paths = [Path(raw_path) for raw_path in files]
    moves = plan_revert_moves(request.directory, paths)
    entries = []
    for index, (path, target) in enumerate(moves, start=1):
        if on_scan:
            on_scan(str(path), index, len(files))
        entries.append(_move_entry(path, target))
    return entries


def _move_entry(source: Path, target: Path) -> dict[str, Any]:
    before = _metadata_snapshot(source)
    return {
        "path": str(source),
        "current_name": source.name,
        "target_path": str(target),
        "target_name": target.name,
        "action": "move",
        "reason": None,
        "before": before,
        "planned_after": {**before, "path": str(target)},
    }


def _service_plan(request: DesktopRequest, path: Path) -> dict[str, Any]:
    before = _metadata_snapshot(path)
    action = "process"
    reason = None
    if request.operation == "covers" and before.get("cover") == "present":
        action, reason = "skipped", "A cover is already embedded."
    return {
        "path": str(path),
        "current_name": path.name,
        "target_path": str(path),
        "target_name": path.name,
        "action": action,
        "reason": reason,
        "before": before,
        "planned_after": before,
    }


def _metadata_snapshot(path: Path) -> dict[str, Any]:
    from mutagen._file import File as MutagenFile

    snapshot: dict[str, Any] = {"path": str(path)}
    try:
        audio = MutagenFile(path, easy=True)
    except Exception as error:
        return {**snapshot, "metadata_error": type(error).__name__}
    if audio:
        for field in (
            "artist",
            "title",
            "album",
            "albumartist",
            "tracknumber",
            "date",
            "genre",
            "lyrics",
        ):
            values = audio.get(field)
            if values:
                snapshot[field] = [str(value) for value in values]
        snapshot["cover"] = "present" if _has_cover(path) else "missing"
    return snapshot


def _has_cover(path: Path) -> bool:
    try:
        if path.suffix.lower() == ".mp3":
            from mutagen.id3 import ID3

            return any(frame.startswith("APIC") for frame in ID3(path).keys())
        if path.suffix.lower() == ".flac":
            from mutagen.flac import FLAC

            return bool(FLAC(path).pictures)
        if path.suffix.lower() == ".m4a":
            from mutagen.mp4 import MP4

            return "covr" in MP4(path)
    except Exception:
        return False
    return False
