"""Synchronized lyrics providers, queried in order until one answers."""

import re
from typing import Tuple

from constants.info import MUSIC_RENAMER_URL, MUSIC_RENAMER_VERSION
from utils.tools import check_internet_connection, suppress_noisy_loggers

_LRCLIB_API = "https://lrclib.net/api"
_ITUNES_SEARCH = "https://itunes.apple.com/search"
_PAXSENIX_APPLE = "https://lyrics.paxsenix.org/apple-music/lyrics"
_TIMEOUT = 10

# Both services ask callers to identify themselves. LRCLIB throttles hard
# otherwise, answering 429 to a large share of requests.
_HEADERS = {"User-Agent": f"musren/{MUSIC_RENAMER_VERSION} ({MUSIC_RENAMER_URL})"}

# A candidate whose length misses by more than this is a different take, not
# the same song. An exact title allows a remaster's few seconds; a search hit
# that merely contains the title has to agree much more closely.
_EXACT_SLACK_S = 10
_SEARCH_SLACK_S = 5

_LRC_TIMESTAMP = re.compile(r"\[\d+:\d{2}[.\d]*\]")


def fetch_lyrics(
    artist: str,
    title: str,
    album: str = "",
    duration: float = 0.0,
) -> Tuple[str, str]:
    """
    Searches for synchronized lyrics through the provider chain.

    Args:
        artist (str): Artist name
        title (str): Song title
        album (str): Album name, narrows the LRCLib lookup
        duration (float): Track length in seconds, rejects another recording

    Returns:
        tuple: (lrc text, provider name), both empty when nothing matched
    """
    if not check_internet_connection():
        return "", ""

    for provider in (_lrclib, _paxsenix, _syncedlyrics):
        try:
            text, name = provider(artist, title, album, duration)
        except Exception:
            continue
        if text and _LRC_TIMESTAMP.search(text):
            return text.strip(), name

    return "", ""


def _within_slack(expected: float, found: float, slack: float) -> bool:
    """Whether a provider's answer is the recording actually on disk."""
    if expected <= 0 or found <= 0:
        return True
    return abs(expected - found) <= slack


def _lrclib(artist: str, title: str, album: str, duration: float) -> Tuple[str, str]:
    """LRCLib: an exact lookup first, then search results filtered by length."""
    import requests

    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    if duration > 0:
        params["duration"] = int(duration)

    response = requests.get(
        f"{_LRCLIB_API}/get", params=params, headers=_HEADERS, timeout=_TIMEOUT
    )
    if response.status_code == 200:
        data = response.json()
        text = data.get("syncedLyrics") or ""
        if text and _within_slack(duration, data.get("duration", 0), _EXACT_SLACK_S):
            return text, "lrclib"

    # LRCLIB throttles each endpoint independently, so a throttled /get is not
    # a sign /search will be too. Keep going either way.
    response = requests.get(
        f"{_LRCLIB_API}/search",
        params={"artist_name": artist, "track_name": title},
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    if response.status_code != 200:
        return "", ""

    for item in response.json():
        text = item.get("syncedLyrics") or ""
        if text and _within_slack(duration, item.get("duration", 0), _SEARCH_SLACK_S):
            return text, "lrclib"

    return "", ""


def _words(text: str) -> str:
    """Comparable form of a title: lowercase, words only."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _best_itunes_track(results, title, artist, duration):
    """The iTunes result that is actually our track, or None.

    Both title and artist have to agree: an iTunes search for a single name
    happily returns a cover or a remix of a different song, and its lyrics
    would then be embedded on the wrong file.
    """
    wanted_title = _words(title)
    wanted_artists = set(_words(artist).split())

    for item in results or []:
        found_title = _words(item.get("trackName"))
        if not found_title or wanted_title not in found_title:
            continue
        if not wanted_artists & set(_words(item.get("artistName")).split()):
            continue

        length = (item.get("trackTimeMillis") or 0) / 1000.0
        if length and duration and abs(length - duration) > _EXACT_SLACK_S:
            continue

        if item.get("trackId"):
            return str(item["trackId"])

    return None


def _timestamp(milliseconds) -> str:
    """Milliseconds as the mm:ss.xx stamp LRC uses."""
    minutes, rest = divmod(max(0, int(milliseconds)), 60000)
    seconds, rest = divmod(rest, 1000)
    return f"{minutes:02d}:{seconds:02d}.{rest // 10:02d}"


def _apple_lrc(payload) -> str:
    """Apple's syllable-timed payload as enhanced LRC.

    Every syllable carries its own timestamp, so each one becomes an inline
    <mm:ss.xx> tag under the line's own. A part flagged ``part`` continues the
    syllable before it ("ex|pres|sions"), so it gets no leading space or the
    word renders broken apart.
    """
    lines = []
    for line in (payload or {}).get("content") or []:
        stamp = line.get("timestamp", 0)
        words = ""
        for part in line.get("text") or []:
            text = part.get("text") or ""
            if not text:
                continue
            gap = "" if part.get("part") else " "
            words += f"{gap}<{_timestamp(part.get('timestamp', stamp))}>{text}"
        if words.strip():
            lines.append(f"[{_timestamp(stamp)}]{words.strip()}")

    return "\n".join(lines)


def _paxsenix(artist: str, title: str, album: str, duration: float) -> Tuple[str, str]:
    """Apple Music syllable-level lyrics, located with the public iTunes
    Search API and fetched through Paxsenix.

    Paxsenix retired its Musixmatch endpoint with a 403 in favour of this one;
    its other relay endpoints are undocumented and unverified.
    """
    if duration <= 0:
        return "", ""

    import requests

    search = requests.get(
        _ITUNES_SEARCH,
        params={
            "term": f"{title} {artist}",
            "media": "music",
            "entity": "song",
            "limit": 5,
            "country": "US",
        },
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    if search.status_code != 200:
        return "", ""

    track_id = _best_itunes_track(search.json().get("results"), title, artist, duration)
    if not track_id:
        return "", ""

    response = requests.get(
        _PAXSENIX_APPLE,
        params={"id": track_id},
        headers={**_HEADERS, "Accept": "application/json"},
        timeout=_TIMEOUT,
    )
    if response.status_code != 200:
        return "", ""

    return _apple_lrc(response.json()), "paxsenix"


def _syncedlyrics(
    artist: str, title: str, album: str, duration: float
) -> Tuple[str, str]:
    """Last resort: the bundled optional extra, which fans out to seven
    catalogues of its own. ``enhanced`` asks for word-level timings and falls
    back to plain synced lyrics where the catalogue has none."""
    try:
        import syncedlyrics
    except ImportError:
        return "", ""

    suppress_noisy_loggers()
    lrc_content = syncedlyrics.search(f"{artist} {title}", enhanced=True)
    suppress_noisy_loggers()

    return (lrc_content or ""), "syncedlyrics"
