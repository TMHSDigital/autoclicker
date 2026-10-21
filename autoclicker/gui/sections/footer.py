# SPDX-License-Identifier: CC-BY-NC-4.0
"""Footer: app toggles (tray, updates), the disclaimer and the Info button."""

import tkinter as tk
from tkinter import ttk

from ..styles import BG_CHECK, BG_FRAME, BG_MUTED


def build_footer_section(app, parent) -> ttk.Frame:
    """Create the footer row."""
    footer = ttk.Frame(parent, style=BG_FRAME, padding=(16, 6, 16, 10))
    footer.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
    footer.grid_columnconfigure(2, weight=1)
    app.footer_frame = footer
    settings = app.controller.settings

    app.minimize_to_tray_var = tk.BooleanVar(value=bool(settings.get("minimize_to_tray", True)))
    ttk.Checkbutton(
        footer,
        text="Minimize to tray",
        variable=app.minimize_to_tray_var,
        command=app._on_minimize_to_tray_toggle,
        style=BG_CHECK,
    ).grid(row=0, column=0, sticky=tk.W)
    app.check_updates_var = tk.BooleanVar(value=settings.get("check_for_updates") is True)
    ttk.Checkbutton(
        footer,
        text="Daily update check",
        variable=app.check_updates_var,
        command=app._on_check_updates_toggle,
        style=BG_CHECK,
    ).grid(row=0, column=1, sticky=tk.W, padx=(14, 0))

    ttk.Label(
        footer,
        text="For legitimate automation only. Use responsibly.",
        style=BG_MUTED,
    ).grid(row=0, column=2, sticky=tk.E, padx=(14, 8))
    ttk.Button(footer, text="ⓘ Info", style="Toolbutton", command=app.show_info).grid(
        row=0, column=3, sticky=tk.E
    )
    return footer
