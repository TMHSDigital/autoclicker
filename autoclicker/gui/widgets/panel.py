# SPDX-License-Identifier: CC-BY-NC-4.0
"""Settings panels: a card with an upper-case heading, optionally collapsible."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..styles import MUTED, PANEL, PANEL_HEADER, PANEL_HEADING

_CLOSED = "▸"  # small right-pointing triangle
_OPEN = "▾"  # small down-pointing triangle


class Panel:
    """A card whose ``body`` frame hosts a section's controls."""

    def __init__(self, parent: Any, title: str) -> None:
        self.title = title.upper()
        self.frame = ttk.Frame(parent, style=PANEL, padding=(12, 10, 12, 12))
        self.frame.grid_columnconfigure(0, weight=1)
        self.body = ttk.Frame(self.frame)
        self.body.grid_columnconfigure(1, weight=1)
        self._build_header()
        self.body.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(6, 0))

    def _build_header(self) -> None:
        self.heading = ttk.Label(self.frame, text=self.title, style=PANEL_HEADING)
        self.heading.grid(row=0, column=0, sticky=tk.W)

    def grid(self, **kwargs: Any) -> None:
        self.frame.grid(**kwargs)


class CollapsiblePanel(Panel):
    """A panel whose body is hidden behind its header; a summary line stands in."""

    def __init__(self, parent: Any, title: str, *, expanded: bool = False) -> None:
        self.expanded = expanded
        super().__init__(parent, title)
        self.summary_var = tk.StringVar(value="")
        self.summary = ttk.Label(
            self.frame, textvariable=self.summary_var, style=MUTED, wraplength=240
        )
        self.summary.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
        self._apply()

    def _build_header(self) -> None:
        self.header = ttk.Button(
            self.frame, text=self._header_text(), style=PANEL_HEADER, command=self.toggle
        )
        self.header.grid(row=0, column=0, sticky=(tk.W, tk.E))

    def _header_text(self) -> str:
        return f"{_OPEN if self.expanded else _CLOSED}  {self.title}"

    def toggle(self) -> None:
        self.expanded = not self.expanded
        self._apply()

    def set_summary(self, text: str) -> None:
        self.summary_var.set(text)

    def _apply(self) -> None:
        self.header.configure(text=self._header_text())
        if self.expanded:
            self.summary.grid_remove()
            self.body.grid()
        else:
            self.body.grid_remove()
            self.summary.grid()
