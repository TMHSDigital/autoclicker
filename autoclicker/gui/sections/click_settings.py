# SPDX-License-Identifier: CC-BY-NC-4.0
"""Click settings and safety options section."""

import tkinter as tk
from tkinter import ttk


def build_click_settings_section(app, parent: ttk.Frame) -> None:
    """Create click settings section."""
    settings_frame = ttk.LabelFrame(parent, text="Click Settings", padding="10")
    settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    settings_frame.grid_columnconfigure(1, weight=1)
    settings_frame.grid_columnconfigure(2, weight=1)
    settings_frame.grid_columnconfigure(3, weight=1)

    settings = app.controller.settings

    ttk.Label(settings_frame, text="Mouse Button:").grid(row=0, column=0, sticky=tk.W)
    app.button_var = tk.StringVar(value=settings.get("mouse_button", "left"))
    button_frame = ttk.Frame(settings_frame)
    button_frame.grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0))

    ttk.Radiobutton(
        button_frame, text="Left", variable=app.button_var, value="left"
    ).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(
        button_frame, text="Right", variable=app.button_var, value="right"
    ).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(
        button_frame, text="Middle", variable=app.button_var, value="middle"
    ).pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Click Type:").grid(
        row=1, column=0, sticky=tk.W, pady=(10, 0)
    )
    app.click_type_var = tk.StringVar(value=settings.get("click_type", "single"))
    click_type_frame = ttk.Frame(settings_frame)
    click_type_frame.grid(
        row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0)
    )

    ttk.Radiobutton(
        click_type_frame, text="Single", variable=app.click_type_var, value="single"
    ).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(
        click_type_frame, text="Double", variable=app.click_type_var, value="double"
    ).pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Interval:").grid(
        row=2, column=0, sticky=tk.W, pady=(10, 0)
    )
    interval_frame = ttk.Frame(settings_frame)
    interval_frame.grid(
        row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0)
    )

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

    ttk.Label(interval_frame, text="±").pack(side=tk.LEFT)
    app.variation_entry = ttk.Entry(interval_frame, width=6)
    app.variation_entry.pack(side=tk.LEFT)
    app.variation_entry.insert(0, str(settings.get("variation", "0")))
    ttk.Label(interval_frame, text="ms").pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Burst Mode:").grid(
        row=3, column=0, sticky=tk.W, pady=(10, 0)
    )
    burst_frame = ttk.Frame(settings_frame)
    burst_frame.grid(
        row=3, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0)
    )

    ttk.Label(burst_frame, text="Clicks:").pack(side=tk.LEFT)
    app.burst_clicks_entry = ttk.Entry(burst_frame, width=5)
    app.burst_clicks_entry.pack(side=tk.LEFT, padx=(0, 10))
    app.burst_clicks_entry.insert(0, str(settings.get("burst_clicks", "1")))

    ttk.Label(burst_frame, text="Pause:").pack(side=tk.LEFT, padx=(10, 0))
    app.burst_pause_entry = ttk.Entry(burst_frame, width=5)
    app.burst_pause_entry.pack(side=tk.LEFT, padx=(0, 5))
    app.burst_pause_entry.insert(0, str(settings.get("burst_pause", "1000")))
    ttk.Label(burst_frame, text="ms").pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Safety:").grid(
        row=4, column=0, sticky=tk.W, pady=(10, 0)
    )
    safety_frame = ttk.Frame(settings_frame)
    safety_frame.grid(
        row=4, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0)
    )

    ttk.Label(safety_frame, text="Max clicks:").pack(side=tk.LEFT)
    app.max_clicks_entry = ttk.Entry(safety_frame, width=8)
    app.max_clicks_entry.pack(side=tk.LEFT, padx=(0, 15))
    app.max_clicks_entry.insert(0, str(settings.get("max_clicks", "0")))

    ttk.Label(safety_frame, text="Auto-stop after:").pack(side=tk.LEFT, padx=(10, 0))
    app.auto_stop_entry = ttk.Entry(safety_frame, width=5)
    app.auto_stop_entry.pack(side=tk.LEFT, padx=(0, 5))
    app.auto_stop_entry.insert(0, str(settings.get("auto_stop_minutes", "0")))
    ttk.Label(safety_frame, text="minutes").pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Advanced:").grid(
        row=5, column=0, sticky=tk.W, pady=(15, 0)
    )
    advanced_frame = ttk.Frame(settings_frame)
    advanced_frame.grid(
        row=5, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(15, 0)
    )

    app.click_queuing_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        advanced_frame,
        text="Enable Click Queuing",
        variable=app.click_queuing_var,
        command=app._toggle_click_queuing,
    ).pack(side=tk.LEFT)

    app.failsafe_var = tk.BooleanVar(value=settings.get("enable_failsafe", True))
    ttk.Checkbutton(
        advanced_frame,
        text="PyAutoGUI Failsafe (corner abort)",
        variable=app.failsafe_var,
        command=app._on_failsafe_toggle,
    ).pack(side=tk.LEFT, padx=(10, 0))

    app.pause_unfocused_var = tk.BooleanVar(
        value=settings.get("pause_when_unfocused", False)
    )
    ttk.Checkbutton(
        advanced_frame,
        text="Pause when window loses focus",
        variable=app.pause_unfocused_var,
    ).pack(side=tk.LEFT, padx=(10, 0))
