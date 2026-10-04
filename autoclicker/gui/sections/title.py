# SPDX-License-Identifier: CC-BY-NC-4.0
"""Title row with app icon and theme toggle."""

import tkinter as tk
from tkinter import ttk

from ...core.resources import resource_path


def build_title_section(app, parent: ttk.Frame) -> None:
    """Create the title row."""
    header = ttk.Frame(parent)
    header.grid(row=0, column=0, columnspan=2, pady=(0, 16), sticky=(tk.W, tk.E))
    header.grid_columnconfigure(1, weight=1)

    icon_path = resource_path("autoclicker.png")
    if icon_path.is_file():
        try:
            from PIL import Image, ImageTk

            image = Image.open(icon_path).resize((28, 28), Image.Resampling.LANCZOS)
            app._title_icon = ImageTk.PhotoImage(image)
            ttk.Label(header, image=app._title_icon).grid(row=0, column=0, padx=(0, 10))
        except Exception:
            pass

    ttk.Label(
        header,
        text="Windows Autoclicker",
        font=("Segoe UI", 16, "bold"),
    ).grid(row=0, column=1, sticky=tk.W)

    app.theme_button = ttk.Button(
        header,
        text=_theme_label(app),
        style="Toolbutton",
        width=10,
        command=app.toggle_theme,
    )
    app.theme_button.grid(row=0, column=3, sticky=tk.E)

    # Shown only when the opt-in update check finds a newer release.
    app.update_button = ttk.Button(
        header,
        text="Update available",
        style="Toolbutton",
        command=app.open_release_page,
    )
    app.update_button.grid(row=0, column=2, sticky=tk.E, padx=(0, 6))
    app.update_button.grid_remove()


def _theme_label(app) -> str:
    return "\u2600 Light" if app.theme_var.get() == "dark" else "\u263d Dark"
