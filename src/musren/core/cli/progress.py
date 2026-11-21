"""Formatting helpers for CLI progress displays."""

import re

PROGRESS_DESC_WIDTH = 60


def format_progress_desc(text: str, width: int = PROGRESS_DESC_WIDTH) -> str:
    """Strip Rich markup, then pad or truncate text to a fixed width."""
    plain = re.sub(r"\[/?\w+(?:=\w+)?\]", "", text)
    if len(plain) > width:
        return plain[: width - 3] + "..."
    padding = width - len(plain)
    return text + " " * padding if padding > 0 else text
