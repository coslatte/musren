"""Check local Markdown links in the README, agent guide, and documentation."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "README.md",
        root / "AGENTS.md",
        *sorted((root / "docs").glob("*.md")),
    ]
    broken = []
    for document in files:
        for target in re.findall(
            r"\[[^\]]+\]\(([^\s)]+)\)", document.read_text(encoding="utf-8")
        ):
            parsed = urlsplit(target)
            if not parsed.scheme and parsed.path:
                path = document.parent / unquote(parsed.path)
                if not path.exists():
                    broken.append(f"{document.relative_to(root)}: {target}")
    if broken:
        raise SystemExit("Broken documentation links:\n" + "\n".join(broken))
    print(f"Local links verified in {len(files)} Markdown documents")


if __name__ == "__main__":
    main()
