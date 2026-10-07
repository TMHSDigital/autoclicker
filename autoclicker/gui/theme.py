# SPDX-License-Identifier: CC-BY-NC-4.0
"""Docs Blue: the app's light and dark palettes, shared with the website.

Colors come from docs/site.css so the app and the site read as one product.
ttk widgets get them through ttk.Style; the custom-drawn widgets register a
listener and redraw themselves when the theme changes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from tkinter import ttk
from typing import Any

import sv_ttk

from .styles import ERROR, MUTED

_log = logging.getLogger(__name__)

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f6f8fb",
        "surface": "#ffffff",
        "text": "#1b2330",
        "muted": "#5b6676",
        "line": "#e1e6ee",
        "accent": "#0067d6",
        "accent_strong": "#0050a8",
        "accent_soft": "#e6f0fc",
        "accent_line": "#c4dbf7",
        "hero_a": "#1a73e0",
        "hero_b": "#0058c9",
        "on_accent": "#ffffff",
        "track": "#e1e6ee",
        "segment": "#e9edf3",
        "error": "#cf222e",
        "success": "#1a7f37",
        "warning": "#9a6700",
        "idle": "#8b949e",
        "shadow": "#d5dbe4",
    },
    "dark": {
        "bg": "#0f141b",
        "surface": "#171e27",
        "text": "#e6ebf2",
        "muted": "#9aa6b6",
        "line": "#26303c",
        "accent": "#4aa3ff",
        "accent_strong": "#7bbcff",
        "accent_soft": "#152a42",
        "accent_line": "#24507f",
        "hero_a": "#5aaeff",
        "hero_b": "#2f88ea",
        "on_accent": "#08111c",
        "track": "#26303c",
        "segment": "#1d2530",
        "error": "#ff7b72",
        "success": "#3fb950",
        "warning": "#d29922",
        "idle": "#6e7681",
        "shadow": "#0a0d12",
    },
}

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_LABEL = ("Segoe UI Semibold", 8)
FONT_TITLE = ("Segoe UI Semibold", 11)
FONT_SENTENCE = ("Segoe UI", 15)
FONT_PILL = ("Segoe UI Semibold", 14)
FONT_BUTTON = ("Segoe UI Semibold", 12)
FONT_COUNT = ("Segoe UI Semibold", 24)

_listeners: list[Callable[[dict[str, str]], None]] = []
_current: dict[str, str] = PALETTES["light"]


def palette(mode: str) -> dict[str, str]:
    """The palette for ``mode`` ("light" or "dark"); anything else is light."""
    return PALETTES.get(mode, PALETTES["light"])


def current() -> dict[str, str]:
    """The palette applied last."""
    return _current


def register(listener: Callable[[dict[str, str]], None]) -> None:
    """Call ``listener(palette)`` after every theme change."""
    _listeners.append(listener)


def unregister(listener: Callable[[dict[str, str]], None]) -> None:
    if listener in _listeners:
        _listeners.remove(listener)


def apply_theme(root: Any, mode: str, *, style: Any = None) -> dict[str, str]:
    """Switch sv_ttk and our ttk styles to ``mode``, then tell the custom widgets."""
    global _current
    colors = palette(mode)
    _current = colors
    try:
        sv_ttk.set_theme("dark" if colors is PALETTES["dark"] else "light")
    except Exception:  # cosmetic; never block startup or a theme switch
        _log.debug("Could not set the sv_ttk theme", exc_info=True)
    try:
        style = style if style is not None else ttk.Style(root)
        _configure_styles(style, colors)
        root.configure(background=colors["bg"])
    except Exception:
        _log.debug("Could not apply ttk styles", exc_info=True)
    for listener in list(_listeners):
        try:
            listener(colors)
        except Exception:  # a destroyed widget must not stop the others
            _log.debug("Theme listener failed", exc_info=True)
    return colors


def _configure_styles(style: Any, c: dict[str, str]) -> None:
    style.configure(MUTED, foreground=c["muted"])
    style.configure(ERROR, foreground=c["error"])
    for name in ("TFrame", "TLabelframe", "Card.TFrame"):
        style.configure(name, background=c["bg"])
    for name in ("TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe.Label"):
        style.configure(name, background=c["bg"], foreground=c["text"])
    style.configure(MUTED, background=c["bg"])
    style.configure(ERROR, background=c["bg"])
    style.configure("Heading.TLabel", background=c["bg"], foreground=c["muted"], font=FONT_LABEL)
    style.configure("Link.TButton", foreground=c["accent"])
    style.configure("Danger.TButton", foreground=c["error"])
