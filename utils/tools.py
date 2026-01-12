import os
from constants.settings import AUDIO_EXTENSIONS


def get_audio_files(directory, recursive=False):
    """
    Gets all audio files in the specified directory.

    Args:
        directory (str): Directory to search
        recursive (bool): Whether to search in subdirectories

    Returns:
        list: List of absolute paths to audio files
    """

    directory = os.path.abspath(directory)
    audio_extensions = AUDIO_EXTENSIONS
    files = []

    if recursive:
        for root, _, filenames in os.walk(directory):
            for f in filenames:
                if f.lower().endswith(audio_extensions):
                    files.append(os.path.join(root, f))
    else:
        for f in os.listdir(directory):
            filepath = os.path.join(directory, f)
            if os.path.isfile(filepath) and f.lower().endswith(audio_extensions):
                files.append(filepath)
    return files
