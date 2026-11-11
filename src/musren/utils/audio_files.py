"""Audio file discovery for processing operations."""

import os

from musren.constants.settings import AUDIO_EXTENSIONS


def get_audio_files(directory, recursive=False):
    """Return supported audio file paths from a directory."""
    directory = os.path.abspath(directory)
    files = []

    if recursive:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if filename.lower().endswith(AUDIO_EXTENSIONS):
                    files.append(os.path.join(root, filename))
    else:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and filename.lower().endswith(AUDIO_EXTENSIONS):
                files.append(filepath)
    return files
