"""
Unit tests for custom exceptions
Tests exception handling and user-friendly error messages
"""

import unittest

from autoclicker.core.exceptions import (
    AutoclickerError,
    ValidationError,
    CoordinateError,
    ClickEngineError,
    SettingsError,
    SafetyError,
    HotkeyError,
    PresetError,
    DependencyError,
    create_user_friendly_error,
    handle_autoclicker_error
)


class TestCustomExceptions(unittest.TestCase):
    """Test cases for custom exceptions"""

    def test_autoclicker_error_creation(self):
        """Test basic AutoclickerError creation"""
        error = AutoclickerError("Test error")
        self.assertEqual(error.message, "Test error")
        self.assertIsNone(error.details)

        error_with_details = AutoclickerError("Test error", "Additional details")
        self.assertEqual(error_with_details.message, "Test error")
        self.assertEqual(error_with_details.details, "Additional details")

    def test_validation_error(self):
        """Test ValidationError creation"""
        error = ValidationError("field_name", "invalid_value", "Field is invalid")
        self.assertEqual(error.field, "field_name")
        self.assertEqual(error.value, "invalid_value")
        self.assertEqual(error.reason, "Field is invalid")
        self.assertEqual(error.message, "Validation failed for field_name: Field is invalid")

    def test_coordinate_error(self):
        """Test CoordinateError creation"""
        error = CoordinateError(100, 200, "Out of bounds")
        self.assertEqual(error.x, 100)
        self.assertEqual(error.y, 200)
        self.assertEqual(error.reason, "Out of bounds")
        self.assertEqual(error.message, "Coordinate error at (100, 200): Out of bounds")

    def test_click_engine_error(self):
        """Test ClickEngineError creation"""
        error = ClickEngineError("perform_click", "Mouse not found")
        self.assertEqual(error.operation, "perform_click")
        self.assertEqual(error.reason, "Mouse not found")
        self.assertEqual(error.message, "Click engine error during perform_click: Mouse not found")

    def test_settings_error(self):
        """Test SettingsError creation"""
        error = SettingsError("interval", "Invalid value")
        self.assertEqual(error.setting_name, "interval")
        self.assertEqual(error.reason, "Invalid value")
        self.assertEqual(error.message, "Settings error for 'interval': Invalid value")

    def test_safety_error(self):
        """Test SafetyError creation"""
        error = SafetyError("click_limit", 1001, 1000)
        self.assertEqual(error.limit_type, "click_limit")
        self.assertEqual(error.value, 1001)
        self.assertEqual(error.limit, 1000)
        self.assertEqual(error.message, "Safety limit exceeded for click_limit: 1001 > 1000")

    def test_hotkey_error(self):
        """Test HotkeyError creation"""
        error = HotkeyError("F6", "Already in use")
        self.assertEqual(error.hotkey, "F6")
        self.assertEqual(error.reason, "Already in use")
        self.assertEqual(error.message, "Hotkey error for 'F6': Already in use")

    def test_preset_error(self):
        """Test PresetError creation"""
        error = PresetError("MyPreset", "save", "File not writable")
        self.assertEqual(error.preset_name, "MyPreset")
        self.assertEqual(error.operation, "save")
        self.assertEqual(error.reason, "File not writable")
        self.assertEqual(error.message, "Preset error for 'MyPreset' during save: File not writable")

    def test_dependency_error(self):
        """Test DependencyError creation"""
        error = DependencyError("pyautogui", "Version 0.9.50 required")
        self.assertEqual(error.dependency, "pyautogui")
        self.assertEqual(error.reason, "Version 0.9.50 required")
        self.assertEqual(error.message, "Dependency error for 'pyautogui': Version 0.9.50 required")

    def test_create_user_friendly_error_validation_error(self):
        """Test user-friendly error messages for ValidationError"""
        error = ValidationError("interval", 0, "Must be positive")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Please check your input for interval: Must be positive")

    def test_create_user_friendly_error_coordinate_error(self):
        """Test user-friendly error messages for CoordinateError"""
        error = CoordinateError(100, 200, "Out of screen bounds")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Please select valid coordinates: Out of screen bounds")

    def test_create_user_friendly_error_safety_error(self):
        """Test user-friendly error messages for SafetyError"""
        error = SafetyError("click_limit", 1001, 1000)
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Safety limit reached: Safety limit exceeded for click_limit: 1001 > 1000")

    def test_create_user_friendly_error_dependency_error(self):
        """Test user-friendly error messages for DependencyError"""
        error = DependencyError("keyboard", "Not installed")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Missing or incompatible dependency: Not installed")

    def test_create_user_friendly_error_value_error(self):
        """Test user-friendly error messages for ValueError"""
        error = ValueError("Invalid input format")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Invalid input format. Please check your entries.")

    def test_create_user_friendly_error_type_error(self):
        """Test user-friendly error messages for TypeError"""
        error = TypeError("Expected string, got int")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Invalid input format. Please check your entries.")

    def test_create_user_friendly_error_permission_error(self):
        """Test user-friendly error messages for PermissionError"""
        error = PermissionError("Access denied")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "Permission denied. Please run with appropriate permissions.")

    def test_create_user_friendly_error_os_error(self):
        """Test user-friendly error messages for OSError"""
        error = OSError("System error")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "System error occurred. Please check your system configuration.")

    def test_create_user_friendly_error_unknown(self):
        """Test user-friendly error messages for unknown exceptions"""
        error = RuntimeError("Something went wrong")
        message = create_user_friendly_error(error)
        self.assertEqual(message, "An unexpected error occurred: Something went wrong")

    def test_handle_autoclicker_error_with_logger(self):
        """Test error handling with logger"""
        error = ValidationError("test_field", "test_value", "Test reason")

        # Test without logger
        message = handle_autoclicker_error(error)
        self.assertIn("Validation failed", message)
        self.assertIn("Additional details", message)

        # Test with mock logger
        class MockLogger:
            def __init__(self):
                self.logged_messages = []

            def error(self, message, extra=None):
                self.logged_messages.append((message, extra))

        logger = MockLogger()
        message = handle_autoclicker_error(error, logger)

        self.assertIn("Validation failed", message)
        self.assertEqual(len(logger.logged_messages), 1)
        logged_message, logged_extra = logger.logged_messages[0]
        self.assertIn("Validation failed", logged_message)
        self.assertIn('error_type', logged_extra)

    def test_exception_inheritance(self):
        """Test that all exceptions inherit from AutoclickerError"""
        exceptions = [
            ValidationError("field", "value", "reason"),
            CoordinateError(0, 0, "reason"),
            ClickEngineError("operation", "reason"),
            SettingsError("setting", "reason"),
            SafetyError("type", 0, 1),
            HotkeyError("key", "reason"),
            PresetError("name", "operation", "reason"),
            DependencyError("dep", "reason")
        ]

        for exception in exceptions:
            self.assertIsInstance(exception, AutoclickerError)
            self.assertIsInstance(exception, Exception)


if __name__ == '__main__':
    unittest.main()
