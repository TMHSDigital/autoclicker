# SPDX-License-Identifier: CC-BY-NC-4.0
"""Reusable collapsible disclosure frame for ttk."""

import tkinter as tk
from tkinter import ttk


class CollapsibleFrame(ttk.Frame):
    """A labeled section whose body can be expanded or collapsed.

    The body is exposed as ``self.body``; place child widgets in it.
    """

    def __init__(self, parent: ttk.Frame, text: str = "", expanded: bool = False) -> None:
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)

        self._expanded = tk.BooleanVar(value=expanded)
        self._text = text

        self._header = ttk.Button(
            self,
            style="Toolbutton",
            command=self.toggle,
        )
        self._header.grid(row=0, column=0, sticky=(tk.W, tk.E))

        self.body = ttk.Frame(self, padding=(0, 8, 0, 0))
        self.body.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.body.grid_columnconfigure(0, weight=1)

        self._render_header()
        if not expanded:
            self.body.grid_remove()

    def _render_header(self) -> None:
        arrow = "\u25be" if self._expanded.get() else "\u25b8"  # ▾ / ▸
        self._header.configure(text=f"{arrow}  {self._text}")

    def toggle(self) -> None:
        if self._expanded.get():
            self.body.grid_remove()
            self._expanded.set(False)
        else:
            self.body.grid()
            self._expanded.set(True)
        self._render_header()
