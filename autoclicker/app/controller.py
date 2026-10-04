# SPDX-License-Identifier: CC-BY-NC-4.0
"""Application controller coordinating core services and click lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pyautogui

from ..core.click_engine import ClickEngine, RunOutcome
from ..core.safety import get_foreground_window_handle
from ..core.screen import ScreenBounds, virtual_screen_bounds
from ..core.session_log import append_session_event
from ..core.settings_manager import SettingsManager
from ..utils.coordinate_picker import CoordinatePicker, PresetManager

_log = logging.getLogger(__name__)


@dataclass
class StartClickResult:
    """Outcome of validate-and-start."""

    success: bool
    validation_errors: dict[str, str] | None = None
    sanitized: dict[str, Any] | None = None
    interval_ms: float | None = None
    # True when Start was refused because the previous run is still shutting down
    busy: bool = False


class AutoclickerController:
    """Owns settings, click engine, coordinate picker, and presets."""

    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.click_engine = ClickEngine()
        self.coordinate_picker = CoordinatePicker()
        self.preset_manager = PresetManager(self.settings)

    def apply_safety_from_settings(self) -> None:
        """Apply persisted safety settings to the click engine."""
        self.click_engine.configure_safety(
            failsafe=bool(self.settings.get("enable_failsafe", True)),
            max_cps=int(self.settings.get("max_cps_ceiling", 50)),
            pause_when_unfocused=bool(self.settings.get("pause_when_unfocused", False)),
        )

    def configure_safety_from_ui(self, failsafe: bool, pause_when_unfocused: bool) -> None:
        """Reconfigure safety from live UI toggle values."""
        self.click_engine.configure_safety(
            failsafe=failsafe,
            max_cps=int(self.settings.get("max_cps_ceiling", 50)),
            pause_when_unfocused=pause_when_unfocused,
        )

    @staticmethod
    def collect_raw_settings(ui_fields: dict[str, Any]) -> dict[str, Any]:
        """Build a raw settings dict from UI field values passed in."""
        return {
            "x_coord": ui_fields["x_coord"],
            "y_coord": ui_fields["y_coord"],
            "interval": ui_fields["interval"],
            "interval_unit": ui_fields["interval_unit"],
            "variation": ui_fields["variation"],
            "mouse_button": ui_fields["mouse_button"],
            "click_type": ui_fields["click_type"],
            "burst_clicks": ui_fields["burst_clicks"],
            "burst_pause": ui_fields["burst_pause"],
            "max_clicks": ui_fields["max_clicks"],
            "auto_stop_minutes": ui_fields["auto_stop_minutes"],
            "enable_failsafe": ui_fields["enable_failsafe"],
            "pause_when_unfocused": ui_fields["pause_when_unfocused"],
            "max_cps_ceiling": ui_fields.get("max_cps_ceiling", 50),
        }

    def validate_and_start_clicking(
        self,
        raw_settings: dict[str, Any],
        *,
        failsafe: bool,
        pause_when_unfocused: bool,
        on_finished: Callable[[RunOutcome], None] | None = None,
        screen_bounds: ScreenBounds | None = None,
    ) -> StartClickResult:
        """Validate settings and start the click engine if valid.

        ``on_finished`` runs on the click thread once the run ends, after the
        session log entry for it has been written.
        """
        if self.click_engine.is_running:
            return StartClickResult(success=False)
        validation_result = self._validate(raw_settings, self.settings, screen_bounds)

        if not validation_result["valid"]:
            return StartClickResult(
                success=False,
                validation_errors=validation_result["errors"],
            )

        sanitized = validation_result["sanitized_settings"]

        x = sanitized["x_coord"]
        y = sanitized["y_coord"]
        interval = sanitized["interval"]
        interval_unit = sanitized["interval_unit"]
        variation = sanitized["variation"]
        burst_clicks = sanitized["burst_clicks"]
        burst_pause = sanitized["burst_pause"] / 1000

        if interval_unit == "seconds":
            interval_ms = interval * 1000
        else:
            interval_ms = interval

        self.settings.update(sanitized)
        self.configure_safety_from_ui(failsafe, pause_when_unfocused)

        if pause_when_unfocused and get_foreground_window_handle() is None:
            return StartClickResult(
                success=False,
                validation_errors={
                    "pause_when_unfocused": (
                        "Could not read the foreground window. "
                        "Uncheck pause-when-unfocused or install pywin32."
                    )
                },
            )

        started = self.click_engine.start_clicking(
            x=x,
            y=y,
            interval=interval_ms,
            variation=variation,
            burst_clicks=burst_clicks,
            burst_pause=burst_pause,
            max_clicks=sanitized["max_clicks"],
            auto_stop_minutes=sanitized["auto_stop_minutes"],
            mouse_button=sanitized["mouse_button"],
            click_type=sanitized["click_type"],
            on_finished=lambda outcome: self._run_finished(outcome, on_finished),
        )

        if started:
            append_session_event(
                "start",
                x=x,
                y=y,
                interval_ms=interval_ms,
                button=sanitized["mouse_button"],
            )

        return StartClickResult(
            success=started,
            sanitized=sanitized,
            interval_ms=interval_ms,
            busy=not started,
        )

    @staticmethod
    def _run_finished(
        outcome: RunOutcome, on_finished: Callable[[RunOutcome], None] | None
    ) -> None:
        """Log the one stop event for a run, then hand the outcome to the UI.

        Runs on the click thread, so the log line is written even when the UI
        is being torn down (e.g. Stop during quit).
        """
        fields: dict[str, Any] = {
            "reason": outcome.reason,
            "clicks": outcome.clicks,
            "detail": outcome.message,
        }
        append_session_event("stop", **fields)
        if on_finished is not None:
            on_finished(outcome)

    @staticmethod
    def _validate(
        raw_settings: dict[str, Any],
        settings: SettingsManager,
        screen_bounds: ScreenBounds | None,
    ) -> dict[str, Any]:
        """Validate against the desktop spanning every monitor."""
        bounds = screen_bounds or virtual_screen_bounds(pyautogui.size)
        return settings.validate_all_settings(
            raw_settings, bounds.width, bounds.height, bounds.left, bounds.top
        )

    def stop_clicking(self) -> bool:
        """Stop clicking and wait for the click thread. Returns prior running state.

        The run's outcome (and its session log entry) arrives via on_finished.
        """
        was_running = self.click_engine.is_running
        self.click_engine.stop_clicking()
        return was_running

    def emergency_stop(self) -> bool:
        """Signal an immediate halt without waiting. Returns prior running state."""
        was_running = self.click_engine.is_running
        self.click_engine.emergency_stop()
        return was_running

    def finish_run(self) -> None:
        """Reap the finished click thread (called on the UI thread after on_finished)."""
        self.click_engine.stop_clicking()

    def persist_settings_on_quit(
        self,
        raw_settings: dict[str, Any],
        *,
        settings_manager: SettingsManager | None = None,
        screen_bounds: ScreenBounds | None = None,
    ) -> None:
        """Validate and persist settings when the application exits."""
        settings = settings_manager or self.settings
        validation_result = self._validate(raw_settings, settings, screen_bounds)
        if validation_result["valid"]:
            settings.update(validation_result["sanitized_settings"])
        else:
            _log.warning("Quit settings invalid; keeping last-good file")
