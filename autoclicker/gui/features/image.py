# SPDX-License-Identifier: CC-BY-NC-4.0
"""Image target mode: capture a button image and click wherever it appears (#87)."""

from __future__ import annotations

import time

from ...core.app_data import app_data_dir
from ...core.image_match import DEFAULT_MARGIN, grab, search_region
from ...core.screen import ScreenBounds, virtual_screen_bounds
from .base import AppBase


class ImageMixin(AppBase):
    def capture_image(self) -> None:
        """Capture… button: drag a rectangle around the image to click."""
        if self.click_engine.is_running or self._countdown_job is not None:
            self._set_status_message("Stop clicking before capturing", "alert")
            return
        if self.coordinate_picker.is_picking():
            return
        started = self.coordinate_picker.start_selecting_area(
            on_selected=self._on_image_area_selected,
            on_cancelled=self._on_coordinate_picker_cancelled,
        )
        if not started:
            self._set_status_message("Could not start the capture overlay", "error")
            return
        self._set_status_message("Drag a rectangle around the image to click...", "running")
        self.root.withdraw()

    def _on_image_area_selected(self, area: ScreenBounds) -> None:
        # Let the overlay repaint away before grabbing the screen; our window
        # stays hidden until then so it can't end up in the capture.
        self.root.after(200, self._grab_image, area)

    def _grab_image(self, area: ScreenBounds) -> None:
        import pyautogui

        try:
            image = grab(area)
            folder = app_data_dir() / "images"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"target-{time.strftime('%Y%m%d-%H%M%S')}.png"
            image.save(path)
        except Exception as e:
            self.show_window()
            self._set_status_message(f"Could not capture the image: {e}", "error")
            return
        desktop = virtual_screen_bounds(pyautogui.size)
        region = search_region(area, self._image_margin(), desktop)
        self.image_path = str(path)
        self.image_region = [region.left, region.top, region.width, region.height]
        self.settings.update({"image_path": self.image_path, "image_region": self.image_region})
        self.target_mode_var.set("image")
        self.show_window()
        self._apply_target_mode_state()
        self._refresh_image_label()
        self._set_status_message(f"Captured a {area.width}x{area.height} image", "alert")

    def _image_margin(self) -> int:
        try:
            return max(0, int(float(self.image_margin_entry.get())))
        except (TypeError, ValueError):
            return DEFAULT_MARGIN

    def _refresh_image_label(self) -> None:
        if not self.image_path or len(self.image_region) != 4:
            self.image_info_var.set("No image captured yet")
            return
        left, top, width, height = self.image_region
        self.image_info_var.set(f"Searching {width}x{height} px at ({left}, {top})")
