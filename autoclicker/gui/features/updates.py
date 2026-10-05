# SPDX-License-Identifier: CC-BY-NC-4.0
"""Opt-in daily update check (#79)."""

from __future__ import annotations

import threading
import time
import webbrowser

from ... import __version__
from ...core.updates import RELEASES_PAGE, Release, check_due, fetch_latest_release, is_newer
from .. import dialogs
from .base import AppBase

# How long to wait before asking again when a run or countdown is in progress.
_RETRY_MS = 60_000


class UpdatesMixin(AppBase):
    def _maybe_check_for_updates(self) -> None:
        """Ask once whether to check, then check at most daily, never while clicking."""
        if self.click_engine.is_running or self._countdown_job is not None:
            # No dialog on top of a run or a countdown (e.g. --start); try again later.
            self.root.after(_RETRY_MS, self._maybe_check_for_updates)
            return
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
        if choice is not True:
            return
        if not check_due(self.settings.get("last_update_check")):
            return
        threading.Thread(target=self._check_for_updates, daemon=True, name="UpdateCheck").start()

    def _check_for_updates(self) -> None:
        """(Worker thread) look for a newer release and report it on the Tk thread.

        Only a successful check counts toward the daily limit, so starting
        offline doesn't skip a day (#103).
        """
        release = fetch_latest_release()
        if release is None:
            return
        self._ui(self.settings.set, "last_update_check", time.time())
        if is_newer(release.version, __version__):
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
