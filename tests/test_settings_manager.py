"""
Unit tests for the SettingsManager class
Tests validation, sanitization, and persistence functionality
"""

import unittest
import tempfile
import os
import json
from unittest.mock import patch

from autoclicker.core.settings_manager import SettingsManager
from autoclicker.core.exceptions import ValidationError


class TestSettingsManager(unittest.TestCase):
    """Test cases for SettingsManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.settings_file = self.temp_file.name
        self.manager = SettingsManager(self.settings_file)

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.settings_file):
            os.unlink(self.settings_file)

    def test_default_settings(self):
        """Test that default settings are properly initialized"""
        settings = self.manager.get_all()

        self.assertEqual(settings['x_coord'], 100)
        self.assertEqual(settings['y_coord'], 100)
        self.assertEqual(settings['interval'], 1000)
        self.assertEqual(settings['interval_unit'], 'ms')
        self.assertEqual(settings['variation'], 0)
        self.assertEqual(settings['mouse_button'], 'left')
        self.assertEqual(settings['click_type'], 'single')
        self.assertEqual(settings['burst_clicks'], 1)
        self.assertEqual(settings['burst_pause'], 1000)
        self.assertEqual(settings['max_clicks'], 0)
        self.assertEqual(settings['auto_stop_minutes'], 0)

    def test_settings_persistence(self):
        """Test that settings are properly saved and loaded"""
        # Set some custom settings
        test_settings = {
            'x_coord': 500,
            'y_coord': 600,
            'interval': 500,
            'mouse_button': 'right'
        }

        for key, value in test_settings.items():
            self.manager.set(key, value)

        # Create a new manager instance to test loading
        new_manager = SettingsManager(self.settings_file)
        loaded_settings = new_manager.get_all()

        for key, expected_value in test_settings.items():
            self.assertEqual(loaded_settings[key], expected_value)

    def test_coordinate_validation(self):
        """Test coordinate validation"""
        # Valid coordinates
        self.assertTrue(self.manager.validate_coordinate(100, 100, 1920, 1080))

        # Invalid coordinates (negative)
        self.assertFalse(self.manager.validate_coordinate(-1, 100, 1920, 1080))
        self.assertFalse(self.manager.validate_coordinate(100, -1, 1920, 1080))

        # Invalid coordinates (too large)
        self.assertFalse(self.manager.validate_coordinate(2000, 100, 1920, 1080))
        self.assertFalse(self.manager.validate_coordinate(100, 1200, 1920, 1080))

    def test_interval_validation(self):
        """Test interval validation"""
        # Valid intervals
        valid, error = self.manager.validate_interval(500, 'ms')
        self.assertTrue(valid)
        self.assertEqual(error, "")

        valid, error = self.manager.validate_interval(1.5, 'seconds')
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid unit
        valid, error = self.manager.validate_interval(500, 'invalid')
        self.assertFalse(valid)
        self.assertIn("Invalid unit", error)

        # Invalid range for ms
        valid, error = self.manager.validate_interval(0.5, 'ms')
        self.assertFalse(valid)
        self.assertIn("between 1 and 60000", error)

        valid, error = self.manager.validate_interval(70000, 'ms')
        self.assertFalse(valid)
        self.assertIn("between 1 and 60000", error)

        # Invalid range for seconds
        valid, error = self.manager.validate_interval(0.0005, 'seconds')
        self.assertFalse(valid)
        self.assertIn("between 0.001 and 60", error)

        valid, error = self.manager.validate_interval(70, 'seconds')
        self.assertFalse(valid)
        self.assertIn("between 0.001 and 60", error)

    def test_clicks_validation(self):
        """Test click count validation"""
        # Valid click counts
        valid, error = self.manager.validate_clicks(100)
        self.assertTrue(valid)
        self.assertEqual(error, "")

        valid, error = self.manager.validate_clicks(0)
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid click counts
        valid, error = self.manager.validate_clicks(-1)
        self.assertFalse(valid)
        self.assertIn("cannot be negative", error)

        valid, error = self.manager.validate_clicks(1000001)
        self.assertFalse(valid)
        self.assertIn("cannot exceed 1,000,000", error)

        valid, error = self.manager.validate_clicks("not_a_number")
        self.assertFalse(valid)
        self.assertIn("must be an integer", error)

    def test_minutes_validation(self):
        """Test minutes validation"""
        # Valid minutes
        valid, error = self.manager.validate_minutes(30)
        self.assertTrue(valid)
        self.assertEqual(error, "")

        valid, error = self.manager.validate_minutes(0)
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid minutes
        valid, error = self.manager.validate_minutes(-1)
        self.assertFalse(valid)
        self.assertIn("cannot be negative", error)

        valid, error = self.manager.validate_minutes(1500)
        self.assertFalse(valid)
        self.assertIn("cannot exceed 24 hours", error)

        valid, error = self.manager.validate_minutes("not_a_number")
        self.assertFalse(valid)
        self.assertIn("must be an integer", error)

    def test_variation_validation(self):
        """Test variation validation"""
        # Valid variation
        valid, error = self.manager.validate_variation(50, 1000, 'ms')
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid variation
        valid, error = self.manager.validate_variation(-1, 1000, 'ms')
        self.assertFalse(valid)
        self.assertIn("cannot be negative", error)

        valid, error = self.manager.validate_variation(1000, 500, 'ms')
        self.assertFalse(valid)
        self.assertIn("cannot be greater than or equal to interval", error)

        valid, error = self.manager.validate_variation("not_a_number", 1000, 'ms')
        self.assertFalse(valid)
        self.assertIn("must be an integer", error)

    def test_burst_settings_validation(self):
        """Test burst mode settings validation"""
        # Valid burst settings
        valid, error = self.manager.validate_burst_settings(5, 1000)
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid burst clicks
        valid, error = self.manager.validate_burst_settings(0, 1000)
        self.assertFalse(valid)
        self.assertIn("must be a positive integer", error)

        valid, error = self.manager.validate_burst_settings(101, 1000)
        self.assertFalse(valid)
        self.assertIn("cannot exceed 100", error)

        # Invalid burst pause
        valid, error = self.manager.validate_burst_settings(5, -1)
        self.assertFalse(valid)
        self.assertIn("must be a non-negative number", error)

        valid, error = self.manager.validate_burst_settings(5, 70000)
        self.assertFalse(valid)
        self.assertIn("cannot exceed 60,000", error)

    def test_input_sanitization(self):
        """Test input sanitization"""
        # Test coordinate sanitization
        self.assertEqual(self.manager.sanitize_input('x_coord', 500), 500)
        self.assertEqual(self.manager.sanitize_input('x_coord', -50), 0)
        self.assertEqual(self.manager.sanitize_input('x_coord', 20000), 10000)
        self.assertEqual(self.manager.sanitize_input('x_coord', "invalid"), 100)  # Default

        # Test interval sanitization
        self.assertEqual(self.manager.sanitize_input('interval', 500), 500)
        self.assertEqual(self.manager.sanitize_input('interval', 0), 1)
        self.assertEqual(self.manager.sanitize_input('interval', 70000), 60000)

        # Test mouse button sanitization
        self.assertEqual(self.manager.sanitize_input('mouse_button', 'left'), 'left')
        self.assertEqual(self.manager.sanitize_input('mouse_button', 'invalid'), 'left')

        # Test click type sanitization
        self.assertEqual(self.manager.sanitize_input('click_type', 'double'), 'double')
        self.assertEqual(self.manager.sanitize_input('click_type', 'invalid'), 'single')

    def test_comprehensive_validation(self):
        """Test comprehensive validation of all settings"""
        # Valid settings
        valid_settings = {
            'x_coord': 500,
            'y_coord': 600,
            'interval': 1000,
            'interval_unit': 'ms',
            'variation': 100,
            'burst_clicks': 5,
            'burst_pause': 2000,
            'max_clicks': 1000,
            'auto_stop_minutes': 30
        }

        result = self.manager.validate_all_settings(valid_settings)
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['errors']), 0)

        # Invalid settings
        invalid_settings = {
            'x_coord': -50,
            'y_coord': 600,
            'interval': 70000,
            'interval_unit': 'invalid',
            'variation': -10,
            'burst_clicks': 150,
            'burst_pause': -500,
            'max_clicks': -100,
            'auto_stop_minutes': 2000
        }

        result = self.manager.validate_all_settings(invalid_settings)
        self.assertFalse(result['valid'])
        self.assertGreater(len(result['errors']), 0)

        # Check that sanitized settings are provided
        self.assertIn('sanitized_settings', result)
        sanitized = result['sanitized_settings']
        self.assertEqual(sanitized['x_coord'], 0)  # Clamped to 0
        self.assertEqual(sanitized['interval_unit'], 'ms')  # Reset to default


if __name__ == '__main__':
    unittest.main()
