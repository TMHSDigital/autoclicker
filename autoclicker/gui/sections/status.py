# SPDX-License-Identifier: CC-BY-NC-4.0
"""Compact status bar section."""

import tkinter as tk
from tkinter import ttk

_DOT = "\u25cf"  # ●

_COLORS = {
    "running": "#2ea043",
    "stopped": "#8b949e",
    "alert": "#d29922",
    "error": "#cf222e",
}


def _state_color(message: str) -> str:
    text = message.lower()
    if "running" in text or "click anywhere" in text:
        return _COLORS["running"]
    if "emergency" in text or "safety" in text or "failed" in text or "error" in text:
        return _COLORS["error"]
    if "cancel" in text or "selected" in text:
        return _COLORS["alert"]
    return _COLORS["stopped"]


def build_status_section(app, parent: ttk.Frame) -> None:
    """Create a compact status bar."""
    status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
    status_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    status_frame.grid_columnconfigure(1, weight=1)

    app.status_var = tk.StringVar(value="Stopped")

    dot = ttk.Label(status_frame, text=_DOT, foreground=_state_color("stopped"))
    dot.grid(row=0, column=0, sticky=tk.W, padx=(0, 8))

    ttk.Label(
        status_frame,
        textvariable=app.status_var,
        font=("Segoe UI", 11, "bold"),
    ).grid(row=0, column=1, sticky=tk.W)

    def _recolor(*_args) -> None:
        dot.configure(foreground=_state_color(app.status_var.get()))

    app.status_var.trace_add("write", _recolor)

    metrics = ttk.Frame(status_frame)
    metrics.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))

    app.click_count_var = tk.StringVar(value="Clicks: 0")
    app.runtime_var = tk.StringVar(value="Runtime: 0:00:00")
    app.performance_var = tk.StringVar(value="Performance: --")

    ttk.Label(metrics, textvariable=app.click_count_var).pack(side=tk.LEFT)
    ttk.Label(metrics, text="\u00b7").pack(side=tk.LEFT, padx=8)
    ttk.Label(metrics, textvariable=app.runtime_var).pack(side=tk.LEFT)
    ttk.Label(metrics, text="\u00b7").pack(side=tk.LEFT, padx=8)
    ttk.Label(metrics, textvariable=app.performance_var).pack(side=tk.LEFT)

    app.coord_var = tk.StringVar(value="Target: (100, 100)")
    ttk.Label(status_frame, textvariable=app.coord_var, foreground="#8b949e").grid(
        row=2, column=0, columnspan=2, sticky=tk.W, pady=(6, 0)
    )
