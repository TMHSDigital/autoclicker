# SPDX-License-Identifier: CC-BY-NC-4.0
"""Target panel: where the clicks go, plus profiles."""

import tkinter as tk
from tkinter import ttk

from ..styles import MUTED, SEGMENT
from ..widgets.panel import Panel

_MODES = (("Fixed", "fixed"), ("Cursor", "cursor"), ("Sequence", "sequence"), ("Image", "image"))


def build_target_panel(app, parent) -> Panel:
    """Create the Target panel; the caller grids it."""
    panel = Panel(parent, "Target")
    body = panel.body
    body.grid_columnconfigure(3, weight=1)

    settings = app.controller.settings
    mode = settings.get("target_mode", "fixed")
    app.target_mode_var = tk.StringVar(
        value=mode if mode in ("fixed", "cursor", "sequence", "image") else "fixed"
    )
    modes = ttk.Frame(body)
    modes.grid(row=0, column=0, columnspan=6, sticky=tk.W, pady=(0, 10))
    for text, value in _MODES:
        ttk.Radiobutton(
            modes,
            text=text,
            variable=app.target_mode_var,
            value=value,
            style=SEGMENT,
            command=app._on_target_mode_change,
        ).pack(side=tk.LEFT)

    ttk.Label(body, text="X").grid(row=1, column=0, padx=(0, 5), sticky=tk.W)
    app.x_entry = ttk.Entry(body, width=7)
    app.x_entry.grid(row=1, column=1, padx=(0, 10), sticky=tk.W)
    app.x_entry.insert(0, str(settings.get("x_coord", "100")))

    ttk.Label(body, text="Y").grid(row=1, column=2, padx=(0, 5), sticky=tk.W)
    app.y_entry = ttk.Entry(body, width=7)
    app.y_entry.grid(row=1, column=3, padx=(0, 10), sticky=tk.W)
    app.y_entry.insert(0, str(settings.get("y_coord", "100")))
    # Keep the status line's target in step with what is typed (#102).
    for entry in (app.x_entry, app.y_entry):
        entry.bind("<KeyRelease>", lambda _e: app._refresh_target_summary(), add="+")

    app.pick_btn = ttk.Button(body, text="Pick", command=app.start_coordinate_picker)
    app.pick_btn.grid(row=1, column=4, columnspan=2, sticky=tk.W)

    ttk.Label(body, text="Profile").grid(row=2, column=0, padx=(0, 5), pady=(10, 0), sticky=tk.W)
    app.preset_var = tk.StringVar()
    app.preset_combo = ttk.Combobox(body, textvariable=app.preset_var, width=11, state="readonly")
    app.preset_combo.grid(
        row=2, column=1, columnspan=3, padx=(0, 8), pady=(10, 0), sticky=(tk.W, tk.E)
    )
    app.update_preset_list()
    app.preset_combo.bind("<<ComboboxSelected>>", app.load_preset)

    app.save_preset_btn = ttk.Button(body, text="Save", style="Toolbutton", command=app.save_preset)
    app.save_preset_btn.grid(row=2, column=4, pady=(10, 0), sticky=tk.W)
    app.delete_preset_btn = ttk.Button(
        body, text="Delete", style="Toolbutton", command=app.delete_preset
    )
    app.delete_preset_btn.grid(row=2, column=5, padx=(2, 0), pady=(10, 0), sticky=tk.W)

    # What the selected profile restores, e.g. "(800, 600) · every 100 ms · left single"
    app.preset_summary_var = tk.StringVar(value="")
    ttk.Label(body, textvariable=app.preset_summary_var, style=MUTED, wraplength=240).grid(
        row=3, column=0, columnspan=6, pady=(4, 0), sticky=tk.W
    )

    _build_sequence_panel(app, body, settings)
    _build_image_panel(app, body, settings)

    app._apply_target_mode_state()
    return panel


def _build_image_panel(app, body: ttk.Frame, settings) -> None:
    """Image mode: capture a button image; clicks go wherever it appears nearby."""
    app.image_path = str(settings.get("image_path", "") or "")
    region = settings.get("image_region", [])
    app.image_region = list(region) if isinstance(region, list) else []

    app.image_frame = ttk.Frame(body)
    app.image_frame.grid(row=5, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 0))
    row = ttk.Frame(app.image_frame)
    row.pack(fill=tk.X)
    ttk.Button(row, text="Capture…", command=app.capture_image).pack(side=tk.LEFT)
    app.image_clear_btn = ttk.Button(row, text="Clear", command=app.clear_image)
    app.image_clear_btn.pack(side=tk.LEFT, padx=(5, 0))
    # Thumbnail of the armed image (#123); empty until one is captured.
    app.image_preview = ttk.Label(row)
    app.image_preview.pack(side=tk.LEFT, padx=(10, 0))
    app.image_info_var = tk.StringVar(value="")
    ttk.Label(app.image_frame, textvariable=app.image_info_var, wraplength=240).pack(
        anchor=tk.W, pady=(4, 0)
    )
    margin_row = ttk.Frame(app.image_frame)
    margin_row.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(margin_row, text="Search").pack(side=tk.LEFT)
    app.image_margin_entry = ttk.Entry(margin_row, width=5)
    app.image_margin_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.image_margin_entry.insert(0, str(settings.get("image_margin", "150")))
    ttk.Label(margin_row, text="px around the capture").pack(side=tk.LEFT)
    tolerance_row = ttk.Frame(app.image_frame)
    tolerance_row.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(tolerance_row, text="Tolerance").pack(side=tk.LEFT)
    app.image_tolerance_entry = ttk.Entry(tolerance_row, width=4)
    app.image_tolerance_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.image_tolerance_entry.insert(0, str(settings.get("image_tolerance", "0")))
    ttk.Label(tolerance_row, text="0 = exact, up to 64", style=MUTED).pack(side=tk.LEFT)
    app._refresh_image_label()


def _build_sequence_panel(app, body: ttk.Frame, settings) -> None:
    """Step list for sequence mode; shown only while Sequence is selected."""
    saved, error = settings.parse_input("sequence", settings.get("sequence", []))
    app.sequence_steps = saved if error is None else []

    app.sequence_frame = ttk.Frame(body)
    app.sequence_frame.grid(row=4, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 0))
    app.sequence_frame.grid_columnconfigure(0, weight=1)

    app.sequence_list = tk.Listbox(
        app.sequence_frame, height=6, width=18, activestyle="none", exportselection=False
    )
    app.sequence_list.grid(row=0, column=0, rowspan=6, sticky=(tk.W, tk.E, tk.N, tk.S))

    buttons = (
        ("Record", app.toggle_sequence_recording),
        ("Add point", app.add_sequence_point),
        ("Wait…", app.edit_sequence_delay),
        ("Up", lambda: app.move_sequence_step(-1)),
        ("Down", lambda: app.move_sequence_step(1)),
        ("Remove", app.remove_sequence_step),
    )
    for row, (text, command) in enumerate(buttons):
        ttk.Button(app.sequence_frame, text=text, width=9, command=command).grid(
            row=row, column=1, padx=(8, 0), pady=(0, 3), sticky=tk.W
        )

    repeat_frame = ttk.Frame(app.sequence_frame)
    repeat_frame.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))
    ttk.Label(repeat_frame, text="Repeat").pack(side=tk.LEFT)
    app.sequence_repeat_entry = ttk.Entry(repeat_frame, width=5)
    app.sequence_repeat_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.sequence_repeat_entry.insert(0, str(settings.get("sequence_repeat", "0")))
    ttk.Label(repeat_frame, text="times (0 = until stopped)", style=MUTED).pack(side=tk.LEFT)

    app._refresh_sequence_list()
