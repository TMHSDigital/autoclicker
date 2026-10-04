# SPDX-License-Identifier: CC-BY-NC-4.0
"""Target coordinates and presets section."""

import tkinter as tk
from tkinter import ttk


def build_coordinate_section(app, parent: ttk.Frame) -> None:
    """Create coordinate input section."""
    coord_frame = ttk.LabelFrame(parent, text="Target", padding="10")
    coord_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    coord_frame.grid_columnconfigure(1, weight=1)
    coord_frame.grid_columnconfigure(3, weight=1)
    coord_frame.grid_columnconfigure(6, weight=1)

    settings = app.controller.settings
    mode = settings.get("target_mode", "fixed")
    app.target_mode_var = tk.StringVar(value=mode if mode in ("fixed", "cursor") else "fixed")
    mode_frame = ttk.Frame(coord_frame)
    mode_frame.grid(row=0, column=0, columnspan=6, sticky=tk.W, pady=(0, 10))
    ttk.Radiobutton(
        mode_frame,
        text="Fixed location",
        variable=app.target_mode_var,
        value="fixed",
        command=app._on_target_mode_change,
    ).pack(side=tk.LEFT, padx=(0, 15))
    ttk.Radiobutton(
        mode_frame,
        text="Current cursor position",
        variable=app.target_mode_var,
        value="cursor",
        command=app._on_target_mode_change,
    ).pack(side=tk.LEFT)

    ttk.Label(coord_frame, text="X:").grid(row=1, column=0, padx=(0, 5), sticky=tk.W)
    app.x_entry = ttk.Entry(coord_frame, width=8)
    app.x_entry.grid(row=1, column=1, padx=(0, 15), sticky=(tk.W, tk.E))
    app.x_entry.insert(0, str(settings.get("x_coord", "100")))

    ttk.Label(coord_frame, text="Y:").grid(row=1, column=2, padx=(0, 5), sticky=tk.W)
    app.y_entry = ttk.Entry(coord_frame, width=8)
    app.y_entry.grid(row=1, column=3, padx=(0, 15), sticky=(tk.W, tk.E))
    app.y_entry.insert(0, str(settings.get("y_coord", "100")))

    app.pick_btn = ttk.Button(
        coord_frame,
        text="Pick Location",
        command=app.start_coordinate_picker,
    )
    app.pick_btn.grid(row=1, column=4, padx=(10, 5), sticky=tk.W)

    ttk.Label(coord_frame, text="Presets:").grid(
        row=2, column=0, padx=(0, 5), pady=(10, 0), sticky=tk.W
    )
    app.preset_var = tk.StringVar()
    app.preset_combo = ttk.Combobox(
        coord_frame,
        textvariable=app.preset_var,
        width=20,
        state="readonly",
    )
    app.preset_combo.grid(
        row=2, column=1, columnspan=3, padx=(0, 10), pady=(10, 0), sticky=(tk.W, tk.E)
    )
    app.update_preset_list()
    app.preset_combo.bind("<<ComboboxSelected>>", app.load_preset)

    app.save_preset_btn = ttk.Button(
        coord_frame,
        text="Save Preset",
        command=app.save_preset,
    )
    app.save_preset_btn.grid(row=2, column=4, pady=(10, 0), sticky=tk.W)

    app.delete_preset_btn = ttk.Button(
        coord_frame,
        text="Delete",
        command=app.delete_preset,
    )
    app.delete_preset_btn.grid(row=2, column=5, padx=(5, 0), pady=(10, 0), sticky=tk.W)

    app._apply_target_mode_state()
