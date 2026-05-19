# SPDX-License-Identifier: CC-BY-NC-4.0
"""Status display section."""

import tkinter as tk
from tkinter import ttk


def build_status_section(app, parent: ttk.Frame) -> None:
    """Create status display section."""
    status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
    status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    app.status_var = tk.StringVar(value="Stopped")
    app.status_label = ttk.Label(
        status_frame,
        textvariable=app.status_var,
        font=("Arial", 12, "bold"),
    )
    app.status_label.pack(anchor=tk.W)

    app.click_count_var = tk.StringVar(value="Clicks: 0")
    ttk.Label(status_frame, textvariable=app.click_count_var).pack(anchor=tk.W, pady=(5, 0))

    app.runtime_var = tk.StringVar(value="Runtime: 0:00:00")
    ttk.Label(status_frame, textvariable=app.runtime_var).pack(anchor=tk.W, pady=(2, 0))

    app.coord_var = tk.StringVar(value="Target: (100, 100)")
    ttk.Label(status_frame, textvariable=app.coord_var).pack(anchor=tk.W, pady=(2, 0))

    app.performance_var = tk.StringVar(value="Performance: --")
    ttk.Label(status_frame, textvariable=app.performance_var).pack(anchor=tk.W, pady=(2, 0))
