"""Shared job operations used by desktop adapters."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from utils.tools import get_audio_files

RENAME_FORMATS = {
    "artist_title": "1",
    "title": "2",
    "track_artist_title": "3",
}

RenameAction = Literal["rename", "unchanged", "skipped"]


@dataclass(frozen=True)
class RenameRequest:
    directory: Path
    recursive: bool = False
    rename_format: str = "artist_title"

    def __post_init__(self) -> None:
        if not self.directory.is_dir():
            raise ValueError("Choose an existing directory.")
        if self.rename_format not in RENAME_FORMATS:
            raise ValueError("Choose a supported rename format.")


@dataclass(frozen=True)
class RenamePreviewEntry:
    path: str
    current_name: str
    target_path: Optional[str]
    target_name: Optional[str]
    action: RenameAction
    reason: Optional[str]


@dataclass(frozen=True)
class RenamePreview:
    token: str
    total_files: int
    planned_changes: int
    skipped_files: int
    unchanged_files: int
    files: tuple[RenamePreviewEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned worker payload shape."""
        return {
            "total_files": self.total_files,
            "planned_changes": self.planned_changes,
            "skipped_files": self.skipped_files,
            "unchanged_files": self.unchanged_files,
            "files": [asdict(entry) for entry in self.files],
        }


def preview_rename_job(
    request: RenameRequest,
    on_scan: Optional[Callable[[str, int, int], None]] = None,
) -> RenamePreview:
    """Return the exact rename plan and a token tied to its current files."""
    from core.audio_processor import AudioProcessor

    processor = AudioProcessor(
        directory=str(request.directory), recursive=request.recursive
    )
    rows = processor.preview_rename_files(
        rename_format=RENAME_FORMATS[request.rename_format],
        scan_callback=on_scan,
    )
    entries = tuple(RenamePreviewEntry(**row) for row in rows)
    file_state = []
    for entry in entries:
        stat = Path(entry.path).stat()
        file_state.append(
            {
                "path": entry.path,
                "target_path": entry.target_path,
                "action": entry.action,
                "size": stat.st_size,
                "modified_ns": stat.st_mtime_ns,
            }
        )

    request_state = {
        "directory": str(request.directory.resolve()),
        "recursive": request.recursive,
        "rename_format": request.rename_format,
        "files": file_state,
    }
    token = hashlib.sha256(
        json.dumps(request_state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return RenamePreview(
        token=token,
        total_files=len(entries),
        planned_changes=sum(entry.action == "rename" for entry in entries),
        skipped_files=sum(entry.action == "skipped" for entry in entries),
        unchanged_files=sum(entry.action == "unchanged" for entry in entries),
        files=entries,
    )


def run_rename_job(
    request: RenameRequest,
    on_scan: Optional[Callable[[str], None]] = None,
    on_file: Optional[Callable[[str, dict[str, Any]], None]] = None,
    expected_preview_token: Optional[str] = None,
) -> dict[str, str]:
    """Run the shared rename engine after checking the reviewed preview."""
    if expected_preview_token is not None:
        current_preview = preview_rename_job(request)
        if current_preview.token != expected_preview_token:
            raise ValueError(
                "Files changed after the preview. Run a new preview before renaming."
            )

    from core.audio_processor import AudioProcessor

    processor = AudioProcessor(
        directory=str(request.directory), recursive=request.recursive
    )
    return processor.rename_files(
        rename_format=RENAME_FORMATS[request.rename_format],
        scan_callback=on_scan,
        progress_callback=on_file,
    )


def undo_rename_job(
    changes: dict[str, str],
    on_file: Optional[Callable[[str, dict[str, Any]], None]] = None,
) -> None:
    """Restore completed rename changes using the shared audio engine."""
    from core.audio_processor import AudioProcessor

    AudioProcessor().undo_rename(changes, progress_callback=on_file)
