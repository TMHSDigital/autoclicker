# SPDX-License-Identifier: CC-BY-NC-4.0
"""Sequence target mode: the step list and its editing (#72, #175)."""

from __future__ import annotations

import functools
import tkinter as tk
from typing import Any

from ...core.settings_manager import MAX_SEQUENCE_STEPS, MAX_STEP_DELAY_MS
from .. import dialogs
from .base import AppBase

_BUTTONS = (("Left", "left"), ("Right", "right"), ("Middle", "middle"))
_CLICK_TYPES = (("Single", "single"), ("Double", "double"))


def describe_step(step: dict) -> str:
    """What one step does, for the step list (#119)."""
    kind = step.get("type", "click")
    if kind == "key":
        return f"key {step.get('key', '')}"
    if kind in ("wait_image", "wait_pixel"):
        # The timeout is left to the step's Edit dialog: the list is narrow.
        if kind == "wait_pixel":
            return f"wait for pixel ({step.get('x')}, {step.get('y')})"
        return "wait for image, click it" if step.get("click") else "wait for image"
    where = f"({step['x']}, {step['y']})"
    if kind == "hold":
        return f"{where}  {step['button']} hold {_duration(float(step.get('hold_ms', 0)))}"
    return f"{where}  {step['button']} {step['click_type']}"


def _duration(ms: float) -> str:
    return f"{ms:g} ms" if ms < 1000 else f"{ms / 1000:g} s"


class SequenceMixin(AppBase):
    _DEFAULT_STEP_DELAY_MS = 500
    # One level of undo for Remove and Record (#175): (steps before, what changed).
    _sequence_undo: tuple[list[dict], str] | None = None

    def _refresh_sequence_list(self, select: int | None = None) -> None:
        listbox = self.sequence_list
        listbox.delete(0, tk.END)
        last = len(self.sequence_steps)
        for number, step in enumerate(self.sequence_steps, start=1):
            delay = step.get("delay_ms", 0)
            text = f"{number}. {describe_step(step)}"
            if number == last:
                text += ", then the Interval"
            elif delay:
                text += f", wait {_duration(float(delay))}"
            listbox.insert(tk.END, text)
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
        self._remember_for_undo(f"Removed step {index + 1}")
        del self.sequence_steps[index]
        self._sequence_changed(select=min(index, len(self.sequence_steps) - 1))
        self._set_status_message(f"Removed step {index + 1} (Ctrl+Z or Undo restores it)", "alert")

    # -- undo (#175) ---------------------------------------------------------

    def _remember_for_undo(self, what: str) -> None:
        """Keep the steps as they are now, so the next change can be undone once."""
        self._sequence_undo = ([dict(step) for step in self.sequence_steps], what)

    def undo_sequence_change(self) -> None:
        """Put back the steps from before the last Remove or Record."""
        if self._sequence_undo is None:
            self._set_status_message("Nothing to undo", "alert")
            return
        steps, what = self._sequence_undo
        self._sequence_undo = None
        self.sequence_steps = steps
        self._sequence_changed(select=0 if steps else None)
        self._set_status_message(f"Undone: {what.lower()}", "alert")

    # -- editing a step in place (#175) --------------------------------------

    def _step_or_hint(self) -> int | None:
        index = self._selected_step()
        if index is None:
            self._set_status_message("Select a step first", "alert")
        return index

    def show_sequence_step_menu(self, event=None) -> None:
        """Edit menu for the selected step: re-pick, button, click type, wait, duplicate."""
        if event is not None and getattr(event, "y", None) is not None:
            # Right-click or double-click selects the step under the pointer.
            index = self.sequence_list.nearest(event.y)
            if 0 <= index < len(self.sequence_steps):
                self.sequence_list.selection_clear(0, tk.END)
                self.sequence_list.selection_set(index)
        index = self._step_or_hint()
        if index is None:
            return
        menu = self._sequence_step_menu(index)
        x = event.x_root if event is not None else self.sequence_list.winfo_rootx()
        y = event.y_root if event is not None else self.sequence_list.winfo_rooty()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _sequence_step_menu(self, index: int) -> tk.Menu:
        step = self.sequence_steps[index]
        kind = step.get("type", "click")
        menu = tk.Menu(self.sequence_list, tearoff=0)
        if kind in ("click", "hold"):  # key and wait steps have no point to click
            menu.add_command(
                label="Re-pick point…", command=lambda: self.repick_sequence_point(index)
            )
            menu.add_separator()
            for label, value in _BUTTONS:
                menu.add_radiobutton(
                    label=f"{label} button",
                    value=value,
                    variable=tk.StringVar(menu, value=step["button"]),
                    command=functools.partial(self.set_sequence_step, index, button=value),
                )
            menu.add_separator()
        if kind == "click":
            for label, value in _CLICK_TYPES:
                menu.add_radiobutton(
                    label=f"{label} click",
                    value=value,
                    variable=tk.StringVar(menu, value=step["click_type"]),
                    command=functools.partial(self.set_sequence_step, index, click_type=value),
                )
            menu.add_separator()
        self._add_step_type_edits(menu, index)
        menu.add_command(label="Wait after this step…", command=self.edit_sequence_delay)
        menu.add_command(label="Duplicate", command=lambda: self.duplicate_sequence_step(index))
        return menu

    def set_sequence_step(self, index: int, **changes: Any) -> None:
        """Change one step's settings that need no check (button, click type, on timeout)."""
        if not 0 <= index < len(self.sequence_steps):
            return
        self.sequence_steps[index].update(changes)
        self._sequence_changed(select=index)

    def repick_sequence_point(self, index: int) -> None:
        """Pick a new point for an existing step, keeping its other settings."""

        def picked(x: int, y: int) -> None:
            if 0 <= index < len(self.sequence_steps):
                self.sequence_steps[index].update(x=x, y=y)
                self._sequence_changed(select=index)
                self._set_status_message(f"Moved step {index + 1} to ({x}, {y})", "alert")
            self.show_window()

        self.start_coordinate_picker(on_selected=picked)

    def duplicate_sequence_step(self, index: int) -> None:
        """Insert a copy of a step right after it."""
        if len(self.sequence_steps) >= MAX_SEQUENCE_STEPS:
            self._set_status_message(f"A sequence has at most {MAX_SEQUENCE_STEPS} steps", "alert")
            return
        if not 0 <= index < len(self.sequence_steps):
            return
        self.sequence_steps.insert(index + 1, dict(self.sequence_steps[index]))
        self._sequence_changed(select=index + 1)

    def _on_sequence_key(self, action: str) -> str:
        """Keyboard shortcuts on the step list; "break" keeps Tk from also handling them."""
        if action == "delete":
            self.remove_sequence_step()
        elif action == "up":
            self.move_sequence_step(-1)
        elif action == "down":
            self.move_sequence_step(1)
        elif action == "undo":
            self.undo_sequence_change()
        return "break"
