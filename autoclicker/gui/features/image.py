# SPDX-License-Identifier: CC-BY-NC-4.0
"""Image target mode: capture a button image and click wherever it appears (#87)."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from ...core.image_match import grab, images_dir
from ...core.screen import ScreenBounds
from .base import AppBase

# Largest thumbnail of the captured image shown in the Image panel.
_PREVIEW_SIZE = (96, 40)


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
            on_cancelled=self._on_image_capture_cancelled,
        )
        if not started:
            self._set_status_message("Could not start the capture overlay", "error")
            return
        self._set_status_message("Drag a rectangle around the image to click...", "running")
        self.root.withdraw()

    def _on_image_capture_cancelled(self) -> None:
        self.show_window()
        self._apply_target_mode_state()
        self._set_status_message(
            "Capture cancelled: drag a rectangle at least 4 px each way around the image", "alert"
        )

    def _on_image_area_selected(self, area: ScreenBounds) -> None:
        # Let the overlay repaint away before grabbing the screen; our window
        # stays hidden until then so it can't end up in the capture.
        self.root.after(200, self._grab_image, area)

    def _grab_image(self, area: ScreenBounds) -> None:
        try:
            image = grab(area)
            folder = images_dir()
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"target-{time.strftime('%Y%m%d-%H%M%S')}.png"
            image.save(path)
        except Exception as e:
            self.show_window()
            self._set_status_message(f"Could not capture the image: {e}", "error")
            return
        self._forget_image(self.image_path)
        self.image_path = str(path)
        # Where it was captured; the search area adds the margin at Start (#100).
        self.image_region = [area.left, area.top, area.width, area.height]
        self.settings.update({"image_path": self.image_path, "image_region": self.image_region})
        self.target_mode_var.set("image")
        self.show_window()
        self._apply_target_mode_state()
        self._refresh_image_label()
        self._set_status_message(f"Captured a {area.width}x{area.height} image", "alert")

    def _forget_image(self, path: str) -> None:
        """Delete a replaced capture unless a profile still uses it (#100)."""
        if not path:
            return
        old = Path(path)
        try:
            if old.parent.resolve() != images_dir().resolve() or not old.name.startswith("target-"):
                return  # only our own captures; imported images are shared by content
        except OSError:
            return
        for name in self.preset_manager.get_preset_names():
            profile = self.preset_manager.load_profile(name) or {}
            if profile.get("image_path") == path:
                return
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass

    def clear_image(self) -> None:
        """Clear button: forget the armed image (and delete it unless a profile uses it)."""
        if self.click_engine.is_running or self._countdown_job is not None:
            return
        self._forget_image(self.image_path)
        self.image_path, self.image_region = "", []
        self.settings.update({"image_path": "", "image_region": []})
        self._refresh_image_label()
        self._refresh_target_summary()

    def _refresh_image_label(self) -> None:
        self._show_image_preview()
        if not self.image_path or len(self.image_region) != 4:
            self.image_info_var.set("No image captured yet")
            return
        left, top, width, height = self.image_region
        self.image_info_var.set(f"Captured {width}x{height} px at ({left}, {top})")

    def _show_image_preview(self) -> None:
        """Small thumbnail of the armed image next to Capture (#123)."""
        preview = getattr(self, "image_preview", None)
        if preview is None:
            return
        photo = None
        if self.image_path:
            try:
                from PIL import ImageTk

                with Image.open(self.image_path) as image:
                    thumb = image.convert("RGB")
                thumb.thumbnail(_PREVIEW_SIZE)
                photo = ImageTk.PhotoImage(thumb, master=self.root)
            except Exception:  # missing file, no Tk (tests): just no thumbnail
                photo = None
        try:
            preview.configure(image=photo if photo is not None else "")
        except Exception:
            return
        self._image_photo = photo  # Tk only borrows the image; keep it alive
