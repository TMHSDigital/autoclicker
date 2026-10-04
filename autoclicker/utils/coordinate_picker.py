# SPDX-License-Identifier: CC-BY-NC-4.0
"""Named coordinate presets stored in settings."""

import logging

_log = logging.getLogger(__name__)


class PresetManager:
    """Manages coordinate presets"""

    def __init__(self, settings_manager):
        self.settings = settings_manager

    def save_preset(self, name: str, x: int, y: int) -> bool:
        """Save coordinates as a preset"""
        try:
            presets = self.settings.get("presets", {})
            presets[name] = {"x": x, "y": y}
            self.settings.set("presets", presets)
            return True
        except Exception as e:
            _log.warning("Failed to save preset: %s", e)
            return False

    def load_preset(self, name: str) -> tuple[int, int] | None:
        """Load coordinates from a preset"""
        try:
            presets = self.settings.get("presets", {})
            if name in presets:
                preset = presets[name]
                return preset["x"], preset["y"]
            return None
        except Exception as e:
            _log.warning("Failed to load preset: %s", e)
            return None

    def get_preset_names(self) -> list:
        """Get list of available preset names"""
        presets = self.settings.get("presets", {})
        return list(presets.keys())

    def delete_preset(self, name: str) -> bool:
        """Delete a preset"""
        try:
            presets = self.settings.get("presets", {})
            if name in presets:
                del presets[name]
                self.settings.set("presets", presets)
                return True
            return False
        except Exception as e:
            _log.warning("Failed to delete preset: %s", e)
            return False
