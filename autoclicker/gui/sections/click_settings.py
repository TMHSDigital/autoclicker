# SPDX-License-Identifier: CC-BY-NC-4.0
"""Essential click settings section (mouse button, click type, interval)."""

import tkinter as tk
from tkinter import ttk


def build_click_settings_section(app, parent: ttk.Frame) -> None:
    """Create the essential click settings section."""
    settings_frame = ttk.LabelFrame(parent, text="Click Settings", padding="10")
    settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    settings_frame.grid_columnconfigure(1, weight=1)

    settings = app.controller.settings

    ttk.Label(settings_frame, text="Mouse Button:").grid(row=0, column=0, sticky=tk.W)
    app.button_var = tk.StringVar(value=settings.get("mouse_button", "left"))
    button_frame = ttk.Frame(settings_frame)
    button_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

    ttk.Radiobutton(button_frame, text="Left", variable=app.button_var, value="left").pack(
        side=tk.LEFT, padx=(0, 10)
    )
    ttk.Radiobutton(button_frame, text="Right", variable=app.button_var, value="right").pack(
        side=tk.LEFT, padx=(0, 10)
    )
    ttk.Radiobutton(button_frame, text="Middle", variable=app.button_var, value="middle").pack(
        side=tk.LEFT
    )

    ttk.Label(settings_frame, text="Click Type:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
    app.click_type_var = tk.StringVar(value=settings.get("click_type", "single"))
    click_type_frame = ttk.Frame(settings_frame)
    click_type_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

    ttk.Radiobutton(
        click_type_frame, text="Single", variable=app.click_type_var, value="single"
    ).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(
        click_type_frame, text="Double", variable=app.click_type_var, value="double"
    ).pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Interval:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
    interval_frame = ttk.Frame(settings_frame)
    interval_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

    app.interval_entry = ttk.Entry(interval_frame, width=8)
    app.interval_entry.pack(side=tk.LEFT, padx=(0, 5))
    app.interval_entry.insert(0, str(settings.get("interval", "1000")))

    app.interval_unit_var = tk.StringVar(value=settings.get("interval_unit", "ms"))
    ttk.Combobox(
        interval_frame,
        textvariable=app.interval_unit_var,
        values=["ms", "seconds"],
        width=8,
        state="readonly",
    ).pack(side=tk.LEFT, padx=(0, 10))

    ttk.Label(interval_frame, text="\u00b1").pack(side=tk.LEFT)
    app.variation_entry = ttk.Entry(interval_frame, width=6)
    app.variation_entry.pack(side=tk.LEFT)
    app.variation_entry.insert(0, str(settings.get("variation", "0")))
    ttk.Label(interval_frame, text="ms").pack(side=tk.LEFT)
