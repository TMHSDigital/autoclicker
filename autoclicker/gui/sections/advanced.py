# SPDX-License-Identifier: CC-BY-NC-4.0
"""Advanced options, grouped into collapsible Timing, Safety and App sections.

All three start collapsed so the window stays short; each opens on its own.
"""

import tkinter as tk
from tkinter import ttk

from .collapsible import CollapsibleFrame


def _row(body: ttk.Frame, row: int, label: str) -> ttk.Frame:
    """A labeled row: label in column 0, a frame for the controls in column 1."""
    pady = (0, 0) if row == 0 else (10, 0)
    ttk.Label(body, text=label).grid(row=row, column=0, sticky=tk.W, pady=pady)
    frame = ttk.Frame(body)
    frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=pady)
    return frame


def _section(container: ttk.Frame, row: int, text: str) -> ttk.Frame:
    section = CollapsibleFrame(container, text=text, expanded=False)
    section.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 4))
    section.body.grid_columnconfigure(1, weight=1)
    return section.body


def build_advanced_section(app, parent: ttk.Frame) -> None:
    """Create the Timing, Safety and App sections."""
    container = ttk.Frame(parent)
    container.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    container.grid_columnconfigure(0, weight=1)
    settings = app.controller.settings

    _build_timing(app, _section(container, 0, "Timing"), settings)
    _build_safety(app, _section(container, 1, "Safety"), settings)
    _build_app_options(app, _section(container, 2, "App"), settings)


def _build_timing(app, body: ttk.Frame, settings) -> None:
    # Reads as "Burst: [3] clicks, [100] ms apart"; the main Interval is the wait between bursts.
    burst = _row(body, 0, "Burst:")
    app.burst_clicks_entry = ttk.Entry(burst, width=5)
    app.burst_clicks_entry.pack(side=tk.LEFT)
    app.burst_clicks_entry.insert(0, str(settings.get("burst_clicks", "1")))
    ttk.Label(burst, text="clicks,").pack(side=tk.LEFT, padx=(5, 10))
    app.burst_pause_entry = ttk.Entry(burst, width=6)
    app.burst_pause_entry.pack(side=tk.LEFT)
    app.burst_pause_entry.insert(0, str(settings.get("burst_pause", "1000")))
    ttk.Label(burst, text="ms apart").pack(side=tk.LEFT, padx=(5, 0))

    # Countdown before a Start-button or tray start; hotkey starts are immediate.
    delay = _row(body, 1, "Start delay:")
    app.start_delay_entry = ttk.Entry(delay, width=6)
    app.start_delay_entry.pack(side=tk.LEFT)
    app.start_delay_entry.insert(0, str(settings.get("start_delay_seconds", "3")))
    ttk.Label(delay, text="seconds after the Start button (hotkeys start at once)").pack(
        side=tk.LEFT, padx=(5, 0)
    )

    # Or wait for a time of day (#121); blank uses the delay above.
    start_at = _row(body, 2, "Start at:")
    app.start_at_entry = ttk.Entry(start_at, width=6)
    app.start_at_entry.pack(side=tk.LEFT)
    app.start_at_entry.insert(0, str(settings.get("start_at", "") or ""))
    ttk.Label(start_at, text="24-hour time, such as 09:30 (blank = use the delay)").pack(
        side=tk.LEFT, padx=(5, 0)
    )


def _build_safety(app, body: ttk.Frame, settings) -> None:
    limits = _row(body, 0, "Limits:")
    saved_max_clicks = str(settings.get("max_clicks", "0"))
    try:
        has_limit = int(float(saved_max_clicks)) > 0
    except (ValueError, TypeError):
        has_limit = False

    app.limit_clicks_var = tk.BooleanVar(value=has_limit)
    app.max_clicks_entry = ttk.Entry(limits, width=8)

    def _toggle_limit_clicks() -> None:
        app.max_clicks_entry.configure(
            state=tk.NORMAL if app.limit_clicks_var.get() else tk.DISABLED
        )

    ttk.Checkbutton(
        limits,
        text="Stop after",
        variable=app.limit_clicks_var,
        command=_toggle_limit_clicks,
    ).pack(side=tk.LEFT)
    app.max_clicks_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.max_clicks_entry.insert(0, saved_max_clicks if has_limit else "1000")
    _toggle_limit_clicks()
    ttk.Label(limits, text="clicks, or after").pack(side=tk.LEFT)
    app.auto_stop_entry = ttk.Entry(limits, width=5)
    app.auto_stop_entry.pack(side=tk.LEFT, padx=(5, 5))
    app.auto_stop_entry.insert(0, str(settings.get("auto_stop_minutes", "0")))
    ttk.Label(limits, text="minutes").pack(side=tk.LEFT)

    # Runaway guard ceiling: a run stops if more clicks than this land in one second.
    speed = _row(body, 1, "Speed limit:")
    app.max_cps_entry = ttk.Entry(speed, width=6)
    app.max_cps_entry.pack(side=tk.LEFT)
    app.max_cps_entry.insert(0, str(settings.get("max_cps_ceiling", "50")))
    ttk.Label(speed, text="clicks per second max (0 = off)").pack(side=tk.LEFT, padx=(5, 0))

    # Only click while a pixel shows an expected color.
    cond = _row(body, 2, "Only when:")
    saved = settings.get("condition", "none")
    app.condition_var = tk.StringVar(value=saved if saved in ("none", "wait", "stop") else "none")
    ttk.Combobox(
        cond,
        textvariable=app.condition_var,
        values=["none", "wait", "stop"],
        width=6,
        state="readonly",
    ).pack(side=tk.LEFT)
    app.condition_var.trace_add("write", lambda *_: app._refresh_condition_label())
    app.condition_label_var = tk.StringVar(value="")
    ttk.Label(cond, textvariable=app.condition_label_var).pack(side=tk.LEFT, padx=(6, 6))
    app.condition_swatch = tk.Label(cond, width=2, relief="solid", borderwidth=1)
    app.condition_swatch.pack(side=tk.LEFT)
    ttk.Label(cond, text="±").pack(side=tk.LEFT, padx=(6, 0))
    app.condition_tolerance_entry = ttk.Entry(cond, width=4)
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
    toggles.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    app.failsafe_var = tk.BooleanVar(value=settings.get("enable_failsafe", True))
    ttk.Checkbutton(
        toggles,
        text="Corner failsafe (slam the mouse into a corner to stop)",
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


def _build_app_options(app, body: ttk.Frame, settings) -> None:
    app.minimize_to_tray_var = tk.BooleanVar(value=bool(settings.get("minimize_to_tray", True)))
    ttk.Checkbutton(
        body,
        text="Minimize to tray",
        variable=app.minimize_to_tray_var,
        command=app._on_minimize_to_tray_toggle,
    ).grid(row=0, column=0, columnspan=2, sticky=tk.W)
    app.check_updates_var = tk.BooleanVar(value=settings.get("check_for_updates") is True)
    ttk.Checkbutton(
        body,
        text="Check GitHub for new versions once a day",
        variable=app.check_updates_var,
        command=app._on_check_updates_toggle,
    ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
    ttk.Button(body, text="Hotkeys…", command=app.open_hotkeys_dialog).grid(
        row=2, column=0, sticky=tk.W, pady=(10, 0)
    )
