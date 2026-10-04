# SPDX-License-Identifier: CC-BY-NC-4.0
"""Desktop geometry: the virtual screen spanning every monitor."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass

# GetSystemMetrics indices for the virtual screen (the bounding box of all monitors).
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


@dataclass(frozen=True)
class ScreenBounds:
    """Half-open rectangle [left, left + width) x [top, top + height) in screen pixels.

    On multi-monitor setups ``left``/``top`` are negative when a monitor sits to
    the left of or above the primary one.
    """

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def describe(self) -> str:
        """Human-readable valid range, e.g. 'X -1920 to 1919, Y 0 to 1079'."""
        return f"X {self.left} to {self.right - 1}, Y {self.top} to {self.bottom - 1}"


def _query_virtual_screen() -> ScreenBounds | None:
    """Ask Win32 for the virtual screen; None if unavailable (non-Windows, failure)."""
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    try:
        metrics = windll.user32.GetSystemMetrics
        bounds = ScreenBounds(
            int(metrics(SM_XVIRTUALSCREEN)),
            int(metrics(SM_YVIRTUALSCREEN)),
            int(metrics(SM_CXVIRTUALSCREEN)),
            int(metrics(SM_CYVIRTUALSCREEN)),
        )
    except Exception:
        return None
    if bounds.width <= 0 or bounds.height <= 0:
        return None
    return bounds


def virtual_screen_bounds(primary_size: Callable[[], tuple[int, int]]) -> ScreenBounds:
    """Bounds of the whole desktop across all monitors.

    ``primary_size`` (normally ``pyautogui.size``) is the fallback when the
    virtual screen cannot be read; it covers the primary monitor only.
    """
    bounds = _query_virtual_screen()
    if bounds is not None:
        return bounds
    width, height = primary_size()
    return ScreenBounds(0, 0, int(width), int(height))
