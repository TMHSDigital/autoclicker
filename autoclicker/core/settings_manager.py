# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Settings management for the autoclicker application
Handles loading, saving, and validation of user settings
"""

import copy
import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .exceptions import ValidationError
from .screen import ScreenBounds
from .settings_paths import LEGACY_FILENAME, atomic_write_json, resolve_settings_file

_log = logging.getLogger(__name__)

# Highest runaway-guard ceiling accepted, in clicks per second.
MAX_CPS_CEILING = 10_000

# Fields parsed from free-text UI entries. Values are parsed, never clamped or
# defaulted: a value that does not parse, or is out of range, is an error.
_INT_FIELDS = frozenset(
    {
        "x_coord",
        "y_coord",
        "variation",
        "burst_clicks",
        "max_clicks",
        "auto_stop_minutes",
        "max_cps_ceiling",
        "start_delay_seconds",
        "sequence_repeat",
    }
)
_FLOAT_FIELDS = frozenset({"interval", "burst_pause", "hold_ms"})
_CHOICE_FIELDS: dict[str, tuple[str, ...]] = {
    "mouse_button": ("left", "right", "middle"),
    "click_type": ("single", "double"),
    "interval_unit": ("ms", "seconds"),
    "target_mode": ("fixed", "cursor", "sequence"),
    "action": ("click", "hold", "key"),
}

# Human-readable names for validation error keys, used in error dialogs.
FIELD_LABELS: dict[str, str] = {
    "x_coord": "X",
    "y_coord": "Y",
    "coordinates": "Coordinates",
    "target_mode": "Target",
    "interval": "Interval",
    "interval_unit": "Interval unit",
    "variation": "Variation",
    "mouse_button": "Mouse button",
    "click_type": "Click type",
    "burst": "Burst",
    "burst_clicks": "Burst clicks",
    "burst_pause": "Burst pause",
    "max_clicks": "Limit clicks",
    "auto_stop": "Auto-stop",
    "auto_stop_minutes": "Auto-stop",
    "max_cps_ceiling": "Max clicks per second",
    "pause_when_unfocused": "Pause when unfocused",
    "start_delay_seconds": "Start delay",
    "sequence": "Sequence",
    "sequence_repeat": "Repeat",
    "action": "Action",
    "hold_ms": "Hold",
    "key": "Key",
}

# Longest mouse-button hold, in milliseconds.
MAX_HOLD_MS = 60_000

# Longest countdown before a Start-button run begins, in seconds.
MAX_START_DELAY_SECONDS = 60

# Sequence mode limits: steps per round, rounds per run, wait between steps (ms).
MAX_SEQUENCE_STEPS = 50
MAX_SEQUENCE_REPEAT = 1_000_000
MAX_STEP_DELAY_MS = 60_000

# Fields of one sequence step and the setting whose parser reads each.
_STEP_FIELDS = (
    ("x", "x_coord"),
    ("y", "y_coord"),
    ("button", "mouse_button"),
    ("click_type", "click_type"),
    ("delay_ms", "burst_pause"),
)
_STEP_LABELS = {"x": "X", "y": "Y", "button": "button", "click_type": "click type"}


# Settings whose stored value must be of a given JSON type; anything else falls
# back to the default for that key on load. Numeric fields also accept strings
# because the UI stores what was typed, and validation reports bad values.
_BOOL_KEYS = frozenset({"enable_failsafe", "pause_when_unfocused", "minimize_to_tray"})
_DICT_KEYS = frozenset({"hotkeys", "presets"})
_LIST_KEYS = frozenset({"sequence"})
_STR_KEYS = frozenset({*_CHOICE_FIELDS, "theme", "key"})
_NUMERIC_KEYS = _INT_FIELDS | _FLOAT_FIELDS


def _has_valid_type(key: str, value: Any) -> bool:
    if key in _BOOL_KEYS:
        return isinstance(value, bool)
    if key in _DICT_KEYS:
        return isinstance(value, dict)
    if key in _LIST_KEYS:
        return isinstance(value, list)
    if key in _STR_KEYS:
        return isinstance(value, str)
    if key in _NUMERIC_KEYS:
        return isinstance(value, (int, float, str)) and not isinstance(value, bool)
    return True


def _is_valid_preset(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(value.get(axis), int) and not isinstance(value.get(axis), bool)
        for axis in ("x", "y")
    )


def _key_error(text: str) -> str | None:
    """Why a key (or "+"-joined combo) can't be pressed, or None if it can."""
    parts = text.split("+")
    if not text or any(not part for part in parts):
        return "Enter a key such as F5, space or ctrl+r"
    import pyautogui  # deferred: the settings layer is otherwise free of it

    for part in parts:
        if part not in pyautogui.KEYBOARD_KEYS:
            return f"Unknown key: {part}"
    return None


def field_label(key: str) -> str:
    """Return the display name for a settings or validation-error key."""
    return FIELD_LABELS.get(key, key.replace("_", " ").capitalize())


class SettingsManager:
    """Manages application settings with validation and persistence"""

    DEFAULT_SETTINGS = {
        "target_mode": "fixed",
        "x_coord": 100,
        "y_coord": 100,
        "interval": 1000,
        "interval_unit": "ms",
        "variation": 0,
        "mouse_button": "left",
        "click_type": "single",
        "burst_clicks": 1,
        "burst_pause": 1000,
        "max_clicks": 0,
        "auto_stop_minutes": 0,
        "enable_failsafe": True,
        "max_cps_ceiling": 50,
        "start_delay_seconds": 3,
        "sequence": [],
        "sequence_repeat": 0,
        "action": "click",
        "hold_ms": 500,
        "key": "",
        "pause_when_unfocused": False,
        "theme": "light",
        "minimize_to_tray": True,
        # None until the user has been asked once; then True or False.
        "check_for_updates": None,
        "last_update_check": 0,
        "hotkeys": {"start": "F6", "stop": "F7", "emergency": "Esc", "toggle": ""},
        "presets": {},
    }

    def __init__(self, settings_file: str | None = None):
        if settings_file is None or settings_file == LEGACY_FILENAME:
            self.settings_file = resolve_settings_file()
        else:
            self.settings_file = settings_file
        # Set when the settings file could not be used; shown once in the UI.
        self.load_warning: str | None = None
        self._settings = self._load_settings()

    def _defaults(self) -> dict[str, Any]:
        """Fresh defaults. Deep copy so nested dicts (presets, hotkeys) are never shared."""
        return copy.deepcopy(self.DEFAULT_SETTINGS)

    def _load_settings(self) -> dict[str, Any]:
        """Load settings from file or return defaults.

        An unreadable file is moved aside (never overwritten by the next save),
        and individual values of the wrong type fall back to their defaults.
        """
        try:
            # A missing or empty file holds nothing worth keeping.
            if not os.path.exists(self.settings_file) or os.path.getsize(self.settings_file) == 0:
                return self._defaults()
            with open(self.settings_file, encoding="utf-8") as f:
                loaded_settings = json.load(f)
        except json.JSONDecodeError as e:
            _log.warning("Settings file is not valid JSON: %s", e)
            self._quarantine("is not valid JSON")
            return self._defaults()
        except (OSError, UnicodeDecodeError) as e:
            _log.warning("Could not load settings file: %s", e)
            return self._defaults()
        if not isinstance(loaded_settings, dict):
            _log.warning("Settings file is not a JSON object; using defaults")
            self._quarantine("is not a JSON object")
            return self._defaults()
        return self._merge_with_defaults(loaded_settings)

    def _merge_with_defaults(self, loaded: dict[str, Any]) -> dict[str, Any]:
        """Defaults overlaid with loaded values, dropping wrong-typed ones per key."""
        merged = self._defaults()
        for key, value in loaded.items():
            if not _has_valid_type(key, value):
                _log.warning("Ignoring setting %r with unexpected value %r", key, value)
                continue
            if key == "presets":
                bad = [name for name, preset in value.items() if not _is_valid_preset(preset)]
                for name in bad:
                    _log.warning("Ignoring malformed preset %r", name)
                value = {k: v for k, v in value.items() if k not in bad}
            merged[key] = value
        return merged

    def _quarantine(self, problem: str) -> None:
        """Move an unusable settings file aside so the next save cannot destroy it."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        source = Path(self.settings_file)
        backup = source.with_name(f"{source.name}.corrupt-{stamp}")
        try:
            os.replace(source, backup)
        except OSError as e:
            _log.warning("Could not move the unreadable settings file aside: %s", e)
            self.load_warning = f"Settings file {problem}; using defaults"
            return
        _log.warning("Moved unreadable settings file to %s", backup)
        self.load_warning = (
            f"Settings file {problem}; using defaults. Saved a copy as {backup.name}"
        )

    def _save_settings(self) -> None:
        """Save current settings to file atomically"""
        try:
            atomic_write_json(Path(self.settings_file), self._settings)
        except OSError as e:
            _log.warning("Could not save settings file: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save"""
        self._settings[key] = value
        self._save_settings()

    def update(self, settings_dict: dict[str, Any]) -> None:
        """Update multiple settings and save"""
        self._settings.update(settings_dict)
        self._save_settings()

    def validate_coordinate(
        self,
        x: int,
        y: int,
        screen_width: int,
        screen_height: int,
        screen_left: int = 0,
        screen_top: int = 0,
    ) -> tuple[bool, str]:
        """Validate that coordinates fall on the desktop.

        The desktop is the half-open rectangle starting at (screen_left,
        screen_top); left/top are negative for monitors left of or above the
        primary one.
        """
        try:
            bounds = ScreenBounds(screen_left, screen_top, screen_width, screen_height)
            if not bounds.contains(x, y):
                raise ValidationError(
                    "coordinates",
                    f"({x}, {y})",
                    f"({x}, {y}) is off screen. Valid range: {bounds.describe()}",
                )
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_interval(self, interval: float, unit: str) -> tuple[bool, str]:
        """Validate click interval settings with detailed error message"""
        try:
            if unit not in ["ms", "seconds"]:
                raise ValidationError(
                    "interval_unit", unit, f"Invalid unit: {unit}. Must be 'ms' or 'seconds'"
                )

            if unit == "ms":
                if not (0 <= interval <= 60000):
                    raise ValidationError(
                        "interval",
                        interval,
                        "Interval in milliseconds must be between 0 and 60000 (0 = no delay between bursts)",
                    )
            elif unit == "seconds":
                if not (0.001 <= interval <= 60):
                    raise ValidationError(
                        "interval",
                        interval,
                        "Interval in seconds must be between 0.001 and 60 (0.001s to 1 minute)",
                    )

            return True, ""
        except ValidationError as e:
            return False, e.reason

    def _parse_int(self, value: Any, field: str) -> int:
        """Parse a value as int or raise ValidationError."""
        try:
            if isinstance(value, str):
                value = value.strip()
            return int(float(value))
        except (ValueError, TypeError):
            raise ValidationError(field, value, "Must be a number")

    def validate_clicks(self, clicks: int) -> tuple[bool, str]:
        """Validate click count settings with detailed error message"""
        try:
            clicks = self._parse_int(clicks, "max_clicks")
            if clicks < 0:
                raise ValidationError("max_clicks", clicks, "Click count cannot be negative")
            if clicks > 1000000:  # Reasonable upper limit to prevent system overload
                raise ValidationError(
                    "max_clicks",
                    clicks,
                    "Click count cannot exceed 1,000,000 to prevent system overload",
                )
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_minutes(self, minutes: int) -> tuple[bool, str]:
        """Validate time settings with detailed error message"""
        try:
            minutes = self._parse_int(minutes, "auto_stop_minutes")
            if minutes < 0:
                raise ValidationError("auto_stop_minutes", minutes, "Minutes cannot be negative")
            if minutes > 1440:  # 24 hours max
                raise ValidationError(
                    "auto_stop_minutes",
                    minutes,
                    "Auto-stop time cannot exceed 24 hours (1440 minutes)",
                )
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_variation(self, variation: int, interval: float, unit: str) -> tuple[bool, str]:
        """Validate random variation settings"""
        try:
            variation = self._parse_int(variation, "variation")
            if variation < 0:
                raise ValidationError("variation", variation, "Variation cannot be negative")

            interval_ms = interval if unit == "ms" else interval * 1000

            if interval_ms <= 0:
                if variation > 0:
                    raise ValidationError(
                        "variation",
                        variation,
                        "Set a positive interval before using random variation",
                    )
                return True, ""

            if variation >= interval_ms:
                raise ValidationError(
                    "variation",
                    variation,
                    f"Variation ({variation}ms) cannot be greater than or equal to interval ({interval_ms}ms)",
                )

            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_burst_settings(self, burst_clicks: int, burst_pause: float) -> tuple[bool, str]:
        """Validate burst mode settings"""
        try:
            if burst_clicks < 1:
                raise ValidationError(
                    "burst_clicks", burst_clicks, "Burst clicks must be a positive integer"
                )
            if burst_clicks > 100:
                raise ValidationError(
                    "burst_clicks",
                    burst_clicks,
                    "Burst clicks cannot exceed 100 to prevent system overload",
                )

            if burst_pause < 0:
                raise ValidationError(
                    "burst_pause", burst_pause, "Burst pause must be a non-negative number"
                )
            if burst_pause > 60000:  # 1 minute max
                raise ValidationError(
                    "burst_pause",
                    burst_pause,
                    "Burst pause cannot exceed 60,000 milliseconds (1 minute)",
                )

            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_max_cps(self, max_cps: int) -> tuple[bool, str]:
        """Validate runaway CPS ceiling. 0 disables the guard."""
        try:
            max_cps = self._parse_int(max_cps, "max_cps_ceiling")
            if max_cps < 0:
                raise ValidationError("max_cps_ceiling", max_cps, "CPS ceiling cannot be negative")
            if max_cps > MAX_CPS_CEILING:
                raise ValidationError(
                    "max_cps_ceiling",
                    max_cps,
                    f"CPS ceiling cannot exceed {MAX_CPS_CEILING:,}",
                )
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def parse_input(self, key: str, value: Any) -> tuple[Any, str | None]:
        """Parse one raw (usually string) UI value.

        Returns ``(parsed, None)`` on success or ``(None, message)`` when the
        value cannot be parsed. Range checks happen in validate_all_settings;
        nothing here clamps or substitutes a default.
        """
        if key in _INT_FIELDS or key in _FLOAT_FIELDS:
            if isinstance(value, bool) or value is None:
                return None, "Enter a number"
            text = value.strip() if isinstance(value, str) else value
            if text == "":
                return None, "Enter a number"
            try:
                number = float(text)
            except (TypeError, ValueError):
                return None, "Must be a number"
            if not math.isfinite(number):
                return None, "Must be a number"
            if key in _INT_FIELDS:
                if not number.is_integer():
                    return None, "Must be a whole number"
                return int(number), None
            # Keep whole numbers as int so they round-trip to the UI as "500", not "500.0"
            return (int(number) if number.is_integer() else number), None
        if key == "sequence":
            return self._parse_sequence(value)
        if key == "key":
            if not isinstance(value, str):
                return None, "Enter a key such as F5, space or ctrl+r"
            return "+".join(part.strip().lower() for part in value.split("+")), None
        if key in _CHOICE_FIELDS:
            choices = _CHOICE_FIELDS[key]
            text = str(value).strip()
            if text not in choices:
                return None, f"Must be one of: {', '.join(choices)}"
            return text, None
        return value, None

    def _parse_sequence(self, value: Any) -> tuple[Any, str | None]:
        """Parse a list of sequence steps; missing button/type/delay get defaults."""
        if not isinstance(value, list):
            return None, "Must be a list of steps"
        steps = []
        for number, raw in enumerate(value, start=1):
            if not isinstance(raw, dict):
                return None, f"Step {number} is not a step"
            step: dict[str, Any] = {"button": "left", "click_type": "single", "delay_ms": 0}
            for field, setting in _STEP_FIELDS:
                if field not in raw:
                    if field in ("x", "y"):
                        return None, f"Step {number} has no {field.upper()}"
                    continue
                parsed, error = self.parse_input(setting, raw[field])
                if error is not None:
                    label = _STEP_LABELS.get(field, "wait")
                    return None, f"Step {number} {label}: {error}"
                step[field] = parsed
            if not 0 <= step["delay_ms"] <= MAX_STEP_DELAY_MS:
                return None, f"Step {number} wait must be 0 to {MAX_STEP_DELAY_MS:,} ms"
            steps.append(step)
        return steps, None

    def validate_all_settings(
        self,
        settings: dict[str, Any],
        screen_width: int = 1920,
        screen_height: int = 1080,
        screen_left: int = 0,
        screen_top: int = 0,
    ) -> dict[str, Any]:
        """Parse and validate settings.

        Returns ``{"valid", "errors", "sanitized_settings"}``. ``errors`` maps a
        field (or group such as ``"coordinates"``) to a message;
        ``sanitized_settings`` holds the parsed values that could be read.
        Invalid input is reported, never rewritten into a different value.
        """
        errors: dict[str, str] = {}
        parsed: dict[str, Any] = {}
        # Fields the chosen target mode doesn't use are not validated: X/Y in
        # cursor and sequence mode, the sequence outside sequence mode.
        mode = str(settings.get("target_mode", "fixed")).strip()
        unused = {"sequence", "sequence_repeat"} if mode != "sequence" else set()
        action = str(settings.get("action", "click")).strip()
        if mode in ("cursor", "sequence") or action == "key":
            unused |= {"x_coord", "y_coord"}
        if action != "key":
            unused.add("key")
        if action != "hold":
            unused.add("hold_ms")
        for key, value in settings.items():
            if key in unused:
                continue
            result, error = self.parse_input(key, value)
            if error is not None:
                errors[key] = error
            else:
                parsed[key] = result

        if "x_coord" in parsed and "y_coord" in parsed:
            ok, error = self.validate_coordinate(
                parsed["x_coord"],
                parsed["y_coord"],
                screen_width,
                screen_height,
                screen_left,
                screen_top,
            )
            if not ok:
                errors["coordinates"] = error

        interval_ok = "interval" in parsed and "interval_unit" in parsed
        if interval_ok:
            ok, error = self.validate_interval(parsed["interval"], parsed["interval_unit"])
            if not ok:
                errors["interval"] = error
                interval_ok = False

        if interval_ok and "variation" in parsed:
            ok, error = self.validate_variation(
                parsed["variation"], parsed["interval"], parsed["interval_unit"]
            )
            if not ok:
                errors["variation"] = error

        if "burst_clicks" in parsed and "burst_pause" in parsed:
            ok, error = self.validate_burst_settings(parsed["burst_clicks"], parsed["burst_pause"])
            if not ok:
                errors["burst"] = error

        if "max_clicks" in parsed:
            ok, error = self.validate_clicks(parsed["max_clicks"])
            if not ok:
                errors["max_clicks"] = error

        if "auto_stop_minutes" in parsed:
            ok, error = self.validate_minutes(parsed["auto_stop_minutes"])
            if not ok:
                errors["auto_stop"] = error

        if "max_cps_ceiling" in parsed:
            ok, error = self.validate_max_cps(parsed["max_cps_ceiling"])
            if not ok:
                errors["max_cps_ceiling"] = error

        if mode == "sequence" and "sequence" in parsed:
            error = self._check_sequence(
                parsed["sequence"],
                ScreenBounds(screen_left, screen_top, screen_width, screen_height),
            )
            if error:
                errors["sequence"] = error
        elif mode == "sequence" and "sequence" not in errors:
            errors["sequence"] = "Add at least one point"
        repeat = parsed.get("sequence_repeat")
        if repeat is not None and not 0 <= repeat <= MAX_SEQUENCE_REPEAT:
            errors["sequence_repeat"] = (
                f"Must be between 0 and {MAX_SEQUENCE_REPEAT:,} (0 = until stopped)"
            )

        if parsed.get("action") in ("hold", "key") and mode == "sequence":
            errors["action"] = "Sequences always click; choose Click"
        hold = parsed.get("hold_ms")
        if hold is not None and not 0 < hold <= MAX_HOLD_MS:
            errors["hold_ms"] = f"Must be between 1 and {MAX_HOLD_MS:,} ms"
        if parsed.get("action") == "key" and "key" in parsed:
            key_error = _key_error(parsed["key"])
            if key_error:
                errors["key"] = key_error

        delay = parsed.get("start_delay_seconds")
        if delay is not None and not 0 <= delay <= MAX_START_DELAY_SECONDS:
            errors["start_delay_seconds"] = (
                f"Must be between 0 and {MAX_START_DELAY_SECONDS} seconds (0 = start at once)"
            )

        return {
            "valid": not errors,
            "errors": errors,
            "sanitized_settings": parsed,
        }

    @staticmethod
    def _check_sequence(steps: list[dict[str, Any]], bounds: ScreenBounds) -> str | None:
        """Error for a parsed sequence that can't run, or None."""
        if not steps:
            return "Add at least one point"
        if len(steps) > MAX_SEQUENCE_STEPS:
            return f"At most {MAX_SEQUENCE_STEPS} steps"
        for number, step in enumerate(steps, start=1):
            if not bounds.contains(step["x"], step["y"]):
                return (
                    f"Step {number} ({step['x']}, {step['y']}) is off screen. "
                    f"Valid range: {bounds.describe()}"
                )
        return None

    def get_all(self) -> dict[str, Any]:
        """Get all current settings"""
        return self._settings.copy()

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults"""
        self._settings = self._defaults()
        self._save_settings()
