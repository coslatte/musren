"""Build validated CLI arguments shared by the TUI and its tests."""

from dataclasses import dataclass
from pathlib import Path
from typing import List

OPERATIONS = {
    "rename": "Rename files",
    "lyrics": "Embed lyrics",
    "covers": "Embed covers",
    "recognize": "Recognize audio",
    "albums": "Organize albums",
    "revert": "Revert album organization",
}


@dataclass(frozen=True)
class Job:
    operation: str
    directory: Path
    recursive: bool = False
    rename_format: str = "1"
    recognition: bool = False
    covers: bool = False
    shazam: bool = False

    def arguments(self) -> List[str]:
        """Validate external input and preserve paths as individual arguments."""
        if self.operation not in OPERATIONS:
            raise ValueError("Select a supported operation.")
        if not self.directory.is_dir():
            raise ValueError("Choose an existing directory.")
        if self.rename_format not in ("1", "2", "3"):
            raise ValueError("Select a valid rename format.")
        command = (
            ["albums", "revert"] if self.operation == "revert" else [self.operation]
        )
        if self.operation != "revert":
            command.append("run")
        command.extend(["--directory", str(self.directory.resolve())])
        if self.recursive and self.operation != "revert":
            command.append("--recursive")
        if self.operation == "rename":
            command.extend(["--format", self.rename_format])
        else:
            command.append("--yes")
        if self.operation == "lyrics":
            if self.recognition:
                command.append("--recognition")
            if self.covers:
                command.append("--covers")
        if self.operation == "recognize" and self.shazam:
            command.append("--shazam")
        return command
