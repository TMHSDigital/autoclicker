# SPDX-License-Identifier: CC-BY-NC-4.0
"""Start-button and tray countdown before clicking (#74)."""

from __future__ import annotations

import tkinter as tk

from .base import AppBase


class CountdownMixin(AppBase):
    def start_from_button(self) -> None:
        """Start button and tray menu: count down first, then start.

        The countdown gives the user time to let go of the mouse and bring the
        target window to the front. Input is validated before it begins.
        """
        if self.click_engine.is_running or self._countdown_job is not None:
            return
        blocked = self._start_blocked_reason()
        if blocked:
            self._set_status_message(blocked, "alert")
            return
        errors = self.controller.validation_errors(self._collect_ui_settings())
        if errors:
            self._show_validation_errors(errors)
            return
        delay = int(float(self.start_delay_entry.get()))
        if delay <= 0:
            self.start_clicking()
            return
        if not self._confirm_guard_off():
            return
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._hotkeys.set_running(True)  # Stop, Emergency and Toggle keys cancel it
        self._countdown_tick(delay)

    def _countdown_tick(self, remaining: int) -> None:
        if remaining > 0:
            self._set_status_message(f"Starting in {remaining}...", "alert")
            self._countdown_job = self.root.after(1000, self._countdown_tick, remaining - 1)
            return
        self._countdown_job = None
        self.start_clicking(confirmed=True)
        if not self.click_engine.is_running:
            # Input changed during the countdown and failed, or the engine was busy
            self._paint_stopped("Not started", "alert")

    def _cancel_countdown(self, message: str | None = "Start cancelled") -> bool:
        """Cancel a pending countdown. Returns True if one was running."""
        job = self._countdown_job
        if job is None:
            return False
        self._countdown_job = None
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
        if message is not None:
            self._paint_stopped(message, "alert")
        return True
