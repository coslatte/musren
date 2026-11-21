import io
import sys

from musren.core.cli.pause import PauseManager


def test_keyboard_listener_ignores_non_tty(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    PauseManager()._keyboard_listener()
