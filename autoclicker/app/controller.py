# SPDX-License-Identifier: CC-BY-NC-4.0
"""Application controller coordinating core services and click lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pyautogui
from PIL import Image

from ..core.click_engine import ClickEngine, ClickStep, PixelCondition, RunOutcome
from ..core.image_match import ImageTarget
from ..core.safety import get_foreground_window_handle
from ..core.screen import ScreenBounds, virtual_screen_bounds
from ..core.session_log import append_session_event
from ..core.settings_manager import SettingsManager
from ..utils.profiles import PresetManager

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


def _load_image_target(sanitized: dict[str, Any]) -> tuple[ImageTarget | None, str | None]:
    """The engine's image target from validated settings, or an error message."""
    path = str(sanitized.get("image_path", ""))
    try:
        with Image.open(path) as captured:
            template = captured.convert("RGB")
    except (OSError, ValueError):
        return None, "The captured image is missing or unreadable; capture it again"
    return ImageTarget(template=template, region=ScreenBounds(*sanitized["image_region"])), None


def _pixel_condition(sanitized: dict[str, Any]) -> PixelCondition | None:
    """The engine's pixel condition from validated settings, or None when off."""
    on_mismatch = sanitized.get("condition", "none")
    if on_mismatch not in ("wait", "stop"):
        return None
    color = str(sanitized["condition_color"])
    rgb = (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    return PixelCondition(
        x=int(sanitized["condition_x"]),
        y=int(sanitized["condition_y"]),
        rgb=rgb,
        tolerance=int(sanitized["condition_tolerance"]),
        on_mismatch=on_mismatch,
    )


def _hotkey_clash(key: str, bindings: Any) -> str | None:
    """Error if the key to press is one of the app's own hotkeys (it would never arrive)."""
    from .hotkeys import HotkeyError, normalize_hotkey

    try:
        pressed = normalize_hotkey(key)
    except HotkeyError:
        return None  # e.g. a bare letter, which can't be a hotkey
    for action, bound in dict(bindings or {}).items():
        try:
            if bound and normalize_hotkey(str(bound)) == pressed:
                return f"{pressed} is the {action} hotkey; pick another key"
        except HotkeyError:
            continue
    return None


class AutoclickerController:
    """Owns settings, click engine, and presets."""

    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.click_engine = ClickEngine()
        self.preset_manager = PresetManager(self.settings)

    def apply_safety_from_settings(self) -> None:
        """Apply persisted safety settings to the click engine."""
        self.click_engine.configure_safety(
            failsafe=bool(self.settings.get("enable_failsafe", True)),
            max_cps=int(self.settings.get("max_cps_ceiling", 50)),
            pause_when_unfocused=bool(self.settings.get("pause_when_unfocused", False)),
        )

    def configure_safety_from_ui(
        self, failsafe: bool, pause_when_unfocused: bool, max_cps: int | None = None
    ) -> None:
        """Reconfigure safety from live UI toggle values (speed limit from settings if not given)."""
        self.click_engine.configure_safety(
            failsafe=failsafe,
            max_cps=int(self.settings.get("max_cps_ceiling", 50) if max_cps is None else max_cps),
            pause_when_unfocused=pause_when_unfocused,
        )

    @staticmethod
    def collect_raw_settings(ui_fields: dict[str, Any]) -> dict[str, Any]:
        """Build a raw settings dict from UI field values passed in."""
        return {
            "target_mode": ui_fields.get("target_mode", "fixed"),
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
            "start_delay_seconds": ui_fields.get("start_delay_seconds", 0),
            "sequence": ui_fields.get("sequence", []),
            "sequence_repeat": ui_fields.get("sequence_repeat", 0),
            "action": ui_fields.get("action", "click"),
            "hold_ms": ui_fields.get("hold_ms", 500),
            "key": ui_fields.get("key", ""),
            "condition": ui_fields.get("condition", "none"),
            "condition_x": ui_fields.get("condition_x", 0),
            "condition_y": ui_fields.get("condition_y", 0),
            "condition_color": ui_fields.get("condition_color", "#000000"),
            "condition_tolerance": ui_fields.get("condition_tolerance", 16),
            "image_path": ui_fields.get("image_path", ""),
            "image_region": ui_fields.get("image_region", []),
            "image_margin": ui_fields.get("image_margin", 150),
        }

    def validate(
        self, raw_settings: dict[str, Any], screen_bounds: ScreenBounds | None = None
    ) -> dict[str, Any]:
        """Parse and validate raw UI settings without starting anything.

        Returns ``{"valid", "errors", "sanitized_settings"}``.
        """
        return self._validate(raw_settings, self.settings, screen_bounds)

    def validation_errors(
        self, raw_settings: dict[str, Any], screen_bounds: ScreenBounds | None = None
    ) -> dict[str, str]:
        """Validation errors for raw UI settings, without starting anything."""
        result = self.validate(raw_settings, screen_bounds)
        return {} if result["valid"] else dict(result["errors"])

    def validate_and_start_clicking(
        self,
        raw_settings: dict[str, Any],
        *,
        failsafe: bool,
        pause_when_unfocused: bool,
        on_finished: Callable[[RunOutcome], None] | None = None,
        screen_bounds: ScreenBounds | None = None,
        persist: bool = True,
    ) -> StartClickResult:
        """Validate settings and start the click engine if valid.

        ``persist=False`` (command-line headless runs) leaves saved settings alone.

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

        mode = sanitized.get("target_mode", "fixed")
        action = sanitized.get("action", "click")
        has_point = mode == "fixed" and action != "key"
        x = sanitized["x_coord"] if has_point else None
        y = sanitized["y_coord"] if has_point else None
        steps = (
            [ClickStep(**step) for step in sanitized["sequence"]] if mode == "sequence" else None
        )
        image = None
        if mode == "image":
            image, error = _load_image_target(sanitized)
            if error:
                return StartClickResult(success=False, validation_errors={"image_path": error})
        interval = sanitized["interval"]
        interval_unit = sanitized["interval_unit"]
        variation = sanitized["variation"]
        burst_clicks = sanitized["burst_clicks"]
        burst_pause = sanitized["burst_pause"] / 1000

        if interval_unit == "seconds":
            interval_ms = interval * 1000
        else:
            interval_ms = interval

        if persist:
            self.settings.update(sanitized)
        self.configure_safety_from_ui(
            failsafe, pause_when_unfocused, sanitized.get("max_cps_ceiling")
        )

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
            steps=steps,
            repeat=int(sanitized.get("sequence_repeat", 0)),
            action=action,
            hold_ms=float(sanitized.get("hold_ms", 0) or 0),
            key=str(sanitized.get("key", "")),
            condition=_pixel_condition(sanitized),
            image=image,
        )

        if started:
            if action == "key":
                target = f"key:{sanitized['key']}"
            elif image is not None:
                target = "image"
            elif steps:
                target = f"sequence:{len(steps)}"
            else:
                target = f"{x},{y}" if has_point else "cursor"
            append_session_event(
                "start",
                target=target,
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
        result = settings.validate_all_settings(
            raw_settings, bounds.width, bounds.height, bounds.left, bounds.top
        )
        sanitized = result["sanitized_settings"]
        if sanitized.get("action") == "key" and "key" not in result["errors"]:
            clash = _hotkey_clash(str(sanitized.get("key", "")), settings.get("hotkeys"))
            if clash:
                result["errors"]["key"] = clash
                result["valid"] = False
        return result

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
