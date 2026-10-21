# SPDX-License-Identifier: CC-BY-NC-4.0
"""A hero readout: a large numeral over a small upper-case caption."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ..styles import BG_FRAME, STAT, STAT_CAPTION


class StatTile:
    def __init__(self, parent: Any, *, caption: str, variable: Any) -> None:
        self.frame = ttk.Frame(parent, style=BG_FRAME)
        self.value = ttk.Label(self.frame, textvariable=variable, style=STAT)
        self.value.grid(row=0, column=0, sticky=tk.W)
        self.caption = ttk.Label(self.frame, text=caption.upper(), style=STAT_CAPTION)
        self.caption.grid(row=1, column=0, sticky=tk.W)

    def grid(self, **kwargs: Any) -> None:
        self.frame.grid(**kwargs)
