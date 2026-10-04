# SPDX-License-Identifier: CC-BY-NC-4.0
"""Target coordinates and profiles section."""

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
    app.target_mode_var = tk.StringVar(
        value=mode if mode in ("fixed", "cursor", "sequence") else "fixed"
    )
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
    ).pack(side=tk.LEFT, padx=(0, 15))
    ttk.Radiobutton(
        mode_frame,
        text="Sequence",
        variable=app.target_mode_var,
        value="sequence",
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

    ttk.Label(coord_frame, text="Profiles:").grid(
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
        text="Save Profile",
        command=app.save_preset,
    )
    app.save_preset_btn.grid(row=2, column=4, pady=(10, 0), sticky=tk.W)

    app.delete_preset_btn = ttk.Button(
        coord_frame,
        text="Delete",
        command=app.delete_preset,
    )
    app.delete_preset_btn.grid(row=2, column=5, padx=(5, 0), pady=(10, 0), sticky=tk.W)

    # What the selected profile restores, e.g. "(800, 600) · every 100 ms · left single"
    app.preset_summary_var = tk.StringVar(value="")
    ttk.Label(
        coord_frame,
        textvariable=app.preset_summary_var,
        foreground="#8b949e",
    ).grid(row=3, column=1, columnspan=3, padx=(0, 10), pady=(4, 0), sticky=tk.W)
    io_frame = ttk.Frame(coord_frame)
    io_frame.grid(row=3, column=4, columnspan=2, pady=(4, 0), sticky=tk.W)
    ttk.Button(io_frame, text="Import\u2026", style="Toolbutton", command=app.import_profiles).pack(
        side=tk.LEFT
    )
    ttk.Button(io_frame, text="Export\u2026", style="Toolbutton", command=app.export_profiles).pack(
        side=tk.LEFT, padx=(5, 0)
    )

    _build_sequence_panel(app, coord_frame, settings)

    app._apply_target_mode_state()


def _build_sequence_panel(app, coord_frame: ttk.LabelFrame, settings) -> None:
    """Step list for sequence mode; shown only while Sequence is selected."""
    saved, error = settings.parse_input("sequence", settings.get("sequence", []))
    app.sequence_steps = saved if error is None else []

    app.sequence_frame = ttk.Frame(coord_frame)
    app.sequence_frame.grid(row=4, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 0))
    app.sequence_frame.grid_columnconfigure(0, weight=1)

    app.sequence_list = tk.Listbox(
        app.sequence_frame, height=5, activestyle="none", exportselection=False
    )
    app.sequence_list.grid(row=0, column=0, rowspan=5, sticky=(tk.W, tk.E, tk.N, tk.S))

    buttons = (
        ("Add point", app.add_sequence_point),
        ("Wait\u2026", app.edit_sequence_delay),
        ("Up", lambda: app.move_sequence_step(-1)),
        ("Down", lambda: app.move_sequence_step(1)),
        ("Remove", app.remove_sequence_step),
    )
    for row, (text, command) in enumerate(buttons):
        ttk.Button(app.sequence_frame, text=text, width=10, command=command).grid(
            row=row, column=1, padx=(8, 0), pady=(0, 4), sticky=tk.W
        )

    repeat_frame = ttk.Frame(app.sequence_frame)
    repeat_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))
    ttk.Label(repeat_frame, text="Repeat:").pack(side=tk.LEFT)
    app.sequence_repeat_entry = ttk.Entry(repeat_frame, width=7)
    app.sequence_repeat_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.sequence_repeat_entry.insert(0, str(settings.get("sequence_repeat", "0")))
    ttk.Label(repeat_frame, text="times (0 = until stopped); the Interval separates rounds").pack(
        side=tk.LEFT
    )

    app._refresh_sequence_list()
