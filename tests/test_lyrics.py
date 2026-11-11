import sys
import types

import pytest
import requests

import core.lyrics as lyrics


class _Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No provider in this suite may touch the network."""
    monkeypatch.setattr(lyrics, "check_internet_connection", lambda: True)

    module = types.ModuleType("syncedlyrics")
    module.search = lambda term, **kwargs: ""
    monkeypatch.setitem(sys.modules, "syncedlyrics", module)

    calls = []
    monkeypatch.setattr(requests, "get", lambda url, **kw: calls.append(url))
    return calls


def _route(monkeypatch, routes):
    def fake_get(url, **kwargs):
        for fragment, response in routes.items():
            if fragment in url:
                return response
        return _Response(status_code=404)

    monkeypatch.setattr(requests, "get", fake_get)


def test_exact_lookup_wins_when_the_length_agrees(monkeypatch):
    _route(
        monkeypatch,
        {
            "/get": _Response(
                payload={
                    "syncedLyrics": "[00:01.00]Hello",
                    "duration": 208.0,
                }
            )
        },
    )

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == (
        "[00:01.00]Hello",
        "lrclib",
    )


def test_another_take_is_rejected_on_both_lookups(monkeypatch):
    _route(
        monkeypatch,
        {
            "/get": _Response(
                payload={"syncedLyrics": "[00:01.00]Wrong", "duration": 312.0}
            ),
            "/search": _Response(
                payload=[{"syncedLyrics": "[00:01.00]Wrong", "duration": 312.0}]
            ),
        },
    )

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == ("", "")


def test_search_hit_is_accepted_only_within_its_tighter_slack(monkeypatch):
    """8s of drift is a remaster for an exact title but too much for a search
    hit, whose title only has to contain ours."""
    _route(
        monkeypatch,
        {
            "/get": _Response(status_code=404),
            "/search": _Response(
                payload=[{"syncedLyrics": "[00:01.00]Close", "duration": 208.0}]
            ),
        },
    )
    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == ("", "")

    _route(
        monkeypatch,
        {
            "/get": _Response(status_code=404),
            "/search": _Response(
                payload=[{"syncedLyrics": "[00:01.00]Close", "duration": 204.0}]
            ),
        },
    )
    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == (
        "[00:01.00]Close",
        "lrclib",
    )


def _itunes_result(title="Title", artist="Artist", millis=200_000, track_id=1):
    return {
        "trackId": track_id,
        "trackName": title,
        "artistName": artist,
        "trackTimeMillis": millis,
    }


def _apple_payload():
    """A trimmed answer of the shape /apple-music/lyrics actually returns."""
    return {
        "type": "Syllable",
        "content": [
            {
                "timestamp": 31405,
                "text": [
                    {"text": "Like", "timestamp": 31405, "part": False},
                    {"text": "the", "timestamp": 31702, "part": False},
                    {"text": "PHO", "timestamp": 31934, "part": False},
                    {"text": "enix", "timestamp": 32470, "part": True},
                ],
            }
        ],
    }


def _apple_chain(monkeypatch, results):
    _route(
        monkeypatch,
        {
            "/api/get": _Response(status_code=404),
            "lrclib.net/api/search": _Response(payload=[]),
            "itunes.apple.com": _Response(payload={"results": results}),
            "apple-music": _Response(payload=_apple_payload()),
        },
    )


def test_paxsenix_returns_syllable_timed_lrc(monkeypatch):
    _apple_chain(monkeypatch, [_itunes_result()])

    text, provider = lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0)
    assert provider == "paxsenix"
    # Line stamp, then one inline tag per syllable, and a "part" fragment
    # closing up the previous word instead of starting a new one.
    assert text == (
        "[00:31.40]<00:31.40>Like <00:31.70>the <00:31.93>PHO<00:32.47>enix"
    )


def test_paxsenix_rejects_a_cover_with_another_artist(monkeypatch):
    _apple_chain(monkeypatch, [_itunes_result(artist="Somebody Else")])

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == ("", "")


def test_paxsenix_rejects_a_result_of_another_length(monkeypatch):
    _apple_chain(monkeypatch, [_itunes_result(millis=310_000)])

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == ("", "")


def test_paxsenix_is_skipped_without_a_known_length(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "get", lambda url, **kw: calls.append(url))

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 0.0) == ("", "")
    assert not any("itunes.apple.com" in url for url in calls)


def test_search_is_still_tried_when_the_exact_lookup_is_throttled(monkeypatch):
    """LRCLIB throttles /get and /search independently, so a 429 on one must
    not skip the other."""

    def fake_get(url, **kwargs):
        if url.endswith("/get"):
            return _Response(status_code=429)
        return _Response(
            payload=[{"syncedLyrics": "[00:01.00]Found", "duration": 200.0}]
        )

    monkeypatch.setattr(requests, "get", fake_get)

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == (
        "[00:01.00]Found",
        "lrclib",
    )


def test_plain_text_is_never_reported_as_synchronized(monkeypatch):
    module = sys.modules["syncedlyrics"]
    module.search = lambda term, **kwargs: "Just words, no timings here"

    assert lyrics.fetch_lyrics("Artist", "Title", "Album", 200.0) == ("", "")
