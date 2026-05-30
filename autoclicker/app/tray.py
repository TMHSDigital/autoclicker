# SPDX-License-Identifier: CC-BY-NC-4.0
"""System tray integration."""

from __future__ import annotations

import os
from collections.abc import Callable

import pystray
from PIL import Image


def _load_tray_image() -> Image.Image:
    """Load the app icon for the tray, falling back to a solid square."""
    for candidate in ("autoclicker.png", "autoclicker.ico"):
        if os.path.exists(candidate):
            try:
                return Image.open(candidate).convert("RGBA")
            except Exception:
                continue
    return Image.new("RGB", (64, 64), color="red")


def create_tray_icon(
    show_window: Callable[[], None],
    start: Callable[[], None],
    stop: Callable[[], None],
    quit_app: Callable[[], None],
    on_error: Callable[[str], None],
) -> pystray.Icon | None:
    """Create the system tray icon and menu, or None on failure."""
    try:
        icon_image = _load_tray_image()
        return pystray.Icon(
            "autoclicker",
            icon_image,
            "Windows Autoclicker",
            menu=pystray.Menu(
                pystray.MenuItem("Show", show_window),
                pystray.MenuItem("Start (F6)", start),
                pystray.MenuItem("Stop (F7)", stop),
                pystray.MenuItem("Exit", quit_app),
            ),
        )
    except Exception as e:
        on_error(f"System tray setup failed: {e}")
        return None
