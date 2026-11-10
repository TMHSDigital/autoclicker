# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Custom exceptions for the autoclicker application
Provides structured error handling with specific exception types
"""

from typing import Any


class AutoclickerError(Exception):
    """Base exception for all autoclicker errors"""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class ValidationError(AutoclickerError):
    """Raised when input validation fails"""

    def __init__(self, field: str, value: Any, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        message = f"Validation failed for {field}: {reason}"
        super().__init__(message, f"Field: {field}, Value: {value}, Reason: {reason}")


class CoordinateError(AutoclickerError):
    """Raised when coordinate-related errors occur"""

    def __init__(self, x: int, y: int, reason: str):
        self.x = x
        self.y = y
        self.reason = reason
        message = f"Coordinate error at ({x}, {y}): {reason}"
        super().__init__(message, f"X: {x}, Y: {y}, Reason: {reason}")


class ClickEngineError(AutoclickerError):
    """Raised when click engine encounters errors"""

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        message = f"Click engine error during {operation}: {reason}"
        super().__init__(message, f"Operation: {operation}, Reason: {reason}")


class SettingsError(AutoclickerError):
    """Raised when settings-related errors occur"""

    def __init__(self, setting_name: str, reason: str):
        self.setting_name = setting_name
        self.reason = reason
        message = f"Settings error for '{setting_name}': {reason}"
        super().__init__(message, f"Setting: {setting_name}, Reason: {reason}")


class SafetyError(AutoclickerError):
    """Raised when safety limits are exceeded or violated"""

    def __init__(self, limit_type: str, value: Any, limit: Any):
        self.limit_type = limit_type
        self.value = value
        self.limit = limit
        self.reason = f"Safety limit exceeded for {limit_type}: {value} > {limit}"
        message = f"Safety limit exceeded for {limit_type}: {value} > {limit}"
        super().__init__(message, f"Type: {limit_type}, Value: {value}, Limit: {limit}")


class SystemTrayError(AutoclickerError):
    """Raised when system tray operations fail"""

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        message = f"System tray error during {operation}: {reason}"
        super().__init__(message, f"Operation: {operation}, Reason: {reason}")


class HotkeyError(AutoclickerError):
    """Raised when hotkey operations fail"""

    def __init__(self, hotkey: str, reason: str):
        self.hotkey = hotkey
        self.reason = reason
        message = f"Hotkey error for '{hotkey}': {reason}"
        super().__init__(message, f"Hotkey: {hotkey}, Reason: {reason}")


class PresetError(AutoclickerError):
    """Raised when preset operations fail"""

    def __init__(self, preset_name: str, operation: str, reason: str):
        self.preset_name = preset_name
        self.operation = operation
        self.reason = reason
        message = f"Preset error for '{preset_name}' during {operation}: {reason}"
        super().__init__(
            message,
            f"Preset: {preset_name}, Operation: {operation}, Reason: {reason}",
        )


class DependencyError(AutoclickerError):
    """Raised when required dependencies are missing or incompatible"""

    def __init__(self, dependency: str, reason: str):
        self.dependency = dependency
        self.reason = reason
        message = f"Dependency error for '{dependency}': {reason}"
        super().__init__(message, f"Dependency: {dependency}, Reason: {reason}")


def handle_autoclicker_error(error: AutoclickerError, logger=None) -> str:
    """Handle autoclicker errors with appropriate logging and user messages"""
    error_message = f"Error: {error.message}"

    if error.details:
        error_message += f"\nDetails: {error.details}"

    if logger:
        logger.error(
            f"AutoclickerError: {error.message}",
            extra={
                "error_type": type(error).__name__,
                "details": error.details,
            },
        )

    return error_message


def create_user_friendly_error(error: Exception) -> str:
    """Say why a run couldn't start, in words a user can act on."""
    if isinstance(error, ValidationError):
        field = error.field.replace("_", " ").capitalize()
        return f"Couldn't start. {field}: {error.reason}"
    if isinstance(error, CoordinateError):
        return f"Couldn't start. Target point: {error.reason}"
    if isinstance(error, SafetyError):
        return f"Couldn't start: {error.reason}"
    if isinstance(error, DependencyError):
        return f"Couldn't start. {error.dependency} is missing or the wrong version: {error.reason}"
    detail = str(error) or type(error).__name__
    if isinstance(error, (ValueError, TypeError)):
        return f"Couldn't start: a setting has a value the app can't read ({detail})."
    if isinstance(error, PermissionError):
        return f"Couldn't start: Windows denied access ({detail})."
    if isinstance(error, OSError):
        return f"Couldn't start: Windows reported an error ({detail})."
    return f"Couldn't start: {detail}"
