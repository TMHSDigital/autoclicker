# SPDX-License-Identifier: CC-BY-NC-4.0
"""Sequence target mode: the step list and its editing (#72)."""

from __future__ import annotations

import tkinter as tk

from ...core.settings_manager import MAX_SEQUENCE_STEPS, MAX_STEP_DELAY_MS
from .. import dialogs
from .base import AppBase


class SequenceMixin(AppBase):
    _DEFAULT_STEP_DELAY_MS = 500

    def _refresh_sequence_list(self, select: int | None = None) -> None:
        listbox = self.sequence_list
        listbox.delete(0, tk.END)
        last = len(self.sequence_steps)
        for number, step in enumerate(self.sequence_steps, start=1):
            delay = step.get("delay_ms", 0)
            after = "then the Interval" if number == last else f"then wait {delay:g} ms"
            listbox.insert(
                tk.END,
                f"{number}. ({step['x']}, {step['y']})  {step['button']} {step['click_type']}, {after}",
            )
        if select is not None and 0 <= select < last:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(select)
            listbox.see(select)

    def _selected_step(self) -> int | None:
        selection = self.sequence_list.curselection()
        return int(selection[0]) if selection else None

    def _sequence_changed(self, select: int | None = None) -> None:
        self._refresh_sequence_list(select)
        self._refresh_target_summary()
        self.settings.set("sequence", [dict(step) for step in self.sequence_steps])

    def add_sequence_point(self) -> None:
        """Pick a point and append it as a step using the current button and click type."""
        if len(self.sequence_steps) >= MAX_SEQUENCE_STEPS:
            self._set_status_message(f"A sequence has at most {MAX_SEQUENCE_STEPS} steps", "alert")
            return
        self.start_coordinate_picker(on_selected=self._on_sequence_point_picked)

    def _on_sequence_point_picked(self, x: int, y: int) -> None:
        self.sequence_steps.append(
            {
                "x": x,
                "y": y,
                "button": self.button_var.get(),
                "click_type": self.click_type_var.get(),
                "delay_ms": self._DEFAULT_STEP_DELAY_MS,
            }
        )
        self._sequence_changed(select=len(self.sequence_steps) - 1)
        self.show_window()
        self._apply_target_mode_state()
        self._set_status_message(f"Added step {len(self.sequence_steps)}", "alert")

    def edit_sequence_delay(self) -> None:
        index = self._selected_step()
        if index is None:
            self._set_status_message("Select a step first", "alert")
            return
        step = self.sequence_steps[index]
        value = dialogs.simpledialog.askfloat(
            "Wait after step",
            f"Milliseconds to wait after step {index + 1} before the next one:",
            initialvalue=step.get("delay_ms", 0),
            minvalue=0,
            maxvalue=MAX_STEP_DELAY_MS,
        )
        if value is None:
            return
        step["delay_ms"] = int(value) if float(value).is_integer() else value
        self._sequence_changed(select=index)

    def move_sequence_step(self, offset: int) -> None:
        index = self._selected_step()
        if index is None:
            return
        target = index + offset
        if not 0 <= target < len(self.sequence_steps):
            return
        steps = self.sequence_steps
        steps[index], steps[target] = steps[target], steps[index]
        self._sequence_changed(select=target)

    def remove_sequence_step(self) -> None:
        index = self._selected_step()
        if index is None:
            return
        del self.sequence_steps[index]
        self._sequence_changed(select=min(index, len(self.sequence_steps) - 1))
