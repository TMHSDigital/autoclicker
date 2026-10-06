# SPDX-License-Identifier: CC-BY-NC-4.0
"""Diagnostics text for bug reports (Info > Copy diagnostics).

Everything is read locally and shown to the user before it is copied; nothing
is sent anywhere. Profile names, sequence points, the watched pixel and the
captured image are left out of the settings dump, and the home folder (which
contains the account name) is replaced everywhere.
"""

from __future__ import annotations

import ctypes
import json
import platform
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import __version__
from .app_data import app_data_dir, portable_data_dir
from .screen import ScreenBounds, monitor_rects

LOG_TAIL_LINES = 50
SESSION_TAIL_LINES = 10

# Settings replaced by a summary in the report.
_REDACTED = (
    "presets",
    "sequence",
    "condition_x",
    "condition_y",
    "condition_color",
    "image_path",
    "image_region",
)

_DPI_MODES = {0: "unaware", 1: "system", 2: "per-monitor"}


def redact_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Settings with personal or layout-specific details summarized."""
    result = {k: v for k, v in settings.items() if k not in _REDACTED}
    presets = settings.get("presets")
    if isinstance(presets, dict):
        result["presets"] = f"<{len(presets)} profiles>"
    sequence = settings.get("sequence")
    if isinstance(sequence, list):
        result["sequence"] = f"<{len(sequence)} steps>"
    if any(k in settings for k in ("condition_x", "condition_y", "condition_color")):
        result["condition_pixel"] = "<redacted>"
    if settings.get("image_path"):
        result["image_path"] = "<captured image>"
    region = settings.get("image_region")
    if isinstance(region, list) and len(region) == 4:
        result["image_region"] = f"<{region[2]}x{region[3]} area>"
    return result


def hide_user_folder(text: str) -> str:
    """Replace the home folder, which contains the Windows account name (#99)."""
    home = str(Path.home())
    if len(home) <= 3:  # no real home folder, such as "C:\"
        return text
    return re.sub(re.escape(home), lambda _m: "%USERPROFILE%", text, flags=re.IGNORECASE)


def _tail(path: Path, lines: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(not found)"
    return "\n".join(text.splitlines()[-lines:]) or "(empty)"


def _dpi_mode() -> str:
    try:
        user32 = ctypes.WinDLL("user32")  # type: ignore[attr-defined, unused-ignore]
        user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        awareness = user32.GetAwarenessFromDpiAwarenessContext(
            user32.GetThreadDpiAwarenessContext()
        )
    except Exception:
        return "unknown"
    return _DPI_MODES.get(int(awareness), f"unknown ({awareness})")


def _tk_version() -> str:
    try:
        import tkinter

        return str(tkinter.TkVersion)
    except Exception:
        return "unknown"


def build_report(
    settings: dict[str, Any],
    *,
    monitors: Callable[[], list[ScreenBounds]] = monitor_rects,
    data_dir: Path | None = None,
) -> str:
    """The full diagnostics text."""
    folder = data_dir or app_data_dir()
    run_method = "exe" if getattr(sys, "frozen", False) else "source"
    if portable_data_dir() is not None:
        run_method += ", portable"
    screens = monitors() or []
    lines = [
        "### Windows Autoclicker diagnostics",
        f"App version: {__version__} ({run_method})",
        f"Windows: {platform.platform()}",
        f"Python: {platform.python_version()}  Tk: {_tk_version()}",
        f"DPI awareness: {_dpi_mode()}",
        f"Monitors ({len(screens)}): "
        + ("; ".join(f"{m.width}x{m.height} at ({m.left}, {m.top})" for m in screens) or "unknown"),
        "",
        "Settings:",
        "```json",
        json.dumps(redact_settings(settings), indent=2, sort_keys=True, default=str),
        "```",
        "",
        f"Last {LOG_TAIL_LINES} lines of autoclicker.log:",
        "```",
        _tail(folder / "autoclicker.log", LOG_TAIL_LINES),
        "```",
        "",
        f"Last {SESSION_TAIL_LINES} lines of sessions.log:",
        "```",
        _tail(folder / "sessions.log", SESSION_TAIL_LINES),
        "```",
    ]
    return hide_user_folder("\n".join(lines))
