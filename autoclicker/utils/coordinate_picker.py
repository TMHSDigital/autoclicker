# SPDX-License-Identifier: CC-BY-NC-4.0
"""Named profiles stored in settings (under the historical ``presets`` key).

A profile always has a target point (``x``/``y``) and may carry any of the
click settings in PROFILE_KEYS. Presets saved by older versions hold only the
point, so they load as coordinate-only profiles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# Click settings a profile restores, in addition to the target point.
PROFILE_KEYS = (
    "target_mode",
    "interval",
    "interval_unit",
    "variation",
    "mouse_button",
    "click_type",
    "burst_clicks",
    "burst_pause",
    "max_clicks",
    "auto_stop_minutes",
    "sequence",
    "sequence_repeat",
)

EXPORT_FORMAT = "windows-autoclicker-profiles"
EXPORT_VERSION = 1


@dataclass
class ImportResult:
    added: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # existing names kept
    invalid: list[str] = field(default_factory=list)  # entries that failed validation


def describe_profile(profile: dict[str, Any]) -> str:
    """One-line summary, e.g. '(800, 600) · every 100 ms ±10 · left double'."""
    parts = []
    if profile.get("target_mode") == "cursor":
        parts.append("at the cursor")
    elif profile.get("target_mode") == "sequence":
        count = len(profile.get("sequence") or [])
        parts.append(f"sequence of {count} point{'s' if count != 1 else ''}")
    else:
        parts.append(f"({profile.get('x')}, {profile.get('y')})")
    if "interval" in profile:
        unit = "s" if profile.get("interval_unit") == "seconds" else "ms"
        every = f"every {profile['interval']} {unit}"
        if profile.get("variation"):
            every += f" ±{profile['variation']} ms"
        parts.append(every)
    if "mouse_button" in profile or "click_type" in profile:
        parts.append(f"{profile.get('mouse_button', 'left')} {profile.get('click_type', 'single')}")
    burst = profile.get("burst_clicks")
    if isinstance(burst, int) and burst > 1:
        parts.append(f"burst {burst} x {profile.get('burst_pause', 0)} ms")
    max_clicks = profile.get("max_clicks")
    if isinstance(max_clicks, int) and max_clicks > 0:
        parts.append(f"stop after {max_clicks:,} clicks")
    minutes = profile.get("auto_stop_minutes")
    if isinstance(minutes, int) and minutes > 0:
        parts.append(f"stop after {minutes} min")
    return " · ".join(parts)


class PresetManager:
    """Manages named profiles (coordinates plus optional click settings)."""

    def __init__(self, settings_manager):
        self.settings = settings_manager

    def _profiles(self) -> dict[str, dict[str, Any]]:
        stored = self.settings.get("presets", {})
        return dict(stored) if isinstance(stored, dict) else {}

    # -- coordinates only (kept for callers that only need the point) -----

    def save_preset(self, name: str, x: int, y: int) -> bool:
        """Save just a target point under ``name``."""
        return self.save_profile(name, {"x": x, "y": y})

    def load_preset(self, name: str) -> tuple[int, int] | None:
        """The target point of a profile, or None."""
        profile = self.load_profile(name)
        if profile is None:
            return None
        return profile["x"], profile["y"]

    # -- profiles ----------------------------------------------------------

    def save_profile(self, name: str, values: dict[str, Any]) -> bool:
        """Store a profile; ``values`` needs ``x``/``y``, other keys outside PROFILE_KEYS are dropped."""
        try:
            profile = {"x": int(values["x"]), "y": int(values["y"])}
            profile.update({k: values[k] for k in PROFILE_KEYS if k in values})
            presets = self._profiles()  # never mutate the stored dict
            presets[name] = profile
            self.settings.set("presets", presets)
            return True
        except Exception as e:
            _log.warning("Failed to save profile: %s", e)
            return False

    def load_profile(self, name: str) -> dict[str, Any] | None:
        """A copy of the stored profile, or None if missing or malformed."""
        profile = self._profiles().get(name)
        if not isinstance(profile, dict) or "x" not in profile or "y" not in profile:
            return None
        return dict(profile)

    def has_profile(self, name: str) -> bool:
        return name in self._profiles()

    def get_preset_names(self) -> list[str]:
        return list(self._profiles().keys())

    def delete_preset(self, name: str) -> bool:
        try:
            presets = self._profiles()
            if name in presets:
                del presets[name]
                self.settings.set("presets", presets)
                return True
            return False
        except Exception as e:
            _log.warning("Failed to delete profile: %s", e)
            return False

    # -- import / export ---------------------------------------------------

    def export_profiles(self, path: str | Path) -> int:
        """Write every profile to a JSON file. Returns how many were written."""
        profiles = self._profiles()
        payload = {"format": EXPORT_FORMAT, "version": EXPORT_VERSION, "profiles": profiles}
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return len(profiles)

    @staticmethod
    def read_profiles_file(path: str | Path) -> dict[str, Any]:
        """Profiles from an export file. Raises ValueError for anything else."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError(f"Could not read the file: {e}") from e
        if not isinstance(data, dict) or data.get("format") != EXPORT_FORMAT:
            raise ValueError("This is not a Windows Autoclicker profiles file.")
        profiles = data.get("profiles")
        if not isinstance(profiles, dict):
            raise ValueError("The file has no profiles.")
        return profiles

    def import_profiles(self, profiles: dict[str, Any], *, replace_existing: bool) -> ImportResult:
        """Add profiles read from a file, validating every value."""
        result = ImportResult()
        current = self._profiles()
        for name, raw in profiles.items():
            clean = self._clean_profile(raw)
            if not isinstance(name, str) or not name.strip() or clean is None:
                result.invalid.append(str(name))
                continue
            if name in current and not replace_existing:
                result.skipped.append(name)
                continue
            (result.replaced if name in current else result.added).append(name)
            current[name] = clean
        if result.added or result.replaced:
            self.settings.set("presets", current)
        return result

    def _clean_profile(self, raw: Any) -> dict[str, Any] | None:
        """Parse an imported profile with the settings parser; None if anything is invalid."""
        if not isinstance(raw, dict):
            return None
        clean: dict[str, Any] = {}
        for key in ("x", "y", *PROFILE_KEYS):
            if key not in raw:
                continue
            setting = {"x": "x_coord", "y": "y_coord"}.get(key, key)
            value, error = self.settings.parse_input(setting, raw[key])
            if error is not None:
                return None
            clean[key] = value
        if "x" not in clean or "y" not in clean:
            return None
        return clean
