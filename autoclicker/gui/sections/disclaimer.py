# SPDX-License-Identifier: CC-BY-NC-4.0
"""Compact disclaimer footer with an info dialog."""

import tkinter as tk
from tkinter import messagebox, ttk

_FULL_WARNING = (
    "USE RESPONSIBLY\n\n"
    "This tool is for legitimate automation purposes only.\n\n"
    "Ensure compliance with application terms of service, website "
    "policies, and local laws. The author assumes no responsibility "
    "for misuse."
)


def build_disclaimer_section(app, parent: ttk.Frame) -> None:
    """Create a one-line disclaimer footer with an info button."""
    footer = ttk.Frame(parent)
    footer.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(4, 0))
    footer.grid_columnconfigure(0, weight=1)

    ttk.Label(
        footer,
        text="For legitimate automation only \u2014 use responsibly.",
        foreground="#8b949e",
    ).grid(row=0, column=0, sticky=tk.W)

    ttk.Button(
        footer,
        text="\u24d8 Info",
        style="Toolbutton",
        command=lambda: messagebox.showwarning("Use Responsibly", _FULL_WARNING),
    ).grid(row=0, column=1, sticky=tk.E)
