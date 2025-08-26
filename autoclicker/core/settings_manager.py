"""
Settings management for the autoclicker application
Handles loading, saving, and validation of user settings
"""

import json
import os
from typing import Dict, Any, Optional

from .exceptions import ValidationError, SettingsError, create_user_friendly_error


class SettingsManager:
    """Manages application settings with validation and persistence"""

    DEFAULT_SETTINGS = {
        'x_coord': 100,
        'y_coord': 100,
        'interval': 1000,
        'interval_unit': 'ms',
        'variation': 0,
        'mouse_button': 'left',
        'click_type': 'single',
        'burst_clicks': 1,
        'burst_pause': 1000,
        'max_clicks': 0,
        'auto_stop_minutes': 0,
        'presets': {}
    }

    def __init__(self, settings_file: str = 'autoclicker_settings.json'):
        self.settings_file = settings_file
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file or return defaults"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to handle missing keys
                    return {**self.DEFAULT_SETTINGS, **loaded_settings}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load settings file: {e}")

        return self.DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> None:
        """Save current settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save settings file: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save"""
        self._settings[key] = value
        self._save_settings()

    def update(self, settings_dict: Dict[str, Any]) -> None:
        """Update multiple settings and save"""
        self._settings.update(settings_dict)
        self._save_settings()

    def validate_coordinate(self, x: int, y: int, screen_width: int, screen_height: int) -> tuple[bool, str]:
        """Validate that coordinates are within screen bounds"""
        try:
            if not (0 <= x <= screen_width and 0 <= y <= screen_height):
                raise ValidationError('coordinates', f"({x}, {y})", f"Coordinates ({x}, {y}) are outside screen bounds ({screen_width}x{screen_height})")
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_interval(self, interval: float, unit: str) -> tuple[bool, str]:
        """Validate click interval settings with detailed error message"""
        try:
            if unit not in ['ms', 'seconds']:
                raise ValidationError('interval_unit', unit, f"Invalid unit: {unit}. Must be 'ms' or 'seconds'")

            if unit == 'ms':
                if not (1 <= interval <= 60000):
                    raise ValidationError('interval', interval, f"Interval in milliseconds must be between 1 and 60000 (1ms to 1 minute)")
            elif unit == 'seconds':
                if not (0.001 <= interval <= 60):
                    raise ValidationError('interval', interval, f"Interval in seconds must be between 0.001 and 60 (0.001s to 1 minute)")

            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_clicks(self, clicks: int) -> tuple[bool, str]:
        """Validate click count settings with detailed error message"""
        try:
            if clicks < 0:
                raise ValidationError('max_clicks', clicks, "Click count cannot be negative")
            if clicks > 1000000:  # Reasonable upper limit to prevent system overload
                raise ValidationError('max_clicks', clicks, "Click count cannot exceed 1,000,000 to prevent system overload")
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_minutes(self, minutes: int) -> tuple[bool, str]:
        """Validate time settings with detailed error message"""
        try:
            if minutes < 0:
                raise ValidationError('auto_stop_minutes', minutes, "Minutes cannot be negative")
            if minutes > 1440:  # 24 hours max
                raise ValidationError('auto_stop_minutes', minutes, "Auto-stop time cannot exceed 24 hours (1440 minutes)")
            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_variation(self, variation: int, interval: float, unit: str) -> tuple[bool, str]:
        """Validate random variation settings"""
        try:
            if variation < 0:
                raise ValidationError('variation', variation, "Variation cannot be negative")

            # Convert interval to milliseconds for comparison
            interval_ms = interval if unit == 'ms' else interval * 1000

            if variation >= interval_ms:
                raise ValidationError('variation', variation, f"Variation ({variation}ms) cannot be greater than or equal to interval ({interval_ms}ms)")

            return True, ""
        except ValidationError as e:
            return False, e.reason

    def validate_burst_settings(self, burst_clicks: int, burst_pause: float) -> tuple[bool, str]:
        """Validate burst mode settings"""
        try:
            if burst_clicks < 1:
                raise ValidationError('burst_clicks', burst_clicks, "Burst clicks must be a positive integer")
            if burst_clicks > 100:
                raise ValidationError('burst_clicks', burst_clicks, "Burst clicks cannot exceed 100 to prevent system overload")

            if burst_pause < 0:
                raise ValidationError('burst_pause', burst_pause, "Burst pause must be a non-negative number")
            if burst_pause > 60000:  # 1 minute max
                raise ValidationError('burst_pause', burst_pause, "Burst pause cannot exceed 60,000 milliseconds (1 minute)")

            return True, ""
        except ValidationError as e:
            return False, e.reason

    def sanitize_input(self, key: str, value: Any) -> Any:
        """Sanitize and validate input values"""
        try:
            # Handle empty strings and None values
            if value is None or (isinstance(value, str) and value.strip() == ""):
                return self.DEFAULT_SETTINGS.get(key, 0)

            # Convert string inputs to appropriate types
            if isinstance(value, str):
                value = value.strip()

            if key in ['x_coord', 'y_coord']:
                return max(0, min(int(float(value)), 10000))  # Reasonable coordinate bounds
            elif key in ['interval']:
                return max(1, min(float(value), 60000))  # 1ms to 1 minute
            elif key in ['variation', 'burst_clicks', 'max_clicks', 'auto_stop_minutes']:
                return max(0, int(float(value)))
            elif key in ['burst_pause']:
                return max(0, min(float(value), 60000))  # Max 1 minute
            elif key in ['mouse_button']:
                if str(value) not in ['left', 'right', 'middle']:
                    return 'left'
                return str(value)
            elif key in ['click_type']:
                if str(value) not in ['single', 'double']:
                    return 'single'
                return str(value)
            elif key in ['interval_unit']:
                if str(value) not in ['ms', 'seconds']:
                    return 'ms'
                return str(value)
        except (ValueError, TypeError):
            # Return default values if conversion fails
            return self.DEFAULT_SETTINGS.get(key, 0)

        return value

    def validate_all_settings(self, settings: Dict[str, Any], screen_width: int = 1920, screen_height: int = 1080) -> Dict[str, Any]:
        """Validate all settings and return sanitized versions with error messages"""
        errors = {}
        sanitized = {}

        # First, sanitize all values to handle string inputs from UI
        sanitized_settings = {}
        for key, value in settings.items():
            sanitized_settings[key] = self.sanitize_input(key, value)

        # Now validate using sanitized values
        # Validate coordinates
        x_coord = sanitized_settings.get('x_coord', 100)
        y_coord = sanitized_settings.get('y_coord', 100)
        x_valid, x_error = self.validate_coordinate(x_coord, y_coord, screen_width, screen_height)
        if not x_valid:
            errors['coordinates'] = x_error

        # Validate interval
        interval = sanitized_settings.get('interval', 1000)
        unit = sanitized_settings.get('interval_unit', 'ms')
        interval_valid, interval_error = self.validate_interval(interval, unit)
        if not interval_valid:
            errors['interval'] = interval_error

        # Validate variation
        variation = sanitized_settings.get('variation', 0)
        variation_valid, variation_error = self.validate_variation(variation, interval, unit)
        if not variation_valid:
            errors['variation'] = variation_error

        # Validate burst settings
        burst_clicks = sanitized_settings.get('burst_clicks', 1)
        burst_pause = sanitized_settings.get('burst_pause', 1000)
        burst_valid, burst_error = self.validate_burst_settings(burst_clicks, burst_pause)
        if not burst_valid:
            errors['burst'] = burst_error

        # Validate safety settings
        max_clicks = sanitized_settings.get('max_clicks', 0)
        clicks_valid, clicks_error = self.validate_clicks(max_clicks)
        if not clicks_valid:
            errors['max_clicks'] = clicks_error

        auto_stop = sanitized_settings.get('auto_stop_minutes', 0)
        time_valid, time_error = self.validate_minutes(auto_stop)
        if not time_valid:
            errors['auto_stop'] = time_error

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'sanitized_settings': sanitized_settings
        }

    def get_all(self) -> Dict[str, Any]:
        """Get all current settings"""
        return self._settings.copy()

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults"""
        self._settings = self.DEFAULT_SETTINGS.copy()
        self._save_settings()
