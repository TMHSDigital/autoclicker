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
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import fields
from .exceptions import ValidationError
from .schedule import parse_start_at
from .screen import ScreenBounds
from .settings_paths import LEGACY_FILENAME, atomic_write_json, resolve_settings_file

_log = logging.getLogger(__name__)

# Highest runaway-guard ceiling accepted, in clicks per second.
MAX_CPS_CEILING = 10_000

# Fields parsed from free-text UI entries. Values are parsed, never clamped or
# defaulted: a value that does not parse, or is out of range, is an error.
# Declared once in core/fields.py (#169).
_INT_FIELDS = fields.keys_of("int")
_FLOAT_FIELDS = fields.keys_of("float")
_CHOICE_FIELDS: dict[str, tuple[str, ...]] = fields.CHOICES

# Human-readable names for validation error keys, used in error dialogs: the
# fields' own labels plus keys that only errors use.
FIELD_LABELS: dict[str, str] = {
    **fields.LABELS,
    "coordinates": "Coordinates",
    "burst": "Burst",
    "auto_stop": "Auto-stop",
}

_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

# Largest search margin around a captured image, in pixels (see core/image_match.py).
MAX_IMAGE_MARGIN = 2000
# Highest per-channel color difference allowed when matching an image.
MAX_IMAGE_TOLERANCE = 64
# Longest an image run may go without seeing its image before it stops (#174).
MAX_IMAGE_MISSING_SECONDS = 86_400
# Farthest a click may land from its target with click spread on, in pixels.
MAX_CLICK_SPREAD = 50

# Longest mouse-button hold, in milliseconds.
MAX_HOLD_MS = 60_000

# Ranges the validators enforce, named once (#169).
MAX_INTERVAL_MS = 60_000
MIN_INTERVAL_SECONDS = 0.001
MAX_INTERVAL_SECONDS = 60
MAX_CLICKS = 1_000_000
MAX_AUTO_STOP_MINUTES = 1440
MAX_BURST_CLICKS = 100
MAX_BURST_PAUSE_MS = 60_000

# Profiles and command-line overrides call the target point x/y; settings
# call it x_coord/y_coord. setting_key() translates (#169).
POINT_KEYS = {"x": "x_coord", "y": "y_coord"}


def setting_key(key: str) -> str:
    """The settings key for a profile-shaped key (``x`` -> ``x_coord``)."""
    return POINT_KEYS.get(key, key)


# Longest countdown before a Start-button run begins, in seconds.
MAX_START_DELAY_SECONDS = 60

# Sequence mode limits: steps per round, rounds per run, wait between steps (ms).
MAX_SEQUENCE_STEPS = 50
MAX_SEQUENCE_REPEAT = 1_000_000
MAX_STEP_DELAY_MS = 60_000
# Longest a wait step may wait before its on_timeout applies (0 = no timeout).
MAX_STEP_TIMEOUT_MS = 3_600_000

# Fields of one sequence step: the setting whose parser reads it (None: parsed
# here) and its name in error messages.
_STEP_FIELDS: dict[str, tuple[str | None, str]] = {
    "x": ("x_coord", "X"),
    "y": ("y_coord", "Y"),
    "button": ("mouse_button", "button"),
    "click_type": ("click_type", "click type"),
    "delay_ms": ("burst_pause", "wait"),
    "hold_ms": ("hold_ms", "hold"),
    "key": ("key", "key"),
    "color": ("condition_color", "color"),
    "tolerance": ("condition_tolerance", "tolerance"),
    "image_path": ("image_path", "image"),
    "image_region": ("image_region", "image"),
    "image_tolerance": ("image_tolerance", "tolerance"),
    "timeout_ms": ("burst_pause", "timeout"),
    "on_timeout": (None, "on timeout"),
    "click": (None, "click"),
}
# What each step type does (#119) and the fields it keeps; a step without a
# type is a click, so sequences saved before step types load unchanged.
STEP_TYPES = ("click", "hold", "key", "wait_image", "wait_pixel")
_STEP_TYPE_FIELDS = {
    "click": ("x", "y", "button", "click_type", "delay_ms"),
    "hold": ("x", "y", "button", "hold_ms", "delay_ms"),
    "key": ("key", "delay_ms"),
    "wait_image": (
        "image_path",
        "image_region",
        "image_tolerance",
        "timeout_ms",
        "on_timeout",
        "click",
        "button",
        "click_type",
        "delay_ms",
    ),
    "wait_pixel": ("x", "y", "color", "tolerance", "timeout_ms", "on_timeout", "delay_ms"),
}
_STEP_DEFAULTS: dict[str, Any] = {
    "button": "left",
    "click_type": "single",
    "delay_ms": 0,
    "tolerance": 16,
    "image_tolerance": 0,
    "timeout_ms": 0,
    "on_timeout": "stop",
    "click": False,
}
# What a step is missing when a field without a default is left out.
_STEP_MISSING = {
    "key": "Enter a key such as F5, space or ctrl+r",
    "hold_ms": f"Must be between 1 and {MAX_HOLD_MS:,} ms",
    "color": "Pick the pixel to wait for",
    "image_path": "Capture an image first",
    "image_region": "Capture an image first",
}


def _step_field_error(field: str, value: Any) -> str | None:
    """Why a parsed step field is out of range, or None."""
    if field == "key":
        return _key_error(value)
    if field == "hold_ms" and not 0 < value <= MAX_HOLD_MS:
        return f"Must be between 1 and {MAX_HOLD_MS:,} ms"
    if field == "delay_ms" and not 0 <= value <= MAX_STEP_DELAY_MS:
        return f"Must be 0 to {MAX_STEP_DELAY_MS:,} ms"
    if field == "timeout_ms" and not 0 <= value <= MAX_STEP_TIMEOUT_MS:
        return f"Must be 0 to {MAX_STEP_TIMEOUT_MS:,} ms (0 = wait until stopped)"
    if field == "color" and not _COLOR.match(str(value)):
        return "Must look like #3a7bd5"
    if field == "tolerance" and not 0 <= value <= 255:
        return "Must be between 0 and 255"
    if field == "image_tolerance" and not 0 <= value <= MAX_IMAGE_TOLERANCE:
        return f"Must be between 0 and {MAX_IMAGE_TOLERANCE} (0 = exact)"
    if field == "image_path" and not str(value).strip():
        return "Capture an image first"
    return None


# Settings whose stored value must be of a given JSON type; anything else falls
# back to the default for that key on load. Numeric fields also accept strings
# because the UI stores what was typed, and validation reports bad values.
_BOOL_KEYS = fields.keys_of("bool") | {"minimize_to_tray"}
_DICT_KEYS = frozenset({"hotkeys", "presets"})
_LIST_KEYS = fields.keys_of("list")
_STR_KEYS = fields.keys_of("str") | frozenset(_CHOICE_FIELDS)
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


def allowed_actions(mode: str) -> tuple[str, ...]:
    """What each click may do in a target mode. Validation and the form share it (#102)."""
    if mode == "sequence":
        return ("click",)
    if mode == "image":
        return ("click", "hold")
    return ("click", "hold", "key")


def uses_point(mode: str, action: str) -> bool:
    """True when the run clicks the X/Y point: Fixed mode, unless it presses a key."""
    return mode == "fixed" and action != "key"


_ACTION_ERRORS = {
    "sequence": "Sequences always click; choose Click",
    "image": "Image targets click or hold; choose Click or Hold",
}


class SettingsManager:
    """Manages application settings with validation and persistence"""

    DEFAULT_SETTINGS = {
        # The run settings, from core/fields.py (#169), then the app's own.
        **copy.deepcopy(fields.DEFAULTS),
        "minimize_to_tray": True,
        # None until the user has been asked once; then True or False.
        "check_for_updates": None,
        "last_update_check": 0,
        "first_run_hint_dismissed": False,
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
        # The last failed save's message (None once a save works again), and a
        # hook the UI sets to hear about each new failure (#151).
        self.save_error: str | None = None
        self.on_save_error: Callable[[str], None] | None = None
        # True when the file exists but could not be read (say, locked): saving
        # would replace settings we never saw, so this session does not save.
        self._read_failed = False
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
        except UnicodeDecodeError as e:
            # Saved as ANSI or UTF-16, say after editing in Notepad (#146).
            _log.warning("Settings file is not UTF-8 text: %s", e)
            self._quarantine("is not UTF-8 text")
            return self._defaults()
        except OSError as e:
            _log.warning("Could not load settings file: %s", e)
            self._read_failed = True
            self.load_warning = (
                "Could not read the settings file; using defaults. "
                "Changes in this session will not be saved"
            )
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

    def _save_settings(self) -> bool:
        """Save current settings to file atomically. False (and reported) on failure."""
        if self._read_failed:
            return self._save_failed(
                "Settings not saved: the settings file could not be read at startup"
            )
        try:
            atomic_write_json(Path(self.settings_file), self._settings)
        except OSError as e:
            _log.warning("Could not save settings file: %s", e)
            return self._save_failed(f"Settings not saved: {e.strerror or e}")
        self.save_error = None
        return True

    def _save_failed(self, message: str) -> bool:
        """Remember a failed save and tell the UI, once per new problem (#151)."""
        if message != self.save_error:
            self.save_error = message
            if self.on_save_error is not None:
                try:
                    self.on_save_error(message)
                except Exception:
                    _log.exception("Settings save-error callback failed")
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Set a setting value and save. False if the save failed."""
        self._settings[key] = value
        return self._save_settings()

    def update(self, settings_dict: dict[str, Any]) -> bool:
        """Update multiple settings and save. False if the save failed."""
        self._settings.update(settings_dict)
        return self._save_settings()

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
                if not (0 <= interval <= MAX_INTERVAL_MS):
                    raise ValidationError(
                        "interval",
                        interval,
                        f"Interval in milliseconds must be between 0 and {MAX_INTERVAL_MS}"
                        " (0 = no delay between bursts)",
                    )
            elif unit == "seconds":
                if not (MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS):
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
            if clicks > MAX_CLICKS:
                raise ValidationError(
                    "max_clicks",
                    clicks,
                    f"Click count cannot exceed {MAX_CLICKS:,} to prevent system overload",
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
            if minutes > MAX_AUTO_STOP_MINUTES:
                raise ValidationError(
                    "auto_stop_minutes",
                    minutes,
                    f"Auto-stop time cannot exceed 24 hours ({MAX_AUTO_STOP_MINUTES} minutes)",
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
            if burst_clicks > MAX_BURST_CLICKS:
                raise ValidationError(
                    "burst_clicks",
                    burst_clicks,
                    f"Burst clicks cannot exceed {MAX_BURST_CLICKS} to prevent system overload",
                )

            if burst_pause < 0:
                raise ValidationError(
                    "burst_pause", burst_pause, "Burst pause must be a non-negative number"
                )
            if burst_pause > MAX_BURST_PAUSE_MS:
                raise ValidationError(
                    "burst_pause",
                    burst_pause,
                    f"Burst pause cannot exceed {MAX_BURST_PAUSE_MS:,} milliseconds (1 minute)",
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
        if key == "image_region":
            if (
                not isinstance(value, list)
                or len(value) != 4
                or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)
                or value[2] <= 0
                or value[3] <= 0
            ):
                return None, "Capture the image again"
            return list(value), None
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
        """Parse a list of sequence steps; missing button/type/delay get defaults.

        Each step keeps only the fields its type uses. Click steps are stored
        without a ``type``, exactly as before step types existed (#119).
        """
        if not isinstance(value, list):
            return None, "Must be a list of steps"
        steps = []
        for number, raw in enumerate(value, start=1):
            if not isinstance(raw, dict):
                return None, f"Step {number} is not a step"
            kind = raw.get("type", "click")
            if kind not in STEP_TYPES:
                return None, f"Step {number} type: Must be one of: {', '.join(STEP_TYPES)}"
            step: dict[str, Any] = {}
            for field in _STEP_TYPE_FIELDS[kind]:
                setting, label = _STEP_FIELDS[field]
                if field not in raw:
                    if field in _STEP_DEFAULTS:
                        step[field] = _STEP_DEFAULTS[field]
                        continue
                    if field in ("x", "y"):
                        return None, f"Step {number} has no {label}"
                    return None, f"Step {number} {label}: {_STEP_MISSING[field]}"
                value = raw[field]
                if field == "on_timeout":
                    ok = value in ("stop", "skip")
                    parsed, error = value, None if ok else "Must be one of: stop, skip"
                elif field == "click":
                    ok = isinstance(value, bool)
                    parsed, error = value, None if ok else "Must be true or false"
                else:
                    assert setting is not None
                    parsed, error = self.parse_input(setting, value)
                if error is None:
                    error = _step_field_error(field, parsed)
                if error is not None:
                    return None, f"Step {number} {label}: {error}"
                step[field] = parsed
            if kind == "wait_image" and not step["click"]:
                del step["button"], step["click_type"]  # used only to click the match
            if kind != "click":
                step = {"type": kind, **step}
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
        if mode != "image":
            unused |= {"image_path", "image_region"}
        action = str(settings.get("action", "click")).strip()
        if not uses_point(mode, action):
            unused |= {"x_coord", "y_coord"}
        if action != "key":
            unused.add("key")
        if mode == "cursor" or action == "key":
            unused.add("click_spread")  # the cursor isn't moved; keys have no point
        if action != "hold":
            unused.add("hold_ms")
        if str(settings.get("condition", "none")).strip() == "none":
            unused |= {"condition_x", "condition_y", "condition_color", "condition_tolerance"}
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

        if parsed.get("condition") in ("wait", "stop"):
            cx, cy = parsed.get("condition_x"), parsed.get("condition_y")
            desktop = ScreenBounds(screen_left, screen_top, screen_width, screen_height)
            if cx is not None and cy is not None and not desktop.contains(cx, cy):
                errors["condition_x"] = f"({cx}, {cy}) is off screen"
            color = parsed.get("condition_color")
            if color is not None and not _COLOR.match(str(color)):
                errors["condition_color"] = "Must look like #3a7bd5"
            tolerance = parsed.get("condition_tolerance")
            if tolerance is not None and not 0 <= tolerance <= 255:
                errors["condition_tolerance"] = "Must be between 0 and 255"

        if mode == "image":
            if not str(parsed.get("image_path") or "").strip():
                errors["image_path"] = "Capture an image first"
            region = parsed.get("image_region")
            if region:
                area = ScreenBounds(*region)
                desktop = ScreenBounds(screen_left, screen_top, screen_width, screen_height)
                if not (
                    desktop.contains(area.left, area.top)
                    and desktop.contains(area.right - 1, area.bottom - 1)
                ):
                    errors["image_region"] = (
                        "The search area is off screen; capture the image again"
                    )
            elif "image_region" not in errors:
                errors["image_region"] = "Capture the image again"
        margin = parsed.get("image_margin")
        if margin is not None and not 0 <= margin <= MAX_IMAGE_MARGIN:
            errors["image_margin"] = f"Must be between 0 and {MAX_IMAGE_MARGIN:,} px"
        image_tolerance = parsed.get("image_tolerance")
        if image_tolerance is not None and not 0 <= image_tolerance <= MAX_IMAGE_TOLERANCE:
            errors["image_tolerance"] = f"Must be between 0 and {MAX_IMAGE_TOLERANCE} (0 = exact)"
        missing = parsed.get("image_missing_stop_seconds")
        if missing is not None and not 0 <= missing <= MAX_IMAGE_MISSING_SECONDS:
            errors["image_missing_stop_seconds"] = (
                f"Must be between 0 and {MAX_IMAGE_MISSING_SECONDS:,} seconds (0 = keep waiting)"
            )
        spread = parsed.get("click_spread")
        if spread is not None and not 0 <= spread <= MAX_CLICK_SPREAD:
            errors["click_spread"] = (
                f"Must be between 0 and {MAX_CLICK_SPREAD} px (0 = exact point)"
            )

        if parsed.get("action", "click") not in allowed_actions(mode) and mode in _ACTION_ERRORS:
            errors["action"] = _ACTION_ERRORS[mode]
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
        start_at = str(parsed.get("start_at") or "").strip()
        if start_at and parse_start_at(start_at) is None:
            errors["start_at"] = "Use a 24-hour time such as 09:30, or leave it blank"
        stop_at = str(parsed.get("stop_at") or "").strip()
        if stop_at and parse_start_at(stop_at) is None:
            errors["stop_at"] = "Use a 24-hour time such as 17:30, or leave it blank"

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
            if "x" not in step:
                continue  # a key step has no point
            if not bounds.contains(step["x"], step["y"]):
                return (
                    f"Step {number} ({step['x']}, {step['y']}) is off screen. "
                    f"Valid range: {bounds.describe()}"
                )
        return None

    def get_all(self) -> dict[str, Any]:
        """Get all current settings"""
        return self._settings.copy()
