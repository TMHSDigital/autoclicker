# SPDX-License-Identifier: CC-BY-NC-4.0
"""Pick Location: a full-desktop overlay that captures one click.

The overlay is a borderless, topmost, translucent Tk window spanning every
monitor. Because it is a real window, the pick click lands on the overlay and
never reaches the application underneath. All of this runs on the Tk thread.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import pyautogui

from ..core.screen import ScreenBounds, virtual_screen_bounds

_OVERLAY_ALPHA = 0.25
_OVERLAY_BG = "#000000"
_HINT = "Click to pick  ·  Esc or right-click to cancel"
# Readout sits this far from the pointer so it never ends up under the click.
_READOUT_OFFSET = 18


class CoordinatePicker:
    """Interactive coordinate selection via a click-absorbing overlay."""

    def __init__(
        self,
        root: Any,
        *,
        bounds: Callable[[], ScreenBounds] | None = None,
        toplevel_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        self._root = root
        self._bounds = bounds or (lambda: virtual_screen_bounds(pyautogui.size))
        self._make_toplevel = toplevel_factory or tk.Toplevel
        self._overlay: Any = None
        self._readout: Any = None
        self._readout_label: Any = None
        self.on_coordinate_selected: Callable[[int, int], None] | None = None
        self.on_cancelled: Callable[[], None] | None = None

    def is_picking(self) -> bool:
        return self._overlay is not None

    def start_picking(
        self,
        on_selected: Callable[[int, int], None],
        on_cancelled: Callable[[], None] | None = None,
    ) -> bool:
        """Show the overlay. Returns False if already picking or it cannot be shown."""
        if self.is_picking():
            return False
        self.on_coordinate_selected = on_selected
        self.on_cancelled = on_cancelled
        try:
            self._show(self._bounds())
        except Exception:
            self._destroy()
            return False
        return True

    def stop_picking(self, cancelled: bool = True) -> None:
        """Close the overlay; fire on_cancelled when ``cancelled`` is True."""
        if not self.is_picking():
            return
        self._destroy()
        if cancelled and self.on_cancelled:
            self.on_cancelled()

    # -- overlay ---------------------------------------------------------

    def _show(self, bounds: ScreenBounds) -> None:
        overlay = self._make_toplevel(self._root)
        self._overlay = overlay
        overlay.overrideredirect(True)
        overlay.geometry(f"{bounds.width}x{bounds.height}+{bounds.left}+{bounds.top}")
        overlay.configure(bg=_OVERLAY_BG, cursor="crosshair")
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", _OVERLAY_ALPHA)
        overlay.bind("<Button-1>", self._on_click)
        overlay.bind("<Button-3>", self._on_cancel)
        overlay.bind("<Escape>", self._on_cancel)
        overlay.bind("<Motion>", self._on_motion)

        # Opaque readout window so the coordinates stay legible over the dim overlay.
        readout = self._make_toplevel(self._root)
        self._readout = readout
        readout.overrideredirect(True)
        readout.attributes("-topmost", True)
        self._readout_label = tk.Label(
            readout,
            text=_HINT,
            bg="#1f2328",
            fg="#ffffff",
            padx=8,
            pady=4,
            font=("Segoe UI", 10),
            justify=tk.LEFT,
        )
        self._readout_label.pack()
        readout.geometry(f"+{bounds.left + 24}+{bounds.top + 24}")

        overlay.focus_force()

    def _on_motion(self, event: Any) -> None:
        if self._readout is None or self._readout_label is None:
            return
        x, y = int(event.x_root), int(event.y_root)
        self._readout_label.configure(text=f"{x}, {y}\n{_HINT}")
        self._readout.geometry(f"+{x + _READOUT_OFFSET}+{y + _READOUT_OFFSET}")

    def _on_click(self, event: Any) -> None:
        if not self.is_picking():
            return
        x, y = int(event.x_root), int(event.y_root)
        self.stop_picking(cancelled=False)
        if self.on_coordinate_selected:
            self.on_coordinate_selected(x, y)

    def _on_cancel(self, _event: Any = None) -> None:
        self.stop_picking(cancelled=True)

    def _destroy(self) -> None:
        for window in (self._readout, self._overlay):
            if window is not None:
                try:
                    window.destroy()
                except Exception:
                    pass
        self._overlay = None
        self._readout = None
        self._readout_label = None
