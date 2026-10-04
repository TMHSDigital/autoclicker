# SPDX-License-Identifier: CC-BY-NC-4.0
"""Safety helpers (failsafe, foreground window)."""

from __future__ import annotations

import os

import pyautogui

try:
    import win32gui
    import win32process
except ImportError:  # pragma: no cover
    win32gui = None  # type: ignore[assignment, unused-ignore]
    win32process = None  # type: ignore[assignment, unused-ignore]

GA_ROOT = 2


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


def is_own_window(hwnd: int) -> bool:
    """True if hwnd belongs to this process.

    Fail-closed: a failed lookup counts as ours, so it is never adopted as the
    target window.
    """
    if win32process is None:
        return True
    try:
        _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return True
    return int(pid) == os.getpid()


def root_window_at(x: int, y: int) -> int | None:
    """Top-level window under a screen point, or None if it cannot be read."""
    if win32gui is None:
        return None
    try:
        child = win32gui.WindowFromPoint((x, y))
        root = win32gui.GetAncestor(child, GA_ROOT) if child else 0
    except Exception:
        return None
    return int(root) or None
