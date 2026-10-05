# SPDX-License-Identifier: CC-BY-NC-4.0
"""Only click while a watched pixel matches a color (#80)."""

from __future__ import annotations

from .base import AppBase


class ConditionMixin(AppBase):
    _CONDITION_TEXT = {
        "none": "off",
        "wait": "wait until ({x}, {y}) is",
        "stop": "stop when ({x}, {y}) isn't",
    }

    def _refresh_condition_label(self) -> None:
        x, y, color = self.condition_point
        template = self._CONDITION_TEXT.get(self.condition_var.get(), "off")
        self.condition_label_var.set(template.format(x=x, y=y))
        try:
            self.condition_swatch.configure(background=color)
        except Exception:
            pass

    def sample_condition_pixel(self) -> None:
        """Pick a point, then read its color once the overlay is gone."""
        self.start_coordinate_picker(on_selected=self._on_condition_point_picked)

    def _on_condition_point_picked(self, x: int, y: int) -> None:
        # The overlay was just destroyed; give the screen a moment to repaint
        # before reading the pixel, and keep our window hidden until then.
        self.root.after(200, self._read_condition_pixel, x, y)

    def _read_condition_pixel(self, x: int, y: int) -> None:
        import pyautogui

        try:
            r, g, b = tuple(pyautogui.pixel(x, y))[:3]
        except Exception as e:
            self.show_window()
            self._apply_target_mode_state()
            self._set_status_message(f"Could not read that pixel: {e}", "error")
            return
        color = f"#{int(r):02x}{int(g):02x}{int(b):02x}"
        self.condition_point = (x, y, color)
        if self.condition_var.get() == "none":
            self.condition_var.set("wait")
        self._refresh_condition_label()
        self.settings.update({"condition_x": x, "condition_y": y, "condition_color": color})
        self.show_window()
        self._apply_target_mode_state()
        self._set_status_message(f"Watching ({x}, {y}) for {color}", "alert")
