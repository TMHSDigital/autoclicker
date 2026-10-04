# SPDX-License-Identifier: CC-BY-NC-4.0
"""Location of the per-user data folder (settings, logs)."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "WindowsAutoclicker"


def app_data_dir() -> Path:
    """``%APPDATA%\\WindowsAutoclicker``, falling back to the roaming profile path.

    Never relative to the working directory, even when APPDATA is unset.
    """
    appdata = os.environ.get("APPDATA", "").strip()
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / APP_DIR_NAME
