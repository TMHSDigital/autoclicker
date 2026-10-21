# SPDX-License-Identifier: CC-BY-NC-4.0
"""Timing and Safety: collapsible panels that summarise themselves while closed."""

import tkinter as tk
from tkinter import ttk

from ..widgets.panel import CollapsiblePanel, labeled_row


def build_timing_panel(app, parent) -> CollapsiblePanel:
    """Burst, start delay and start-at time."""
    panel = CollapsiblePanel(parent, "Timing")
    _build_timing(app, panel.body, app.controller.settings)
    for entry in (
        app.burst_clicks_entry,
        app.burst_pause_entry,
        app.start_delay_entry,
        app.start_at_entry,
    ):
        _refresh_on_edit(app, entry)
    return panel


def build_safety_panel(app, parent) -> CollapsiblePanel:
    """Limits, speed limit, pixel condition, failsafe and focus pause."""
    panel = CollapsiblePanel(parent, "Safety")
    _build_safety(app, panel.body, app.controller.settings)
    for entry in (app.max_clicks_entry, app.auto_stop_entry, app.max_cps_entry):
        _refresh_on_edit(app, entry)
    app.condition_var.trace_add("write", lambda *_: app._refresh_panel_summaries())
    return panel


def _refresh_on_edit(app, entry: ttk.Entry) -> None:
    for sequence in ("<KeyRelease>", "<FocusOut>"):
        entry.bind(sequence, lambda _e: app._refresh_panel_summaries(), add="+")


def _build_timing(app, body: ttk.Frame, settings) -> None:
    # Reads as "Burst: [3] clicks, [100] ms apart"; the main Interval is the wait between bursts.
    burst = labeled_row(body, 0, "Burst")
    app.burst_clicks_entry = ttk.Entry(burst, width=4)
    app.burst_clicks_entry.pack(side=tk.LEFT)
    app.burst_clicks_entry.insert(0, str(settings.get("burst_clicks", "1")))
    ttk.Label(burst, text="clicks,").pack(side=tk.LEFT, padx=(5, 8))
    app.burst_pause_entry = ttk.Entry(burst, width=5)
    app.burst_pause_entry.pack(side=tk.LEFT)
    app.burst_pause_entry.insert(0, str(settings.get("burst_pause", "1000")))
    ttk.Label(burst, text="ms apart").pack(side=tk.LEFT, padx=(5, 0))

    # Countdown before a Start-button or tray start; hotkey starts are immediate.
    delay = labeled_row(body, 1, "Start delay")
    app.start_delay_entry = ttk.Entry(delay, width=4)
    app.start_delay_entry.pack(side=tk.LEFT)
    app.start_delay_entry.insert(0, str(settings.get("start_delay_seconds", "3")))
    ttk.Label(delay, text="s after Start (hotkeys start at once)", wraplength=170).pack(
        side=tk.LEFT, padx=(5, 0)
    )

    # Or wait for a time of day (#121); blank uses the delay above.
    start_at = labeled_row(body, 2, "Start at")
    app.start_at_entry = ttk.Entry(start_at, width=6)
    app.start_at_entry.pack(side=tk.LEFT)
    app.start_at_entry.insert(0, str(settings.get("start_at", "") or ""))
    ttk.Label(
        start_at, text="24-hour time, e.g. 09:30 (blank = use the delay)", wraplength=170
    ).pack(side=tk.LEFT, padx=(5, 0))


def _build_safety(app, body: ttk.Frame, settings) -> None:
    limits = labeled_row(body, 0, "Limits")
    saved_max_clicks = str(settings.get("max_clicks", "0"))
    try:
        has_limit = int(float(saved_max_clicks)) > 0
    except (ValueError, TypeError):
        has_limit = False

    app.limit_clicks_var = tk.BooleanVar(value=has_limit)
    app.max_clicks_entry = ttk.Entry(limits, width=6)

    def _toggle_limit_clicks() -> None:
        app.max_clicks_entry.configure(
            state=tk.NORMAL if app.limit_clicks_var.get() else tk.DISABLED
        )
        app._refresh_panel_summaries()

    ttk.Checkbutton(
        limits,
        text="Stop after",
        variable=app.limit_clicks_var,
        command=_toggle_limit_clicks,
    ).pack(side=tk.LEFT)
    app.max_clicks_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.max_clicks_entry.insert(0, saved_max_clicks if has_limit else "1000")
    app.max_clicks_entry.configure(state=tk.NORMAL if has_limit else tk.DISABLED)
    ttk.Label(limits, text="clicks").pack(side=tk.LEFT)
    minutes = labeled_row(body, 1, "")
    ttk.Label(minutes, text="or after").pack(side=tk.LEFT)
    app.auto_stop_entry = ttk.Entry(minutes, width=4)
    app.auto_stop_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.auto_stop_entry.insert(0, str(settings.get("auto_stop_minutes", "0")))
    ttk.Label(minutes, text="minutes").pack(side=tk.LEFT)

    # Runaway guard ceiling: a run stops if more clicks than this land in one second.
    speed = labeled_row(body, 2, "Speed limit")
    app.max_cps_entry = ttk.Entry(speed, width=4)
    app.max_cps_entry.pack(side=tk.LEFT)
    app.max_cps_entry.insert(0, str(settings.get("max_cps_ceiling", "50")))
    ttk.Label(speed, text="clicks per second max (0 = off)", wraplength=170).pack(
        side=tk.LEFT, padx=(5, 0)
    )

    # Only click while a pixel shows an expected color.
    cond = labeled_row(body, 3, "Only when")
    saved = settings.get("condition", "none")
    app.condition_var = tk.StringVar(value=saved if saved in ("none", "wait", "stop") else "none")
    ttk.Combobox(
        cond,
        textvariable=app.condition_var,
        values=["none", "wait", "stop"],
        width=5,
        state="readonly",
    ).pack(side=tk.LEFT)
    app.condition_var.trace_add("write", lambda *_: app._refresh_condition_label())
    app.condition_label_var = tk.StringVar(value="")
    ttk.Label(cond, textvariable=app.condition_label_var).pack(side=tk.LEFT, padx=(6, 6))
    app.condition_swatch = tk.Label(cond, width=2, relief="solid", borderwidth=1)
    app.condition_swatch.pack(side=tk.LEFT)
    ttk.Label(cond, text="±").pack(side=tk.LEFT, padx=(6, 0))
    app.condition_tolerance_entry = ttk.Entry(cond, width=3)
    app.condition_tolerance_entry.pack(side=tk.LEFT)
    app.condition_tolerance_entry.insert(0, str(settings.get("condition_tolerance", "16")))
    ttk.Button(cond, text="Sample…", style="Toolbutton", command=app.sample_condition_pixel).pack(
        side=tk.LEFT, padx=(6, 0)
    )
    app.condition_point = (
        settings.get("condition_x", 0),
        settings.get("condition_y", 0),
        str(settings.get("condition_color", "#000000")),
    )
    app._refresh_condition_label()

    toggles = ttk.Frame(body)
    toggles.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    app.failsafe_var = tk.BooleanVar(value=settings.get("enable_failsafe", True))
    ttk.Checkbutton(
        toggles,
        text="Corner failsafe (mouse in a corner stops)",
        variable=app.failsafe_var,
        command=app._on_failsafe_toggle,
    ).pack(anchor=tk.W)
    app.pause_unfocused_var = tk.BooleanVar(value=settings.get("pause_when_unfocused", False))
    ttk.Checkbutton(
        toggles,
        text="Pause when the target window isn't in front",
        variable=app.pause_unfocused_var,
        command=app._sync_safety_from_ui,
    ).pack(anchor=tk.W, pady=(4, 0))
