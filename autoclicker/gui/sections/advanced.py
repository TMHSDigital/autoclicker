# SPDX-License-Identifier: CC-BY-NC-4.0
"""Advanced options (burst, safety limits, toggles) in a collapsible disclosure."""

import tkinter as tk
from tkinter import ttk

from .collapsible import CollapsibleFrame


def build_advanced_section(app, parent: ttk.Frame) -> None:
    """Create the collapsible advanced options section."""
    section = CollapsibleFrame(parent, text="Advanced", expanded=False)
    section.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    body = section.body
    body.grid_columnconfigure(1, weight=1)

    settings = app.controller.settings

    ttk.Label(body, text="Burst Mode:").grid(row=0, column=0, sticky=tk.W)
    burst_frame = ttk.Frame(body)
    burst_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

    ttk.Label(burst_frame, text="Clicks:").pack(side=tk.LEFT)
    app.burst_clicks_entry = ttk.Entry(burst_frame, width=5)
    app.burst_clicks_entry.pack(side=tk.LEFT, padx=(0, 10))
    app.burst_clicks_entry.insert(0, str(settings.get("burst_clicks", "1")))

    ttk.Label(burst_frame, text="Pause:").pack(side=tk.LEFT, padx=(10, 0))
    app.burst_pause_entry = ttk.Entry(burst_frame, width=5)
    app.burst_pause_entry.pack(side=tk.LEFT, padx=(0, 5))
    app.burst_pause_entry.insert(0, str(settings.get("burst_pause", "1000")))
    ttk.Label(burst_frame, text="ms").pack(side=tk.LEFT)

    ttk.Label(body, text="Safety:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
    safety_frame = ttk.Frame(body)
    safety_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

    saved_max_clicks = str(settings.get("max_clicks", "0"))
    try:
        has_limit = int(float(saved_max_clicks)) > 0
    except (ValueError, TypeError):
        has_limit = False

    app.limit_clicks_var = tk.BooleanVar(value=has_limit)
    app.max_clicks_entry = ttk.Entry(safety_frame, width=8)

    def _toggle_limit_clicks() -> None:
        app.max_clicks_entry.configure(
            state=tk.NORMAL if app.limit_clicks_var.get() else tk.DISABLED
        )

    ttk.Checkbutton(
        safety_frame,
        text="Limit clicks:",
        variable=app.limit_clicks_var,
        command=_toggle_limit_clicks,
    ).pack(side=tk.LEFT)
    app.max_clicks_entry.pack(side=tk.LEFT, padx=(5, 15))
    app.max_clicks_entry.insert(0, saved_max_clicks if has_limit else "1000")
    _toggle_limit_clicks()

    ttk.Label(safety_frame, text="Auto-stop after:").pack(side=tk.LEFT, padx=(10, 0))
    app.auto_stop_entry = ttk.Entry(safety_frame, width=5)
    app.auto_stop_entry.pack(side=tk.LEFT, padx=(0, 5))
    app.auto_stop_entry.insert(0, str(settings.get("auto_stop_minutes", "0")))
    ttk.Label(safety_frame, text="minutes").pack(side=tk.LEFT)

    toggles_frame = ttk.Frame(body)
    toggles_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(12, 0))

    app.click_queuing_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        toggles_frame,
        text="Enable click queuing",
        variable=app.click_queuing_var,
        command=app._toggle_click_queuing,
    ).pack(anchor=tk.W)

    app.failsafe_var = tk.BooleanVar(value=settings.get("enable_failsafe", True))
    ttk.Checkbutton(
        toggles_frame,
        text="PyAutoGUI failsafe (corner abort)",
        variable=app.failsafe_var,
        command=app._on_failsafe_toggle,
    ).pack(anchor=tk.W, pady=(4, 0))

    app.pause_unfocused_var = tk.BooleanVar(value=settings.get("pause_when_unfocused", False))
    ttk.Checkbutton(
        toggles_frame,
        text="Pause when window loses focus",
        variable=app.pause_unfocused_var,
        command=app._on_failsafe_toggle,
    ).pack(anchor=tk.W, pady=(4, 0))
