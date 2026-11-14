# SPDX-License-Identifier: CC-BY-NC-4.0
"""Adding and editing the step types of a sequence: hold, key and waits (#119).

Each step is built with the tools the app already has (the point picker, the
area capture and a pixel read) plus a short prompt, then checked with the
same parser that validates the saved sequence.
"""

from __future__ import annotations

import functools
import time
import tkinter as tk
import uuid
from collections.abc import Callable
from typing import Any

from ...core.image_match import grab, images_dir
from ...core.screen import ScreenBounds
from ...core.settings_manager import (
    MAX_HOLD_MS,
    MAX_SEQUENCE_STEPS,
    MAX_STEP_TIMEOUT_MS,
)
from .. import dialogs
from .base import AppBase

_ADD_ITEMS = (
    ("Click point…", "click"),
    ("Hold…", "hold"),
    ("Key…", "key"),
    ("Wait for image…", "wait_image"),
    ("Wait for pixel…", "wait_pixel"),
)
_BUTTONS = (("Left", "left"), ("Right", "right"), ("Middle", "middle"))
_ON_TIMEOUT = (
    ("If it times out: stop the run", "stop"),
    ("If it times out: go to the next step", "skip"),
)
# The overlay is gone but the screen may not have repainted yet (as for the
# image target and the pixel condition).
_REPAINT_MS = 200
_KEY_PROMPT = "Key or combination to press, such as F5, enter or ctrl+s:"


def _number(value: float) -> int | float:
    """Whole numbers stored as int, as the form stores what was typed."""
    return int(value) if float(value).is_integer() else value


class StepsMixin(AppBase):
    _DEFAULT_WAIT_AFTER_MS = 500

    # -- adding --------------------------------------------------------------

    def show_add_step_menu(self, event=None) -> None:
        """Add… button: choose the type of step to add."""
        if self._sequence_full():
            return
        menu = self._add_step_menu()
        button = self.add_step_button
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _add_step_menu(self) -> tk.Menu:
        menu = tk.Menu(self.sequence_list, tearoff=0)
        for label, kind in _ADD_ITEMS:
            menu.add_command(label=label, command=functools.partial(self.add_step, kind))
        return menu

    def add_step(self, kind: str) -> None:
        """Start adding a step of ``kind``; it is appended once its pick or prompt is done."""
        if self._sequence_full():
            return
        if kind == "click":
            self.add_sequence_point()
        elif kind == "hold":
            self.start_coordinate_picker(on_selected=self._on_hold_point_picked)
        elif kind == "key":
            key = self._ask_key()
            if key is not None:
                self._append_step({"type": "key", "key": key})
        elif kind == "wait_image":
            self._capture_step_image(
                lambda path, region: self._append_step(
                    {"type": "wait_image", "image_path": path, "image_region": region}
                )
            )
        elif kind == "wait_pixel":
            self._sample_step_pixel(
                lambda x, y, color: self._append_step(
                    {"type": "wait_pixel", "x": x, "y": y, "color": color}
                )
            )

    def _sequence_full(self) -> bool:
        if len(self.sequence_steps) < MAX_SEQUENCE_STEPS:
            return False
        self._set_status_message(f"A sequence has at most {MAX_SEQUENCE_STEPS} steps", "alert")
        return True

    def _on_hold_point_picked(self, x: int, y: int) -> None:
        self._back_from_overlay()
        ms = dialogs.simpledialog.askfloat(
            "Hold",
            "Milliseconds to hold the button down:",
            initialvalue=500,
            minvalue=1,
            maxvalue=MAX_HOLD_MS,
        )
        if ms is None:
            return
        self._append_step(
            {
                "type": "hold",
                "x": x,
                "y": y,
                "button": self.button_var.get(),
                "hold_ms": _number(ms),
            }
        )

    def _append_step(self, fields: dict[str, Any]) -> None:
        """Check a new step like a saved one, then add it at the end of the list."""
        step = self._checked_step({**fields, "delay_ms": self._DEFAULT_WAIT_AFTER_MS})
        if step is None:
            return
        self.sequence_steps.append(step)
        self._sequence_changed(select=len(self.sequence_steps) - 1)
        self._apply_target_mode_state()
        self._set_status_message(f"Added step {len(self.sequence_steps)}", "alert")

    def _checked_step(self, step: dict[str, Any]) -> dict[str, Any] | None:
        """The step as the settings will store it, or None after showing why it can't be."""
        parsed, error = self.settings.parse_input("sequence", [step])
        if error is not None:
            # The parser numbers the steps of the list it was given: always 1 here.
            self._set_status_message(error.replace("Step 1 ", "", 1), "error")
            return None
        return dict(parsed[0])

    # -- pickers and prompts ---------------------------------------------------

    def _back_from_overlay(self) -> None:
        self.show_window()
        self._apply_target_mode_state()

    def _ask_key(self, current: str = "") -> str | None:
        """Ask for a key until it is one that can be pressed, or None if cancelled."""
        text = current
        while True:
            answer = dialogs.simpledialog.askstring("Key", _KEY_PROMPT, initialvalue=text)
            if answer is None:
                return None
            text = answer
            parsed, error = self.settings.parse_input("sequence", [{"type": "key", "key": text}])
            if error is None:
                return str(parsed[0]["key"])
            dialogs.messagebox.showerror("Key", error.split(": ", 1)[-1])

    def _capture_step_image(self, on_captured: Callable[[str, list[int]], None]) -> None:
        """Drag a rectangle; ``on_captured(path, region)`` once the capture is saved."""
        if self.click_engine.is_running or self._countdown_job is not None:
            self._set_status_message("Stop clicking before capturing", "alert")
            return
        if self.coordinate_picker.is_picking():
            return
        started = self.coordinate_picker.start_selecting_area(
            on_selected=lambda area: self.root.after(
                _REPAINT_MS, self._grab_step_image, area, on_captured
            ),
            on_cancelled=self._on_step_capture_cancelled,
        )
        if not started:
            self._set_status_message("Could not start the capture overlay", "error")
            return
        self._set_status_message("Drag a rectangle around the image to wait for...", "running")
        self.root.withdraw()

    def _on_step_capture_cancelled(self) -> None:
        self._back_from_overlay()
        self._set_status_message(
            "Capture cancelled: drag a rectangle at least 4 px each way around the image", "alert"
        )

    def _grab_step_image(
        self, area: ScreenBounds, on_captured: Callable[[str, list[int]], None]
    ) -> None:
        try:
            image = grab(area)
            folder = images_dir()
            folder.mkdir(parents=True, exist_ok=True)
            # "step-" captures are never deleted with the image target's ("target-").
            name = f"step-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.png"
            path = folder / name
            image.save(path)
        except Exception as e:
            self._back_from_overlay()
            self._set_status_message(f"Could not capture the image: {e}", "error")
            return
        self._back_from_overlay()
        on_captured(str(path), [area.left, area.top, area.width, area.height])

    def _sample_step_pixel(self, on_sampled: Callable[[int, int, str], None]) -> None:
        """Pick a point; ``on_sampled(x, y, color)`` with its color once the overlay is gone."""
        self.start_coordinate_picker(
            on_selected=lambda x, y: self.root.after(
                _REPAINT_MS, self._read_step_pixel, x, y, on_sampled
            )
        )

    def _read_step_pixel(self, x: int, y: int, on_sampled: Callable[[int, int, str], None]) -> None:
        import pyautogui

        try:
            r, g, b = tuple(pyautogui.pixel(x, y))[:3]
        except Exception as e:
            self._back_from_overlay()
            self._set_status_message(f"Could not read that pixel: {e}", "error")
            return
        self._back_from_overlay()
        on_sampled(x, y, f"#{int(r):02x}{int(g):02x}{int(b):02x}")

    # -- editing ---------------------------------------------------------------

    def _add_step_type_edits(self, menu: tk.Menu, index: int) -> None:
        """The step menu's entries for what only this step's type has."""
        step = self.sequence_steps[index]
        kind = step.get("type", "click")
        if kind == "hold":
            menu.add_command(label="Hold time…", command=lambda: self.edit_hold_time(index))
        elif kind == "key":
            menu.add_command(label="Key…", command=lambda: self.edit_step_key(index))
        elif kind == "wait_image":
            menu.add_command(
                label="Capture the image again…", command=lambda: self.recapture_step_image(index)
            )
            menu.add_checkbutton(
                label="Click the image when it appears",
                variable=tk.BooleanVar(menu, value=bool(step.get("click"))),
                command=lambda: self.toggle_step_click(index),
            )
            if step.get("click"):
                for label, value in _BUTTONS:
                    menu.add_radiobutton(
                        label=f"{label} button",
                        value=value,
                        variable=tk.StringVar(menu, value=step.get("button", "left")),
                        command=functools.partial(self.set_sequence_step, index, button=value),
                    )
        elif kind == "wait_pixel":
            menu.add_command(
                label="Pick the pixel again…", command=lambda: self.repick_step_pixel(index)
            )
            menu.add_command(
                label=f"Color tolerance ({step.get('tolerance', 16)})…",
                command=lambda: self.edit_step_tolerance(index),
            )
        if kind in ("wait_image", "wait_pixel"):
            menu.add_separator()
            seconds = float(step.get("timeout_ms", 0) or 0) / 1000
            shown = f"{seconds:g} s" if seconds else "none"
            menu.add_command(
                label=f"Timeout ({shown})…", command=lambda: self.edit_step_timeout(index)
            )
            for label, value in _ON_TIMEOUT:
                menu.add_radiobutton(
                    label=label,
                    value=value,
                    variable=tk.StringVar(menu, value=step.get("on_timeout", "stop")),
                    command=functools.partial(self.set_sequence_step, index, on_timeout=value),
                )
        if kind != "click":
            menu.add_separator()

    def _replace_step(
        self, index: int, changes: dict[str, Any], drop: tuple[str, ...] = ()
    ) -> None:
        """Apply changes to one step if the result is a valid step."""
        if not 0 <= index < len(self.sequence_steps):
            return
        new = {k: v for k, v in self.sequence_steps[index].items() if k not in drop}
        step = self._checked_step({**new, **changes})
        if step is None:
            return
        self.sequence_steps[index] = step
        self._sequence_changed(select=index)

    def edit_hold_time(self, index: int) -> None:
        ms = dialogs.simpledialog.askfloat(
            "Hold",
            f"Milliseconds to hold the button down in step {index + 1}:",
            initialvalue=self.sequence_steps[index].get("hold_ms", 500),
            minvalue=1,
            maxvalue=MAX_HOLD_MS,
        )
        if ms is not None:
            self._replace_step(index, {"hold_ms": _number(ms)})

    def edit_step_key(self, index: int) -> None:
        key = self._ask_key(str(self.sequence_steps[index].get("key", "")))
        if key is not None:
            self._replace_step(index, {"key": key})

    def edit_step_timeout(self, index: int) -> None:
        current = float(self.sequence_steps[index].get("timeout_ms", 0) or 0) / 1000
        seconds = dialogs.simpledialog.askfloat(
            "Timeout",
            f"Seconds step {index + 1} waits before giving up (0 = until stopped):",
            initialvalue=_number(current),
            minvalue=0,
            maxvalue=MAX_STEP_TIMEOUT_MS / 1000,
        )
        if seconds is not None:
            self._replace_step(index, {"timeout_ms": _number(round(seconds * 1000, 3))})

    def edit_step_tolerance(self, index: int) -> None:
        tolerance = dialogs.simpledialog.askinteger(
            "Color tolerance",
            "How far each of red, green and blue may differ (0 = exact, up to 255):",
            initialvalue=self.sequence_steps[index].get("tolerance", 16),
            minvalue=0,
            maxvalue=255,
        )
        if tolerance is not None:
            self._replace_step(index, {"tolerance": tolerance})

    def toggle_step_click(self, index: int) -> None:
        """Turn clicking the found image on or off for a wait_image step."""
        if self.sequence_steps[index].get("click"):
            self._replace_step(index, {"click": False}, drop=("button", "click_type"))
        else:
            self._replace_step(index, {"click": True, "button": self.button_var.get()})

    def recapture_step_image(self, index: int) -> None:
        self._capture_step_image(
            lambda path, region: self._replace_step(
                index, {"image_path": path, "image_region": region}
            )
        )

    def repick_step_pixel(self, index: int) -> None:
        self._sample_step_pixel(
            lambda x, y, color: self._replace_step(index, {"x": x, "y": y, "color": color})
        )
