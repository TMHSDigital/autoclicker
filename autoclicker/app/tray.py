# SPDX-License-Identifier: CC-BY-NC-4.0
"""System tray integration."""

from __future__ import annotations

from collections.abc import Callable

import pystray
from PIL import Image

from ..core.resources import resource_path


def _load_tray_image() -> Image.Image:
    """Load the app icon for the tray, falling back to a solid square."""
    for candidate in ("autoclicker.png", "autoclicker.ico"):
        path = resource_path(candidate)
        if path.is_file():
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                continue
    return Image.new("RGB", (64, 64), color="red")


def _profile_items(
    profile_names: Callable[[], list[str]] | None,
    load_profile: Callable[[str], None] | None,
    can_switch: Callable[[], bool],
) -> list[pystray.MenuItem]:
    """One item per saved profile, or a disabled placeholder when there are none."""
    names = sorted(profile_names(), key=str.lower) if profile_names is not None else []
    if not names or load_profile is None:
        return [pystray.MenuItem("No saved profiles", None, enabled=False)]

    def item(name: str) -> pystray.MenuItem:
        return pystray.MenuItem(
            name,
            lambda _icon, _item: load_profile(name),
            enabled=lambda _item: can_switch(),
        )

    return [item(name) for name in names]


def create_tray_icon(
    show_window: Callable[[], None],
    start: Callable[[], None],
    stop: Callable[[], None],
    quit_app: Callable[[], None],
    on_error: Callable[[str], None],
    start_label: Callable[[], str] = lambda: "Start",
    stop_label: Callable[[], str] = lambda: "Stop",
    show_info: Callable[[], None] | None = None,
    profile_names: Callable[[], list[str]] | None = None,
    load_profile: Callable[[str], None] | None = None,
    can_switch_profile: Callable[[], bool] = lambda: True,
) -> pystray.Icon | None:
    """Create the system tray icon and menu, or None on failure.

    Start/Stop labels are callables so they follow hotkey changes
    (call ``icon.update_menu()`` after rebinding). With ``profile_names`` and
    ``load_profile`` a Profiles submenu lists the saved profiles (#178); its
    items are greyed out while ``can_switch_profile()`` is False. Call
    ``update_menu()`` after profiles or the run state change.
    """
    try:
        icon_image = _load_tray_image()
        return pystray.Icon(
            "autoclicker",
            icon_image,
            "Windows Autoclicker",
            menu=pystray.Menu(
                # default=True: double-clicking the tray icon restores the window
                pystray.MenuItem("Show", show_window, default=True),
                pystray.MenuItem(lambda _item: start_label(), start),
                pystray.MenuItem(lambda _item: stop_label(), stop),
                pystray.MenuItem(
                    "Profiles",
                    pystray.Menu(
                        lambda: _profile_items(profile_names, load_profile, can_switch_profile)
                    ),
                    visible=profile_names is not None and load_profile is not None,
                ),
                pystray.MenuItem("About and diagnostics", show_info, visible=show_info is not None),
                pystray.MenuItem("Exit", quit_app),
            ),
        )
    except Exception as e:
        on_error(f"System tray setup failed: {e}")
        return None
