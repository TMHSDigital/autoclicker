# SPDX-License-Identifier: CC-BY-NC-4.0
"""Application controller coordinating core services and click lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pyautogui

from ..core.click_engine import ClickEngine
from ..core.session_log import append_session_event
from ..core.settings_manager import SettingsManager
from ..utils.coordinate_picker import CoordinatePicker, PresetManager


@dataclass
class StartClickResult:
    """Outcome of validate-and-start."""

    success: bool
    validation_errors: dict[str, str] | None = None
    sanitized: dict[str, Any] | None = None
    interval_ms: float | None = None


class AutoclickerController:
    """Owns settings, click engine, coordinate picker, and presets."""

    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.click_engine = ClickEngine()
        self.coordinate_picker = CoordinatePicker()
        self.preset_manager = PresetManager(self.settings)
        self._on_safety_stop: Callable[[str], None] | None = None

    def apply_safety_from_settings(
        self,
        on_safety_stop: Callable[[str], None] | None = None,
    ) -> None:
        """Apply persisted safety settings to the click engine."""
        if on_safety_stop is not None:
            self._on_safety_stop = on_safety_stop
        self.click_engine.configure_safety(
            failsafe=bool(self.settings.get("enable_failsafe", True)),
            max_cps=int(self.settings.get("max_cps_ceiling", 50)),
            pause_when_unfocused=bool(self.settings.get("pause_when_unfocused", False)),
            on_safety_stop=self._on_safety_stop,
        )

    def configure_safety_from_ui(
        self,
        failsafe: bool,
        pause_when_unfocused: bool,
        on_safety_stop: Callable[[str], None],
    ) -> None:
        """Reconfigure safety from live UI toggle values."""
        self._on_safety_stop = on_safety_stop
        self.click_engine.configure_safety(
            failsafe=failsafe,
            max_cps=int(self.settings.get("max_cps_ceiling", 50)),
            pause_when_unfocused=pause_when_unfocused,
            on_safety_stop=on_safety_stop,
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
        on_safety_stop: Callable[[str], None],
        on_click_complete: Callable[[], None],
        on_status_update: Callable[[], None],
        screen_size: tuple[int, int] | None = None,
    ) -> StartClickResult:
        """Validate settings and start the click engine if valid."""
        if screen_size is None:
            screen_size = pyautogui.size()
        screen_width, screen_height = screen_size

        validation_result = self.settings.validate_all_settings(
            raw_settings, screen_width, screen_height
        )

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
        self.apply_safety_from_settings(on_safety_stop)
        self.configure_safety_from_ui(failsafe, pause_when_unfocused, on_safety_stop)

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
            on_click_complete=on_click_complete,
            on_status_update=on_status_update,
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
        )

    def stop_clicking(self, *, reason: str = "user_stop") -> bool:
        """Stop clicking; log session if it was running. Returns prior running state."""
        was_running = self.click_engine.is_running
        self.click_engine.stop_clicking()
        if was_running:
            append_session_event(
                "stop",
                reason=reason,
                clicks=self.click_engine.click_count,
            )
        return was_running

    def emergency_stop(self) -> bool:
        """Emergency halt with session log. Returns prior running state."""
        was_running = self.click_engine.is_running
        self.click_engine.emergency_stop()
        if was_running:
            append_session_event(
                "stop",
                reason="emergency",
                clicks=self.click_engine.click_count,
            )
        return was_running

    def log_safety_stop(self, reason: str) -> None:
        """Append a safety-triggered stop to the session log."""
        append_session_event(
            "safety_stop",
            reason=reason,
            clicks=self.click_engine.click_count,
        )

    def persist_settings_on_quit(
        self,
        raw_settings: dict[str, Any],
        *,
        settings_manager: SettingsManager | None = None,
        screen_size: tuple[int, int] | None = None,
    ) -> None:
        """Validate and persist settings when the application exits."""
        settings = settings_manager or self.settings
        if screen_size is None:
            screen_size = pyautogui.size()
        screen_width, screen_height = screen_size
        validation_result = settings.validate_all_settings(
            raw_settings, screen_width, screen_height
        )
        if validation_result["valid"]:
            settings.update(validation_result["sanitized_settings"])
        else:
            settings.update(raw_settings)
