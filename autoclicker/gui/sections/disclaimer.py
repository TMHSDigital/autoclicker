# SPDX-License-Identifier: CC-BY-NC-4.0
"""Disclaimer section."""

import tkinter as tk
from tkinter import ttk


def build_disclaimer_section(app, parent: ttk.Frame) -> None:
    """Create disclaimer section."""
    disclaimer_text = (
        "WARNING: USE RESPONSIBLY\n\n"
        "This tool is for legitimate automation purposes only.\n"
        "Ensure compliance with application terms of service,\n"
        "website policies, and local laws. The author assumes\n"
        "no responsibility for misuse."
    )

    disclaimer_label = ttk.Label(
        parent,
        text=disclaimer_text,
        background="#fff3cd",
        foreground="#856404",
        padding="10",
        justify=tk.CENTER,
        relief="solid",
        wraplength=400,
    )
    disclaimer_label.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

    parent.grid_rowconfigure(5, weight=1)
