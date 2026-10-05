# SPDX-License-Identifier: CC-BY-NC-4.0
"""Info dialog with Copy diagnostics (#88)."""

from __future__ import annotations

from ... import __version__
from ...core.diagnostics import build_report
from ..info_dialog import InfoDialog
from .base import AppBase


class InfoMixin(AppBase):
    def show_info(self) -> None:
        """Info dialog: version, responsible-use note, Copy diagnostics, Sponsor."""
        InfoDialog(
            self.root,
            __version__,
            diagnostics=lambda: build_report(self._settings_for_diagnostics()),
        )

    def _show_info_from_tray(self) -> None:
        self.show_window()
        self.show_info()

    def _settings_for_diagnostics(self) -> dict:
        """Saved settings plus the form's current (possibly unsaved) values."""
        values = dict(self.settings.get_all())
        try:
            values.update(self._collect_ui_settings())
        except Exception:
            pass
        return values
