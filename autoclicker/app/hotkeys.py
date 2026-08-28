# SPDX-License-Identifier: CC-BY-NC-4.0
"""Global keyboard hotkey registration."""

from __future__ import annotations

from collections.abc import Callable

import keyboard


class HotkeyHandle:
    """Registered hotkeys that can be removed on shutdown."""

    def __init__(self) -> None:
        self._keys: list[str] = []

    def add(self, key: str, callback: Callable[[], None]) -> None:
        keyboard.add_hotkey(key, callback)
        self._keys.append(key)

    def unregister(self) -> None:
        for key in self._keys:
            try:
                keyboard.remove_hotkey(key)
            except Exception:
                pass
        self._keys.clear()


def setup_hotkeys(
    start: Callable[[], None],
    stop: Callable[[], None],
    emergency: Callable[[], None],
    on_error: Callable[[str], None],
) -> HotkeyHandle:
    """Register F6/F7/ESC hotkeys; unwind on partial failure."""
    handle = HotkeyHandle()
    try:
        handle.add("f6", start)
        handle.add("f7", stop)
        handle.add("esc", emergency)
    except Exception as e:
        handle.unregister()
        on_error(f"Hotkey setup failed: {e}")
    return handle
