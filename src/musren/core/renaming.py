"""Filename rules and safe file renaming."""

import os
import re
from typing import Any, Optional


def build_target_name(
    file_path: str,
    metadata: dict[str, Any],
    album_counts: dict[str, int],
    rename_format: str,
) -> str:
    """Build a target filename from tags and the selected naming format."""
    artist = metadata["artist"]
    title = metadata["title"]
    album = metadata["album"]
    tracknumber = metadata["tracknumber"]
    is_album = album != "__no_album__" and album_counts.get(album, 0) > 2
    extension = os.path.splitext(file_path)[1]

    if rename_format == "2":
        return f"{title}{extension}"
    if rename_format == "3" and is_album and tracknumber:
        try:
            track_num = int(tracknumber.split("/")[0].split(".")[0])
            return f"{track_num:02d} - {artist} - {title}{extension}"
        except (ValueError, IndexError):
            pass
    return f"{artist} - {title}{extension}"


def preview_rename(
    os_type: str, old_path: str, new_name: str, reserved_paths: set[str]
) -> tuple[str, str, Optional[str]]:
    """Return a sanitized, collision-free destination for a rename preview."""
    directory = os.path.dirname(old_path)
    new_name = sanitize_filename(os_type, new_name)
    new_path = os.path.join(directory, new_name)
    normalized_old = os.path.normcase(old_path)
    normalized_new = os.path.normcase(new_path)

    if normalized_old == normalized_new:
        return new_path, "unchanged", "No change needed."

    base, extension = os.path.splitext(new_name)
    counter = 1
    while os.path.exists(new_path) or normalized_new in reserved_paths:
        new_name = f"{base} ({counter}){extension}"
        new_path = os.path.join(directory, new_name)
        normalized_new = os.path.normcase(new_path)
        counter += 1
    return new_path, "rename", None


def sanitize_filename(os_type, filename):
    """
    Sanitizes the filename according to the operating system.

    Args:
        filename (str): Filename to sanitize

    Returns:
        str: Sanitized filename
    """
    if os_type == "Windows":
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        sanitized = re.sub(invalid_chars, "", filename)
        forbidden_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
        if sanitized.upper() in forbidden_names:
            sanitized = "_" + sanitized
    else:
        sanitized = re.sub(r"/", "-", filename)
        sanitized = sanitized.strip(".")

    sanitized = sanitized.strip()
    max_length = 255
    base, ext = os.path.splitext(sanitized)

    if len(sanitized) > max_length:
        base = base[: max_length - len(ext) - 1]
        sanitized = base + ext

    if not base:
        sanitized = f"audio_file{ext}"

    return sanitized


def safe_rename(directory, os_type, old_name, new_name):
    """
    Renames a file safely, avoiding name conflicts.

    Args:
        old_name (str): Original filename
        new_name (str): New filename

    Returns:
        tuple: (final_name, change_made, error)
    """

    if os.path.isabs(old_name):
        old_path = old_name
        directory = os.path.dirname(old_name)
    else:
        old_path = os.path.join(directory, old_name)
        directory = directory

    new_name = sanitize_filename(os_type, new_name)
    new_path = os.path.join(directory, new_name)

    if os.path.normcase(old_path) == os.path.normcase(new_path):
        return new_path, False, None

    base, extension = os.path.splitext(new_name)
    counter = 1

    while os.path.exists(new_path):
        if os.path.normcase(new_path) == os.path.normcase(old_path):
            break

        new_name = f"{base} ({counter}){extension}"
        new_path = os.path.join(directory, new_name)
        counter += 1

    if os.path.normcase(new_path) == os.path.normcase(old_path):
        return new_path, False, None

    try:
        os.rename(old_path, new_path)
        return new_path, True, None
    except OSError as e:
        return old_path, False, str(e)
