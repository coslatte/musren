"""Source-checkout shim for the installed musren entry points."""

import sys
from pathlib import Path

_SOURCE = str(Path(__file__).resolve().parent / "src")
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from musren.entrypoint import main, tui  # noqa: E402

__all__ = ["main", "tui"]


if __name__ == "__main__":
    main()
