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

    # One-time hint with the ways out of a run (#124); "Got it" hides it for good.
    app.first_run_hint_var = tk.StringVar(value=app._first_run_hint_text())
    app.first_run_hint = ttk.Frame(header)
    app.first_run_hint.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 0))
    app.first_run_hint.grid_columnconfigure(0, weight=1)
    ttk.Label(
        app.first_run_hint,
        textvariable=app.first_run_hint_var,
        wraplength=420,
        justify=tk.LEFT,
    ).grid(row=0, column=0, sticky=tk.W)
    ttk.Button(
        app.first_run_hint,
        text="Got it",
        style="Toolbutton",
        command=app.dismiss_first_run_hint,
    ).grid(row=0, column=1, sticky=tk.NE, padx=(8, 0))
    # The update opt-in rides along on first run instead of a second, modal prompt.
    app.hint_updates_var = tk.BooleanVar(value=False)
    if app.settings.get("check_for_updates") is None:
        ttk.Checkbutton(
            app.first_run_hint,
            text="Also check GitHub once a day for new versions (nothing is sent or downloaded)",
            variable=app.hint_updates_var,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
    if app.settings.get("first_run_hint_dismissed", False):
        app.first_run_hint.grid_remove()


def _theme_label(app) -> str:
    return "\u2600 Light" if app.theme_var.get() == "dark" else "\u263d Dark"
