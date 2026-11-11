"""Logging settings for third-party lyrics providers."""

import logging

_NOISY_LOGGERS = {
    "syncedlyrics",
    "syncedlyrics.providers.musixmatch",
    "Musixmatch",
    "Lrclib",
    "NetEase",
    "Deezer",
    "Megalobiz",
    "Lyricsify",
    "Genius",
}


def suppress_noisy_loggers() -> None:
    """Silence verbose loggers used by lyrics providers."""
    for name in _NOISY_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.handlers.clear()
        logger.propagate = False
