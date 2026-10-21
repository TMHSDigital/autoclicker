# SPDX-License-Identifier: CC-BY-NC-4.0
"""The hero Start/Stop button: a rounded block whose color says what a click does.

Built by composition over a tk.Canvas so tests can replace tkinter.Canvas.
The shape is a Pillow image; the title and caption are canvas text items so
they keep ClearType.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from PIL import ImageTk

from .. import theme
from .render import px, rounded_rect, ui_scale

# Palette key of the fill for each mode.
MODE_FILL = {"idle": "accent", "countdown": "warning", "running": "error"}
_TITLES = {"idle": "▶  START", "running": "■  STOP"}


class RunButton:
    """Idle: START + start hotkey. Countdown: STARTING IN n. Running: STOP."""

    def __init__(
        self,
        parent: Any,
        *,
        command: Callable[[], None],
        width: int = 150,
        height: int = 108,
        radius: int = 18,
    ) -> None:
        self._command = command
        self._mode = "idle"
        self._detail = ""
        self._hotkeys = ("", "")
        self._hover = False
        self._photo: Any = None
        self.canvas = tk.Canvas(
            parent,
            highlightthickness=0,
            borderwidth=0,
            background=theme.PALETTE["bg"],
            cursor="hand2",
            takefocus=1,
        )
        scale = ui_scale(self.canvas)
        self._size = (px(width, scale), px(height, scale), px(radius, scale))
        self.canvas.configure(width=self._size[0], height=self._size[1])
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Return>", self._on_click)
        self.canvas.bind("<space>", self._on_click)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self._render()

    # Public API

    def set_mode(self, mode: str, *, detail: str = "") -> None:
        """``idle``, ``countdown`` (detail: seconds or a wait text) or ``running``."""
        if mode not in MODE_FILL:
            mode = "idle"
        if (mode, detail) == (self._mode, self._detail):
            return
        self._mode, self._detail = mode, detail
        self._render()

    def set_hotkey(self, start: str, stop: str = "") -> None:
        """Captions: the start key while idle, the stop key while running."""
        self._hotkeys = (start, stop)
        self._render()

    def grid(self, **kwargs: Any) -> None:
        self.canvas.grid(**kwargs)

    def grid_remove(self) -> None:
        self.canvas.grid_remove()

    def winfo_class(self) -> str:
        return "RunButton"

    # Drawing

    def _texts(self) -> tuple[str, str]:
        if self._mode == "countdown":
            if self._detail.isdigit():
                return f"STARTING IN {self._detail}", "click to cancel"
            return "STARTING", self._detail or "click to cancel"
        if self._mode == "running":
            return _TITLES["running"], self._hotkeys[1] or "click to stop"
        return _TITLES["idle"], self._hotkeys[0]

    def _fill(self) -> str:
        if self._mode == "idle" and self._hover:
            return theme.PALETTE["accent_strong"]
        return theme.PALETTE[MODE_FILL[self._mode]]

    def _render(self) -> None:
        width, height, radius = self._size
        image = rounded_rect(width, height, radius, self._fill())
        self._photo = ImageTk.PhotoImage(image)
        title, caption = self._texts()
        color = theme.PALETTE["on_accent"]
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        offset = px(9, height / 108) if caption else 0
        self.canvas.create_text(
            width // 2,
            height // 2 - offset,
            text=title,
            fill=color,
            font=theme.FONT_RUN,
        )
        if caption:
            self.canvas.create_text(
                width // 2,
                height // 2 + px(16, height / 108),
                text=caption,
                fill=color,
                font=theme.FONT_RUN_CAPTION,
            )

    # Events

    def _on_click(self, _event: Any = None) -> None:
        self._command()

    def _on_enter(self, _event: Any = None) -> None:
        self._hover = True
        self._render()

    def _on_leave(self, _event: Any = None) -> None:
        self._hover = False
        self._render()
