# SPDX-License-Identifier: CC-BY-NC-4.0
"""The app's single dark palette, fonts and ttk styles.

Colors come from the dark palette of docs/site.css so the app and the site read
as one product; ``surface`` is sv_ttk's own window gray, which its card and input
images are drawn for. ttk widgets get them through ttk.Style; custom-drawn widgets
read PALETTE directly and may register a listener for re-application.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from tkinter import ttk
from typing import Any

import sv_ttk

from .high_contrast import system_palette
from .styles import (
    BG_CHECK,
    BG_FRAME,
    BG_LABEL,
    BG_MUTED,
    DANGER,
    ERROR,
    MUTED,
    PANEL,
    PANEL_HEADER,
    PANEL_HEADING,
    SEGMENT,
    STAT,
    STAT_CAPTION,
)

_log = logging.getLogger(__name__)

PALETTE: dict[str, str] = {
    "bg": "#0f141b",
    "surface": "#1c1c1c",
    "text": "#e6ebf2",
    "muted": "#9aa6b6",
    "line": "#26303c",
    "accent": "#4aa3ff",
    "accent_strong": "#7bbcff",
    "accent_soft": "#152a42",
    "accent_line": "#24507f",
    "on_accent": "#08111c",
    "track": "#26303c",
    "segment": "#1d2530",
    "error": "#ff7b72",
    "success": "#3fb950",
    "warning": "#d29922",
    "idle": "#6e7681",
    "shadow": "#0a0d12",
}

# Status-dot colors by state (see AutoclickerApp._set_status_message).
STATUS_COLORS: dict[str, str] = {
    "running": PALETTE["success"],
    "stopped": PALETTE["idle"],
    "alert": PALETTE["warning"],
    "error": PALETTE["error"],
}

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_LABEL = ("Segoe UI Semibold", 8)
FONT_TITLE = ("Segoe UI Semibold", 12)
FONT_STAT = ("Consolas", 22)
FONT_STAT_CAPTION = ("Segoe UI Semibold", 8)
FONT_RUN = ("Segoe UI Semibold", 15)
FONT_RUN_CAPTION = ("Segoe UI", 9)

_listeners: list[Callable[[dict[str, str]], None]] = []
_current: dict[str, str] = PALETTE


def current() -> dict[str, str]:
    """The palette applied last (always PALETTE; kept for custom widgets)."""
    return _current


def register(listener: Callable[[dict[str, str]], None]) -> None:
    """Call ``listener(palette)`` after every apply_theme."""
    _listeners.append(listener)


def unregister(listener: Callable[[dict[str, str]], None]) -> None:
    if listener in _listeners:
        _listeners.remove(listener)


def apply_theme(root: Any, *, style: Any = None) -> dict[str, str]:
    """Put sv_ttk in dark mode, configure our styles, then tell the custom widgets.

    With Windows High Contrast on, the system colors replace the palette (in
    place, so every widget that reads PALETTE follows) and sv_ttk is skipped:
    its themed images would keep the dark look (#181).
    """
    global _current
    system = system_palette()
    if system is not None:
        PALETTE.update(system)
        STATUS_COLORS.update(
            running=PALETTE["success"],
            stopped=PALETTE["idle"],
            alert=PALETTE["warning"],
            error=PALETTE["error"],
        )
    colors = PALETTE
    _current = colors
    try:
        if system is None:
            sv_ttk.set_theme("dark")
    except Exception:  # cosmetic; never block startup
        _log.debug("Could not set the sv_ttk theme", exc_info=True)
    try:
        style = style if style is not None else ttk.Style(root)
        if system is not None:
            style.theme_use("clam")  # plain shapes that take any colors
            _configure_clam(style, colors)
        else:
            _flat_disabled_segments(style)
        _configure_styles(style, colors)
        root.configure(background=colors["bg"])
        # sv_ttk's tk_setPalette writes *background and *foreground into the option
        # database, and a ttk label's own option beats its style. Blank them for
        # labels so Bg.*, Stat.* and the dimming styles show; classic widgets
        # (Listbox, Menu) keep the dark palette. The same goes for *Font, which
        # the app sets as the default and which would hide the Stat fonts.
        # tk_setPalette runs from a <<ThemeChanged>> binding, so let it run
        # first: the option database lets the newest of equal entries win, and
        # blanks added before it were overridden (labels drew the panel color
        # on the page and the stats lost their font).
        root.update_idletasks()
        for option in ("background", "foreground", "font"):
            root.option_add(f"*TLabel.{option}", "")
    except Exception:
        _log.debug("Could not apply ttk styles", exc_info=True)
    for listener in list(_listeners):
        try:
            listener(colors)
        except Exception:  # a destroyed widget must not stop the others
            _log.debug("Theme listener failed", exc_info=True)
    return colors


def set_dimmed(dimmed: bool, *, style: Any = None) -> None:
    """Fade the panel text while the settings are locked during a run."""
    c = PALETTE
    text = c["muted"] if dimmed else c["text"]
    heading = c["idle"] if dimmed else c["muted"]
    try:
        style = style if style is not None else ttk.Style()
        for name in ("TLabel", "TCheckbutton", "TRadiobutton"):
            style.configure(name, foreground=text)
        style.configure(PANEL_HEADING, foreground=heading)
    except Exception:
        _log.debug("Could not dim the panels", exc_info=True)


def _configure_styles(style: Any, c: dict[str, str]) -> None:
    surface, bg = c["surface"], c["bg"]
    # Panels are the majority of widgets, so the base styles sit on `surface`
    # and the section builders need no style names at all.
    for name in ("TFrame", "TLabelframe", PANEL):
        style.configure(name, background=surface)
    for name in ("TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe.Label"):
        style.configure(name, background=surface, foreground=c["text"])
    style.configure(MUTED, background=surface, foreground=c["muted"])
    style.configure(ERROR, background=surface, foreground=c["error"])
    # Window chrome on the darker page background.
    style.configure(BG_FRAME, background=bg)
    style.configure(BG_LABEL, background=bg, foreground=c["text"])
    style.configure(BG_MUTED, background=bg, foreground=c["muted"])
    style.configure(BG_CHECK, background=bg, foreground=c["text"])
    style.configure(PANEL_HEADING, background=surface, foreground=c["muted"], font=FONT_LABEL)
    style.configure(PANEL_HEADER, font=FONT_BOLD, foreground=c["text"], anchor="w")
    style.configure(SEGMENT, font=FONT, padding=(10, 4))
    style.map(
        SEGMENT,
        background=[("selected", c["accent_soft"])],
        foreground=[("disabled", c["idle"]), ("selected", c["accent_strong"])],
    )
    style.configure(STAT, background=bg, foreground=c["text"], font=FONT_STAT)
    style.configure(STAT_CAPTION, background=bg, foreground=c["muted"], font=FONT_STAT_CAPTION)
    style.configure(DANGER, foreground=c["error"], background=bg)


_SV_IMAGES = "ttk::theme::sv_dark::I"


def _flat_disabled_segments(style: Any) -> None:
    """Draw a disabled segment flat, like an unselected one, only dimmed.

    sv_ttk gives every disabled Toolbutton a filled box, so the actions a mode
    does not allow (Hold and Key in Sequence mode) looked more like buttons than
    the ones that work. Segments get their own button element without it.
    """
    try:
        image = {
            name: style.tk.eval(f"set {_SV_IMAGES}({name})")
            for name in ("empty", "button-pressed", "button-hover", "button-focus-hover")
        }
        if "Segment.button" not in style.element_names():
            style.element_create(
                "Segment.button",
                "image",
                image["empty"],
                ("disabled", image["empty"]),
                ("pressed", image["button-pressed"]),
                ("active focus", image["button-focus-hover"]),
                ("active", image["button-hover"]),
                border=4,
                sticky="nsew",
            )
        style.layout(
            SEGMENT,
            [
                (
                    "Segment.button",
                    {
                        "sticky": "nsew",
                        "children": [
                            (
                                "Toolbutton.padding",
                                {
                                    "sticky": "nsew",
                                    "children": [
                                        ("Toolbutton.label", {"side": "left", "expand": 1})
                                    ],
                                },
                            )
                        ],
                    },
                )
            ],
        )
    except Exception:  # sv_ttk missing or changed: keep its look
        _log.debug("Could not restyle the segments", exc_info=True)


def _configure_clam(style: Any, c: dict[str, str]) -> None:
    """Give clam's controls the High Contrast colors (#181).

    clam's own defaults are light gray, which ignores the user's scheme and
    left white panel headers unreadable on a gray bar.
    """
    surface, text, line = c["surface"], c["text"], c["line"]
    edges = {"bordercolor": line, "lightcolor": surface, "darkcolor": surface}
    for name in ("TButton", "Toolbutton", "TCheckbutton", "TRadiobutton"):
        style.configure(name, background=surface, foreground=text, **edges)
        style.map(
            name,
            background=[("active", c["accent"]), ("pressed", c["accent"])],
            foreground=[
                ("disabled", c["idle"]),
                ("active", c["on_accent"]),
                ("pressed", c["on_accent"]),
            ],
        )
    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(name, indicatorbackground=c["bg"], indicatorforeground=text)
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            name,
            fieldbackground=c["bg"],
            foreground=text,
            insertcolor=text,
            arrowcolor=text,
            background=surface,
            selectbackground=c["accent"],
            selectforeground=c["on_accent"],
            **edges,
        )
        style.map(
            name,
            fieldbackground=[("readonly", c["bg"]), ("disabled", c["bg"])],
            foreground=[("disabled", c["idle"])],
        )
    style.configure("TScrollbar", background=surface, troughcolor=c["bg"], arrowcolor=text, **edges)
