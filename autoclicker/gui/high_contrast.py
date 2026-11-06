# SPDX-License-Identifier: CC-BY-NC-4.0
"""Windows High Contrast mode (#181).

When the user has turned High Contrast on, the app takes its colors from the
system (``GetSysColor``) instead of its own dark palette, so low-vision users
get the colors they chose.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Any

_log = logging.getLogger(__name__)

SPI_GETHIGHCONTRAST = 0x0042
HCF_HIGHCONTRASTON = 0x00000001

# GetSysColor indexes.
COLOR_WINDOW = 5
COLOR_WINDOWTEXT = 8
COLOR_HIGHLIGHT = 13
COLOR_HIGHLIGHTTEXT = 14
COLOR_BTNFACE = 15
COLOR_GRAYTEXT = 17
COLOR_BTNTEXT = 18
COLOR_HOTLIGHT = 26


class _HighContrast(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint32),
        ("lpszDefaultScheme", ctypes.c_wchar_p),
    ]


def _user32() -> Any:
    windll = getattr(ctypes, "windll", None)
    return windll.user32 if windll is not None and sys.platform == "win32" else None


def is_high_contrast(user32: Any = None) -> bool:
    """True when Windows High Contrast is on. False if it can't be read."""
    user32 = user32 if user32 is not None else _user32()
    if user32 is None:
        return False
    info = _HighContrast()
    info.cbSize = ctypes.sizeof(_HighContrast)
    try:
        if not user32.SystemParametersInfoW(
            SPI_GETHIGHCONTRAST, info.cbSize, ctypes.byref(info), 0
        ):
            return False
    except (AttributeError, OSError):
        return False
    return bool(info.dwFlags & HCF_HIGHCONTRASTON)


def _hex(colorref: int) -> str:
    """A Win32 COLORREF (0x00BBGGRR) as ``#rrggbb``."""
    red, green, blue = colorref & 0xFF, (colorref >> 8) & 0xFF, (colorref >> 16) & 0xFF
    return f"#{red:02x}{green:02x}{blue:02x}"


def system_palette(user32: Any = None) -> dict[str, str] | None:
    """The app palette's keys filled from the system colors, or None when HC is off."""
    user32 = user32 if user32 is not None else _user32()
    if not is_high_contrast(user32):
        return None
    try:

        def color(index: int) -> str:
            return _hex(int(user32.GetSysColor(index)))

        window, text = color(COLOR_WINDOW), color(COLOR_WINDOWTEXT)
        face, face_text = color(COLOR_BTNFACE), color(COLOR_BTNTEXT)
        highlight, highlight_text = color(COLOR_HIGHLIGHT), color(COLOR_HIGHLIGHTTEXT)
        gray, link = color(COLOR_GRAYTEXT), color(COLOR_HOTLIGHT)
    except (AttributeError, OSError, TypeError, ValueError):
        _log.debug("Could not read the system colors", exc_info=True)
        return None
    # Status colors become the system's own text colors too: in High Contrast
    # the dot's meaning comes from the status text next to it.
    return {
        "bg": window,
        "surface": face,
        "text": text,
        "muted": face_text,
        "line": text,
        "accent": highlight,
        "accent_strong": link,
        "accent_soft": face,
        "accent_line": text,
        "on_accent": highlight_text,
        "track": gray,
        "segment": face,
        "error": link,
        "success": highlight,
        "warning": link,
        "idle": gray,
        "shadow": window,
    }
