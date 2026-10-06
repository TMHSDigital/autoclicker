# SPDX-License-Identifier: CC-BY-NC-4.0
"""Location of the per-user data folder (settings, logs, captured images)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "WindowsAutoclicker"
# An empty file with this name next to WindowsAutoclicker.exe turns on portable
# mode: everything is kept in a "data" folder beside the exe instead (#122).
PORTABLE_MARKER = "portable.txt"
PORTABLE_DATA_DIR = "data"


def app_dir() -> Path:
    """Folder the app runs from: the exe's folder, or the source checkout."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def portable_data_dir() -> Path | None:
    """The portable data folder when the exe has a portable.txt beside it, else None.

    Only the frozen exe can be portable, so a marker in a source checkout never
    redirects a developer's (or the test suite's) settings.
    """
    if not getattr(sys, "frozen", False):
        return None
    folder = app_dir()
    if (folder / PORTABLE_MARKER).is_file():
        return folder / PORTABLE_DATA_DIR
    return None


def app_data_dir() -> Path:
    """Where settings, logs and images live.

    ``%APPDATA%\\WindowsAutoclicker`` (falling back to the roaming profile path),
    or the portable data folder. Never relative to the working directory, even
    when APPDATA is unset.
    """
    portable = portable_data_dir()
    if portable is not None:
        return portable
    appdata = os.environ.get("APPDATA", "").strip()
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / APP_DIR_NAME
