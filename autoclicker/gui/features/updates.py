# SPDX-License-Identifier: CC-BY-NC-4.0
"""Opt-in daily update check (#79)."""

from __future__ import annotations

import threading
import time
import webbrowser

from ... import __version__
from ...core.updates import RELEASES_PAGE, Release, check_due, newer_release
from .. import dialogs
from .base import AppBase


class UpdatesMixin(AppBase):
    def _maybe_check_for_updates(self) -> None:
        """Ask once whether to check, then check at most daily, never while clicking."""
        choice = self.settings.get("check_for_updates")
        if choice is None:
            choice = bool(
                dialogs.messagebox.askyesno(
                    "Check for updates",
                    "Check GitHub once a day for new versions of Windows Autoclicker?\n\n"
                    "Only the public release page is contacted, and nothing is downloaded. "
                    "You can change this under App.",
                )
            )
            self.settings.set("check_for_updates", choice)
            self.check_updates_var.set(choice)
        if choice is not True or self.click_engine.is_running:
            return
        if not check_due(self.settings.get("last_update_check")):
            return
        self.settings.set("last_update_check", time.time())
        threading.Thread(target=self._check_for_updates, daemon=True, name="UpdateCheck").start()

    def _check_for_updates(self) -> None:
        """(Worker thread) look for a newer release and report it on the Tk thread."""
        release = newer_release(__version__)
        if release is not None:
            self._ui(self._show_update, release)

    def _show_update(self, release: Release) -> None:
        self._release_url = release.url
        self.update_button.configure(text=f"Update to {release.version}")
        self.update_button.grid()
        if self.tray_icon is not None:
            try:
                self.tray_icon.notify(
                    f"Version {release.version} is available.", "Windows Autoclicker"
                )
            except Exception:
                pass

    def open_release_page(self) -> None:
        webbrowser.open(self._release_url or RELEASES_PAGE)

    def _on_check_updates_toggle(self) -> None:
        self.settings.set("check_for_updates", bool(self.check_updates_var.get()))
