# SPDX-License-Identifier: CC-BY-NC-4.0
"""Compact status bar section."""

import tkinter as tk
from tkinter import ttk

_DOT = "\u25cf"  # ●

# Status dot colors by explicit state (set by AutoclickerApp._set_status_message).
STATUS_COLORS = {
    "running": "#2ea043",
    "stopped": "#8b949e",
    "alert": "#d29922",
    "error": "#cf222e",
}


def build_status_section(app, parent: ttk.Frame) -> None:
    """Create a compact status bar."""
    status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
    status_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    status_frame.grid_columnconfigure(1, weight=1)

    app.status_var = tk.StringVar(value="Stopped")

    app.status_dot = ttk.Label(status_frame, text=_DOT, foreground=STATUS_COLORS["stopped"])
    app.status_dot.grid(row=0, column=0, sticky=tk.W, padx=(0, 8))

    ttk.Label(
        status_frame,
        textvariable=app.status_var,
        font=("Segoe UI", 11, "bold"),
    ).grid(row=0, column=1, sticky=tk.W)

    metrics = ttk.Frame(status_frame)
    metrics.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))

    app.click_count_var = tk.StringVar(value="Clicks: 0")
    app.runtime_var = tk.StringVar(value="Runtime: 00:00:00")
    app.performance_var = tk.StringVar(value="Performance: --")

    ttk.Label(metrics, textvariable=app.click_count_var).pack(side=tk.LEFT)
    ttk.Label(metrics, text="\u00b7").pack(side=tk.LEFT, padx=8)
    ttk.Label(metrics, textvariable=app.runtime_var).pack(side=tk.LEFT)
    ttk.Label(metrics, text="\u00b7").pack(side=tk.LEFT, padx=8)
    ttk.Label(metrics, textvariable=app.performance_var).pack(side=tk.LEFT)

    app.coord_var = tk.StringVar(value="Target: (100, 100)")
    ttk.Label(status_frame, textvariable=app.coord_var, foreground=STATUS_COLORS["stopped"]).grid(
        row=2, column=0, columnspan=2, sticky=tk.W, pady=(6, 0)
    )
