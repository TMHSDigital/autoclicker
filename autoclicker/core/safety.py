# SPDX-License-Identifier: CC-BY-NC-4.0
"""Safety helpers (failsafe, foreground window)."""

from __future__ import annotations

import pyautogui


def apply_failsafe(enabled: bool) -> None:
    """Configure pyautogui failsafe (corner abort). Default should be enabled."""
    pyautogui.FAILSAFE = enabled


def get_foreground_window_handle() -> int | None:
    """Return Win32 foreground HWND or None if unavailable."""
    try:
        import win32gui

        return int(win32gui.GetForegroundWindow())
    except Exception:
        return None


def is_foreground_window(hwnd: int | None) -> bool:
    """True if hwnd is still foreground, or check skipped when hwnd is None."""
    if hwnd is None:
        return True
    current = get_foreground_window_handle()
    return current is None or current == hwnd
