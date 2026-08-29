# SPDX-License-Identifier: CC-BY-NC-4.0
"""Resolve bundled assets for source, pip, and frozen (PyInstaller) runs."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    """Locate `name` next to the frozen exe, the package, or the repo root."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / name)
    package_dir = Path(__file__).resolve().parent.parent
    candidates.append(package_dir / name)
    candidates.append(package_dir.parent / name)
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0] if candidates else Path(name)
