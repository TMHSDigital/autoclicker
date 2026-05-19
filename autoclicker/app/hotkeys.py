# SPDX-License-Identifier: CC-BY-NC-4.0
"""Global keyboard hotkey registration."""

from __future__ import annotations

from typing import Callable

import keyboard


def setup_hotkeys(
    start: Callable[[], None],
    stop: Callable[[], None],
    emergency: Callable[[], None],
    on_error: Callable[[str], None],
) -> None:
    """Register F6/F7/ESC hotkeys; report failures via on_error."""
    try:
        keyboard.add_hotkey("f6", start)
        keyboard.add_hotkey("f7", stop)
        keyboard.add_hotkey("esc", emergency)
    except Exception as e:
        on_error(f"Hotkey setup failed: {e}")
