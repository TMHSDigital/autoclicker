# SPDX-License-Identifier: CC-BY-NC-4.0
"""System tray integration."""

from __future__ import annotations

from typing import Callable

import pystray
from PIL import Image


def create_tray_icon(
    show_window: Callable[[], None],
    start: Callable[[], None],
    stop: Callable[[], None],
    quit_app: Callable[[], None],
    on_error: Callable[[str], None],
) -> pystray.Icon | None:
    """Create the system tray icon and menu, or None on failure."""
    try:
        icon_image = Image.new("RGB", (64, 64), color="red")
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
