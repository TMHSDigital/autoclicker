# SPDX-License-Identifier: CC-BY-NC-4.0
"""Click panel: button, click type, interval, action and spread."""

import tkinter as tk
from tkinter import ttk

from ..styles import MUTED, SEGMENT
from ..widgets.panel import Panel, labeled_row


def build_click_panel(app, parent) -> Panel:
    """Create the Click panel; the caller grids it."""
    panel = Panel(parent, "Click")
    body = panel.body
    settings = app.controller.settings

    def refresh(*_args) -> None:
        app._refresh_click_summary()

    app.button_var = tk.StringVar(value=settings.get("mouse_button", "left"))
    buttons = labeled_row(body, 0, "Button")
    for text, value in (("Left", "left"), ("Right", "right"), ("Middle", "middle")):
        ttk.Radiobutton(
            buttons, text=text, variable=app.button_var, value=value, style=SEGMENT
        ).pack(side=tk.LEFT)
    app.button_var.trace_add("write", refresh)

    app.click_type_var = tk.StringVar(value=settings.get("click_type", "single"))
    types = labeled_row(body, 1, "Type")
    for text, value in (("Single", "single"), ("Double", "double")):
        ttk.Radiobutton(
            types, text=text, variable=app.click_type_var, value=value, style=SEGMENT
        ).pack(side=tk.LEFT)
    app.click_type_var.trace_add("write", refresh)

    every = labeled_row(body, 2, "Every")
    app.interval_entry = ttk.Entry(every, width=6)
    app.interval_entry.pack(side=tk.LEFT, padx=(0, 5))
    app.interval_entry.insert(0, str(settings.get("interval", "1000")))
    app.interval_unit_var = tk.StringVar(value=settings.get("interval_unit", "ms"))
    ttk.Combobox(
        every,
        textvariable=app.interval_unit_var,
        values=["ms", "seconds"],
        width=7,
        state="readonly",
    ).pack(side=tk.LEFT, padx=(0, 8))
    app.interval_unit_var.trace_add("write", refresh)
    ttk.Label(every, text="±").pack(side=tk.LEFT)
    app.variation_entry = ttk.Entry(every, width=4)
    app.variation_entry.pack(side=tk.LEFT, padx=(3, 3))
    app.variation_entry.insert(0, str(settings.get("variation", "0")))
    ttk.Label(every, text="ms").pack(side=tk.LEFT)

    # What each click does: click, hold the button, or press a key.
    actions = labeled_row(body, 3, "Action")
    saved_action = settings.get("action", "click")
    app.action_var = tk.StringVar(
        value=saved_action if saved_action in ("click", "hold", "key") else "click"
    )
    app.action_radios = {}
    for text, value in (("Click", "click"), ("Hold", "hold"), ("Key", "key")):
        app.action_radios[value] = ttk.Radiobutton(
            actions,
            text=text,
            variable=app.action_var,
            value=value,
            style=SEGMENT,
            command=app._apply_action_state,
        )
        app.action_radios[value].pack(side=tk.LEFT)

    details = labeled_row(body, 4, "Hold")
    app.hold_entry = ttk.Entry(details, width=5)
    app.hold_entry.pack(side=tk.LEFT)
    app.hold_entry.insert(0, str(settings.get("hold_ms", "500")))
    ttk.Label(details, text="ms").pack(side=tk.LEFT, padx=(3, 10))
    ttk.Label(details, text="Key").pack(side=tk.LEFT, padx=(0, 5))
    app.key_entry = ttk.Entry(details, width=8)
    app.key_entry.pack(side=tk.LEFT)
    app.key_entry.insert(0, str(settings.get("key", "")))
    app.key_entry.bind("<KeyRelease>", lambda _e: app._refresh_target_summary(), add="+")

    # Click spread (#120): land each click up to N px from the target.
    spread = labeled_row(body, 5, "Spread")
    ttk.Label(spread, text="±").pack(side=tk.LEFT)
    app.spread_entry = ttk.Entry(spread, width=4)
    app.spread_entry.pack(side=tk.LEFT, padx=(3, 3))
    app.spread_entry.insert(0, str(settings.get("click_spread", "0")))
    ttk.Label(spread, text="px around the target (0 = exact)", style=MUTED).pack(side=tk.LEFT)

    for entry in (app.interval_entry, app.variation_entry, app.hold_entry):
        entry.bind("<KeyRelease>", lambda _e: app._refresh_click_summary(), add="+")
    app._apply_action_state()
    return panel
