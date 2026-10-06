#!/usr/bin/env python3
"""Make README.md's relative links absolute before building the PyPI package.

PyPI shows the README as the project page but can't resolve links relative to
the repository, so images and doc links would break there. Run in CI just
before ``python -m build`` (#118); the committed README keeps relative links.

    python tools/pypi_readme.py README.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = "https://github.com/TMHSDigital/autoclicker"
RAW = "https://raw.githubusercontent.com/TMHSDigital/autoclicker/main"

# src="docs/..." (images) and ](docs/...) / href="docs/..." (links), plus the
# other repository files the README points at.
_RELATIVE = (
    r"(?!https?:|#|mailto:)"
    r"((?:docs|autoclicker|\.github)/[^\"')\s]*|(?:[A-Z]+\.md|LICENSE)[^\"')\s]*)"
)


def absolutize(text: str) -> str:
    text = re.sub(r'src="' + _RELATIVE, lambda m: f'src="{RAW}/{m.group(1)}', text)
    text = re.sub(r'href="' + _RELATIVE, lambda m: f'href="{REPO}/blob/main/{m.group(1)}', text)
    return re.sub(r"\]\(" + _RELATIVE, lambda m: f"]({REPO}/blob/main/{m.group(1)}", text)


def main(argv: list[str]) -> int:
    path = Path(argv[0] if argv else "README.md")
    path.write_text(absolutize(path.read_text("utf-8")), "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
