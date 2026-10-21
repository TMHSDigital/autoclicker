# SPDX-License-Identifier: CC-BY-NC-4.0
"""Header: status-colored brand dot, wordmark, update button, hotkeys and the menu."""

import contextlib
import tkinter as tk
from tkinter import ttk

from ..styles import BG_CHECK, BG_FRAME, BG_LABEL
from ..theme import FONT_TITLE, STATUS_COLORS


def build_header_section(app, parent) -> ttk.Frame:
    """Create the header row (and the first-run hint strip under it)."""
    header = ttk.Frame(parent, style=BG_FRAME, padding=(16, 12, 16, 4))
    header.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
    header.grid_columnconfigure(1, weight=1)
    app.header_frame = header

    app.brand_dot = ttk.Label(
        header, text="●", style=BG_LABEL, foreground=STATUS_COLORS["stopped"], font=FONT_TITLE
    )
    app.brand_dot.grid(row=0, column=0, padx=(0, 8))
    ttk.Label(header, text="Autoclicker", style=BG_LABEL, font=FONT_TITLE).grid(
        row=0, column=1, sticky=tk.W
    )

    actions = ttk.Frame(header, style=BG_FRAME)
    actions.grid(row=0, column=2, sticky=tk.E)
    # Shown only when the opt-in update check finds a newer release.
    app.update_button = ttk.Button(
        actions, text="Update available", style="Toolbutton", command=app.open_release_page
    )
    app.update_button.grid(row=0, column=0, padx=(0, 6))
    app.update_button.grid_remove()
    ttk.Button(
        actions, text="⌨", style="Toolbutton", width=3, command=app.open_hotkeys_dialog
    ).grid(row=0, column=1)

    app.overflow_menu = tk.Menu(header, tearoff=0)
    app.overflow_menu.add_command(label="Import profiles…", command=app.import_profiles)
    app.overflow_menu.add_command(label="Export profiles…", command=app.export_profiles)
    app.overflow_menu.add_command(label="Check for updates now", command=app.check_for_updates_now)
    app.overflow_menu.add_separator()
    app.overflow_menu.add_command(label="Hotkeys…", command=app.open_hotkeys_dialog)
    app.overflow_menu.add_command(label="About", command=app.show_info)
    menu_button = ttk.Button(actions, text="≡", style="Toolbutton", width=3)
    menu_button.configure(command=lambda: _post_menu(app.overflow_menu, menu_button))
    menu_button.grid(row=0, column=2, padx=(2, 0))

    _build_first_run_hint(app, header)
    return header


def _post_menu(menu, button) -> None:
    """Drop the menu under its button."""
    try:
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
    finally:
        with contextlib.suppress(Exception):
            menu.grab_release()


def _build_first_run_hint(app, header) -> None:
    # One-time hint with the ways out of a run (#124); "Got it" hides it for good.
    app.first_run_hint_var = tk.StringVar(value=app._first_run_hint_text())
    app.first_run_hint = ttk.Frame(header, style=BG_FRAME)
    app.first_run_hint.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    app.first_run_hint.grid_columnconfigure(0, weight=1)
    ttk.Label(
        app.first_run_hint,
        textvariable=app.first_run_hint_var,
        style=BG_LABEL,
        wraplength=520,
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
            style=BG_CHECK,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
    if app.settings.get("first_run_hint_dismissed", False):
        app.first_run_hint.grid_remove()
