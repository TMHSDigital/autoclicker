# SPDX-License-Identifier: CC-BY-NC-4.0
"""Resolve bundled assets for source, pip/pipx, and frozen (PyInstaller) runs.

Assets live in the package at ``autoclicker/assets/`` so wheels include them;
the PyInstaller spec copies them to the same relative folder.
"""

from __future__ import annotations

import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def resource_path(name: str) -> Path:
    """Locate asset ``name``; returns the package path even if it is missing."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "autoclicker" / "assets" / name)
    candidates.append(ASSETS_DIR / name)
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1]
