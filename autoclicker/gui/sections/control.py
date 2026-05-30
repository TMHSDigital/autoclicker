# SPDX-License-Identifier: CC-BY-NC-4.0
"""Start/stop control buttons section."""

import tkinter as tk
from tkinter import ttk


def build_control_section(app, parent: ttk.Frame) -> None:
    """Create control buttons section."""
    control_frame = ttk.Frame(parent)
    control_frame.grid(row=4, column=0, columnspan=2, pady=(0, 15))

    app.start_btn = ttk.Button(
        control_frame,
        text="Start (F6)",
        command=app.start_clicking,
        style="Accent.TButton",
        width=15,
    )
    app.start_btn.pack(side=tk.LEFT, padx=(0, 10))

    app.stop_btn = ttk.Button(
        control_frame,
        text="Stop (F7)",
        command=app.stop_clicking,
        state=tk.DISABLED,
        width=15,
    )
    app.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

    app.emergency_btn = ttk.Button(
        control_frame,
        text="Emergency Stop (ESC)",
        command=app.emergency_stop,
        width=20,
    )
    app.emergency_btn.pack(side=tk.LEFT)
