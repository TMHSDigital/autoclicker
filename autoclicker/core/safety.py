# SPDX-License-Identifier: CC-BY-NC-4.0
"""Safety helpers (failsafe, foreground window)."""

from __future__ import annotations

import pyautogui

try:
    import win32gui
except ImportError:  # pragma: no cover
    win32gui = None  # type: ignore[assignment, unused-ignore]


def apply_failsafe(enabled: bool) -> None:
    """Configure pyautogui failsafe (corner abort). Default should be enabled."""
    pyautogui.FAILSAFE = enabled


def get_foreground_window_handle() -> int | None:
    """Return Win32 foreground HWND or None if unavailable."""
    if win32gui is None:
        return None
    try:
        return int(win32gui.GetForegroundWindow())
    except Exception:
        return None


def is_foreground_window(hwnd: int | None) -> bool:
    """True if hwnd is still the foreground window.

    Fail-closed: missing hwnd or a failed lookup is treated as unfocused.
    """
    if hwnd is None:
        return False
    current = get_foreground_window_handle()
    if current is None:
        return False
    return current == hwnd
