"""Keyboard pause controls for interactive CLI jobs."""

import threading
import time


class PauseManager:
    """Manage pause and resume state with a terminal keyboard listener."""

    def __init__(self):
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._paused.clear()
        self._thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._paused.clear()
        if self._thread:
            self._thread.join(timeout=1)

    @property
    def is_paused(self):
        return self._paused.is_set()

    def toggle(self):
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()

    def wait_if_paused(self, console=None):
        while self._paused.is_set() and not self._stop.is_set():
            if console:
                console.print(
                    "[yellow]⏸ PAUSED — press ESC or P to resume[/yellow]", end="\r"
                )
            time.sleep(0.2)

    def _keyboard_listener(self):
        try:
            import msvcrt

            while not self._stop.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="replace").lower()
                    if key in ("\x1b", "p", "c"):
                        self.toggle()
                time.sleep(0.05)
        except ImportError:
            try:
                import select
                import sys
                import termios
                import tty

                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    while not self._stop.is_set():
                        if select.select([sys.stdin], [], [], 0.05) == (
                            [sys.stdin],
                            [],
                            [],
                        ):
                            key = sys.stdin.read(1).lower()
                            if key in ("\x1b", "p", "c"):
                                self.toggle()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except (ImportError, AttributeError):
                pass


_PAUSE_MANAGER = PauseManager()


def get_pause_manager():
    return _PAUSE_MANAGER
