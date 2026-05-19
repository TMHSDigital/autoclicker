# SPDX-License-Identifier: CC-BY-NC-4.0
"""Target coordinates and presets section."""

import tkinter as tk
from tkinter import ttk


def build_coordinate_section(app, parent: ttk.Frame) -> None:
    """Create coordinate input section."""
    coord_frame = ttk.LabelFrame(parent, text="Target Coordinates", padding="10")
    coord_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    coord_frame.grid_columnconfigure(1, weight=1)
    coord_frame.grid_columnconfigure(3, weight=1)
    coord_frame.grid_columnconfigure(6, weight=1)

    ttk.Label(coord_frame, text="X:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
    app.x_entry = ttk.Entry(coord_frame, width=8)
    app.x_entry.grid(row=0, column=1, padx=(0, 15), sticky=(tk.W, tk.E))
    app.x_entry.insert(0, str(app.controller.settings.get("x_coord", "100")))

    ttk.Label(coord_frame, text="Y:").grid(row=0, column=2, padx=(0, 5), sticky=tk.W)
    app.y_entry = ttk.Entry(coord_frame, width=8)
    app.y_entry.grid(row=0, column=3, padx=(0, 15), sticky=(tk.W, tk.E))
    app.y_entry.insert(0, str(app.controller.settings.get("y_coord", "100")))

    app.pick_btn = ttk.Button(
        coord_frame,
        text="Pick Location",
        command=app.start_coordinate_picker,
    )
    app.pick_btn.grid(row=0, column=4, padx=(10, 5), sticky=tk.W)

    ttk.Label(coord_frame, text="Presets:").grid(
        row=1, column=0, padx=(0, 5), pady=(10, 0), sticky=tk.W
    )
    app.preset_var = tk.StringVar()
    app.preset_combo = ttk.Combobox(
        coord_frame,
        textvariable=app.preset_var,
        width=20,
        state="readonly",
    )
    app.preset_combo.grid(
        row=1, column=1, columnspan=3, padx=(0, 10), pady=(10, 0), sticky=(tk.W, tk.E)
    )
    app.update_preset_list()
    app.preset_combo.bind("<<ComboboxSelected>>", app.load_preset)

    app.save_preset_btn = ttk.Button(
        coord_frame,
        text="Save Preset",
        command=app.save_preset,
    )
    app.save_preset_btn.grid(row=1, column=4, pady=(10, 0), sticky=tk.W)
