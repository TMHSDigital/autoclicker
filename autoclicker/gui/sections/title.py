# SPDX-License-Identifier: CC-BY-NC-4.0
"""Title section."""

import tkinter as tk
from tkinter import ttk


def build_title_section(app, parent: ttk.Frame) -> None:
    """Create title section."""
    title_label = ttk.Label(
        parent,
        text="Windows Autoclicker",
        font=("Arial", 16, "bold"),
    )
    title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))
