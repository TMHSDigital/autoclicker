# SPDX-License-Identifier: CC-BY-NC-4.0
"""Compact disclaimer footer with an Info button (version, diagnostics, support)."""

import tkinter as tk
from tkinter import ttk


def build_disclaimer_section(app, parent: ttk.Frame) -> None:
    """Create a one-line disclaimer footer with an info button."""
    footer = ttk.Frame(parent)
    footer.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(4, 0))
    footer.grid_columnconfigure(0, weight=1)

    ttk.Label(
        footer,
        text="For legitimate automation only. Use responsibly.",
        foreground="#8b949e",
    ).grid(row=0, column=0, sticky=tk.W)

    ttk.Button(
        footer,
        text="\u24d8 Info",
        style="Toolbutton",
        command=app.show_info,
    ).grid(row=0, column=1, sticky=tk.E)
