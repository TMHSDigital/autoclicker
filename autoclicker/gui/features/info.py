# SPDX-License-Identifier: CC-BY-NC-4.0
"""Info dialog with Copy diagnostics (#88)."""

from __future__ import annotations

import contextlib
import logging
import os

from ... import __version__
from ...core.app_data import app_data_dir
from ...core.diagnostics import build_report
from ..info_dialog import InfoDialog
from .base import AppBase

_log = logging.getLogger(__name__)


class InfoMixin(AppBase):
    def show_info(self) -> None:
        """Info dialog: version, responsible-use note, Copy diagnostics, Sponsor."""
        InfoDialog(
            self.root,
            __version__,
            diagnostics=lambda: build_report(self._settings_for_diagnostics()),
        )

    def open_data_folder(self) -> None:
        """Open the folder with settings, logs and images in Explorer (#180).

        That is the WindowsAutoclicker folder in %APPDATA%, or the portable data folder.
        """
        folder = app_data_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)  # type: ignore[attr-defined, unused-ignore]
        except OSError as e:
            _log.warning("Could not open the data folder: %s", e)
            self._set_status_message(f"Could not open {folder}", "error")

    def _show_info_from_tray(self) -> None:
        self.show_window()
        self.show_info()

    def _settings_for_diagnostics(self) -> dict:
        """Saved settings plus the form's current (possibly unsaved) values."""
        values = dict(self.settings.get_all())
        with contextlib.suppress(Exception):
            values.update(self._collect_ui_settings())
        return values
