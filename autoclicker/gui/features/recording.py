# SPDX-License-Identifier: CC-BY-NC-4.0
"""Record a sequence by clicking through it once (#86)."""

from __future__ import annotations

from ...core.recorder import ClickRecorder, RecordedClick, clicks_to_steps
from ...core.safety import is_own_window, root_window_at
from ...core.settings_manager import MAX_SEQUENCE_STEPS
from .. import dialogs
from .base import AppBase


class RecordingMixin(AppBase):
    def toggle_sequence_recording(self) -> None:
        """Record button: start capturing real clicks as steps, or finish."""
        if self._finish_recording():
            return
        if self.click_engine.is_running or self._countdown_job is not None:
            self._set_status_message("Stop clicking before recording", "alert")
            return
        self._recorded: list[RecordedClick] = []
        recorder = ClickRecorder(on_click=lambda click: self._ui(self._on_recorded_click, click))
        if not recorder.start():
            self._set_status_message("Could not start recording on this system", "error")
            return
        self._recorder = recorder
        self._hotkeys.set_running(True)  # the Stop and Emergency keys finish recording
        stop_key = self._hotkey_suffix("stop").strip(" ()") or "Stop"
        self._set_status_message(
            f"Recording: click each point in order, then press {stop_key} or Record", "alert"
        )

    def _on_recorded_click(self, click: RecordedClick) -> None:
        if self._recorder is None:
            return
        window = root_window_at(click.x, click.y)
        if window is None or is_own_window(window):
            return  # clicks on the autoclicker itself (e.g. the Record button)
        self._recorded.append(click)
        count = len(self._recorded)
        self._set_status_message(f"Recording: {count} click{'s' * (count != 1)}", "alert")

    def _finish_recording(self) -> bool:
        """Stop recording and turn the clicks into steps. False if not recording."""
        recorder, self._recorder = self._recorder, None
        if recorder is None:
            return False
        recorder.stop()
        self._hotkeys.set_running(False)
        steps = clicks_to_steps(self._recorded)
        if not steps:
            self._set_status_message("Recording ended with no clicks", "alert")
            return True
        if self.sequence_steps:
            replace = dialogs.messagebox.askyesnocancel(
                "Recorded sequence",
                f"Replace the current {len(self.sequence_steps)} steps with the "
                f"{len(steps)} recorded ones?\n\nYes replaces them, No adds the recording "
                "after them, Cancel discards the recording.",
            )
            if replace is None:
                self._set_status_message("Recording discarded", "alert")
                return True
            if not replace:
                steps = self.sequence_steps + steps
        recorded = len(steps)
        self.sequence_steps = steps[:MAX_SEQUENCE_STEPS]
        self.target_mode_var.set("sequence")
        self._apply_target_mode_state()
        self._sequence_changed(select=0)
        kept = len(self.sequence_steps)
        if kept < recorded:
            self._set_status_message(
                f"Kept {kept} of {recorded} steps (a sequence holds up to {MAX_SEQUENCE_STEPS})",
                "alert",
            )
        else:
            self._set_status_message(f"Recorded {kept} steps", "alert")
        return True
