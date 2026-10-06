# SPDX-License-Identifier: CC-BY-NC-4.0
"""Start-button and tray countdown before clicking (#74)."""

from __future__ import annotations

import math
import tkinter as tk
from datetime import datetime

from ...core.schedule import describe_wait, next_start, parse_start_at
from .base import AppBase

# A scheduled start claims the global Stop and Emergency keys only this close to it.
_CLAIM_STOP_KEYS_SECONDS = 60


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
        start_at = parse_start_at(self.start_at_entry.get())
        if start_at is not None:
            # Follows the wall clock, so sleep or a long wait can't make it late.
            self._countdown_until = next_start(*start_at, datetime.now())
            delay = math.ceil((self._countdown_until - datetime.now()).total_seconds())
        else:
            self._countdown_until = None
            delay = int(float(self.start_delay_entry.get()))
        if delay <= 0:
            self.start_clicking()
            return
        if not self._confirm_guard_off():
            return
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        # Stop, Emergency and Toggle keys cancel it. A long scheduled wait claims
        # them only for its last minute, so Esc keeps working elsewhere meanwhile;
        # until then the Stop button, tray Stop or the toggle key cancel it.
        self._hotkeys.set_running(delay <= _CLAIM_STOP_KEYS_SECONDS)
        self._set_settings_locked(True)
        self._countdown_tick(delay)

    def _countdown_tick(self, remaining: int) -> None:
        until = self._countdown_until
        if until is not None:
            remaining = math.ceil((until - datetime.now()).total_seconds())
        if remaining > 0:
            if remaining <= _CLAIM_STOP_KEYS_SECONDS:
                self._hotkeys.set_running(True)
            if until is not None and remaining > _CLAIM_STOP_KEYS_SECONDS:
                message = f"Starting at {until:%H:%M} (in {describe_wait(remaining)})"
            else:
                message = f"Starting in {remaining}..."
            self._set_status_message(message, "alert")
            self._countdown_job = self.root.after(1000, self._countdown_tick, remaining - 1)
            return
        self._countdown_job = None
        self._countdown_until = None
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
        self._countdown_until = None
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
        if message is not None:
            self._paint_stopped(message, "alert")
        return True
