# SPDX-License-Identifier: CC-BY-NC-4.0
"""Hero: the Start/Stop button, the live readouts and the status line."""

import tkinter as tk
from tkinter import ttk

from ..styles import BG_FRAME, BG_LABEL, BG_MUTED, DANGER
from ..theme import FONT_BOLD, STATUS_COLORS
from ..widgets.run_button import RunButton
from ..widgets.stat_tile import StatTile


def build_hero_section(app, parent) -> ttk.Frame:
    """Create the hero row. Built after the panels: the status line reads the form."""
    hero = ttk.Frame(parent, style=BG_FRAME, padding=(16, 8, 16, 10))
    hero.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
    hero.grid_columnconfigure(1, weight=1)
    app.hero_frame = hero

    app.run_button = RunButton(hero, command=app.toggle_from_button)
    app.run_button.grid(row=0, column=0, rowspan=2, sticky=tk.N, padx=(0, 20))

    stats = ttk.Frame(hero, style=BG_FRAME)
    stats.grid(row=0, column=1, sticky=(tk.W, tk.E))
    app.click_count_var = tk.StringVar(value="0")
    app.runtime_var = tk.StringVar(value="00:00:00")
    app.performance_var = tk.StringVar(value="--")
    app.clicks_tile = StatTile(stats, caption="Clicks", variable=app.click_count_var)
    app.clicks_tile.grid(row=0, column=0, sticky=tk.W, padx=(0, 28))
    app.runtime_tile = StatTile(stats, caption="Runtime", variable=app.runtime_var)
    app.runtime_tile.grid(row=0, column=1, sticky=tk.W, padx=(0, 28))
    app.rate_tile = StatTile(stats, caption="Rate", variable=app.performance_var)
    app.rate_tile.grid(row=0, column=2, sticky=tk.W)

    status = ttk.Frame(hero, style=BG_FRAME)
    status.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(8, 0))
    app.status_var = tk.StringVar(value="Stopped")
    app.status_dot = ttk.Label(
        status, text="●", style=BG_LABEL, foreground=STATUS_COLORS["stopped"]
    )
    app.status_dot.pack(side=tk.LEFT, padx=(0, 6))
    ttk.Label(status, textvariable=app.status_var, style=BG_LABEL, font=FONT_BOLD).pack(
        side=tk.LEFT
    )
    app.coord_var = tk.StringVar(value=app._target_summary())
    ttk.Label(status, textvariable=app.coord_var, style=BG_MUTED).pack(side=tk.LEFT, padx=(10, 0))
    app.click_summary_var = tk.StringVar(value="")
    ttk.Label(status, textvariable=app.click_summary_var, style=BG_MUTED).pack(
        side=tk.LEFT, padx=(10, 0)
    )
    app.emergency_btn = ttk.Button(
        status, text="Emergency stop", style=DANGER, command=app.emergency_stop
    )
    app.emergency_btn.pack(side=tk.RIGHT)
    return hero
