# SPDX-License-Identifier: CC-BY-NC-4.0
"""Essential click settings section (mouse button, click type, interval)."""

import tkinter as tk
from tkinter import ttk

from ..styles import MUTED


def build_click_settings_section(app, parent: ttk.Frame) -> None:
    """Create the essential click settings section."""
    settings_frame = ttk.LabelFrame(parent, text="Click Settings", padding="10")
    settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
    settings_frame.grid_columnconfigure(1, weight=1)

    settings = app.controller.settings

    ttk.Label(settings_frame, text="Mouse Button:").grid(row=0, column=0, sticky=tk.W)
    app.button_var = tk.StringVar(value=settings.get("mouse_button", "left"))
    button_frame = ttk.Frame(settings_frame)
    button_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

    ttk.Radiobutton(button_frame, text="Left", variable=app.button_var, value="left").pack(
        side=tk.LEFT, padx=(0, 10)
    )
    ttk.Radiobutton(button_frame, text="Right", variable=app.button_var, value="right").pack(
        side=tk.LEFT, padx=(0, 10)
    )
    ttk.Radiobutton(button_frame, text="Middle", variable=app.button_var, value="middle").pack(
        side=tk.LEFT
    )

    ttk.Label(settings_frame, text="Click Type:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
    app.click_type_var = tk.StringVar(value=settings.get("click_type", "single"))
    click_type_frame = ttk.Frame(settings_frame)
    click_type_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

    ttk.Radiobutton(
        click_type_frame, text="Single", variable=app.click_type_var, value="single"
    ).pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(
        click_type_frame, text="Double", variable=app.click_type_var, value="double"
    ).pack(side=tk.LEFT)

    ttk.Label(settings_frame, text="Interval:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
    interval_frame = ttk.Frame(settings_frame)
    interval_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

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

    ttk.Label(interval_frame, text="\u00b1").pack(side=tk.LEFT)
    app.variation_entry = ttk.Entry(interval_frame, width=6)
    app.variation_entry.pack(side=tk.LEFT)
    app.variation_entry.insert(0, str(settings.get("variation", "0")))
    ttk.Label(interval_frame, text="ms").pack(side=tk.LEFT)

    # What each click does: click, hold the button, or press a key.
    ttk.Label(settings_frame, text="Action:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
    action_frame = ttk.Frame(settings_frame)
    action_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))
    saved_action = settings.get("action", "click")
    app.action_var = tk.StringVar(
        value=saved_action if saved_action in ("click", "hold", "key") else "click"
    )
    app.action_radios = {}
    for text, value in (("Click", "click"), ("Hold", "hold")):
        app.action_radios[value] = ttk.Radiobutton(
            action_frame,
            text=text,
            variable=app.action_var,
            value=value,
            command=app._apply_action_state,
        )
        app.action_radios[value].pack(side=tk.LEFT, padx=(0, 6))
    app.hold_entry = ttk.Entry(action_frame, width=6)
    app.hold_entry.pack(side=tk.LEFT)
    app.hold_entry.insert(0, str(settings.get("hold_ms", "500")))
    ttk.Label(action_frame, text="ms").pack(side=tk.LEFT, padx=(3, 12))
    app.action_radios["key"] = ttk.Radiobutton(
        action_frame,
        text="Key",
        variable=app.action_var,
        value="key",
        command=app._apply_action_state,
    )
    app.action_radios["key"].pack(side=tk.LEFT, padx=(0, 6))
    app.key_entry = ttk.Entry(action_frame, width=10)
    app.key_entry.pack(side=tk.LEFT)
    app.key_entry.insert(0, str(settings.get("key", "")))
    app.key_entry.bind("<KeyRelease>", lambda _e: app._refresh_target_summary(), add="+")

    # Click spread (#120): land each click up to N px from the target.
    ttk.Label(settings_frame, text="Spread:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
    spread_frame = ttk.Frame(settings_frame)
    spread_frame.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))
    ttk.Label(spread_frame, text="\u00b1").pack(side=tk.LEFT)
    app.spread_entry = ttk.Entry(spread_frame, width=6)
    app.spread_entry.pack(side=tk.LEFT)
    app.spread_entry.insert(0, str(settings.get("click_spread", "0")))
    ttk.Label(
        spread_frame,
        text="px around the target (0 = the exact point)",
        style=MUTED,
    ).pack(side=tk.LEFT, padx=(3, 0))
    app._apply_action_state()
