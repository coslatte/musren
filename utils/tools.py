import os
from constants.settings import AUDIO_EXTENSIONS


def get_audio_files(directory, recursive=False):
    """
    Obtiene todos los archivos de audio en el directorio especificado.

    Args:
        directory (str): Directorio a buscar
        recursive (bool): Si buscar en subdirectorios

    Returns:
        list: Lista de rutas absolutas de archivos de audio
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
            if f.lower().endswith(audio_extensions):
                files.append(os.path.join(directory, f))

    return files
