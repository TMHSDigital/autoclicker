"""
Unit tests for the SettingsManager class
Tests validation, sanitization, and persistence functionality
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from autoclicker.core.settings_manager import SettingsManager


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

        self.assertEqual(settings["x_coord"], 100)
        self.assertEqual(settings["y_coord"], 100)
        self.assertEqual(settings["interval"], 1000)
        self.assertEqual(settings["interval_unit"], "ms")
        self.assertEqual(settings["variation"], 0)
        self.assertEqual(settings["mouse_button"], "left")
        self.assertEqual(settings["click_type"], "single")
        self.assertEqual(settings["burst_clicks"], 1)
        self.assertEqual(settings["burst_pause"], 1000)
        self.assertEqual(settings["max_clicks"], 0)
        self.assertEqual(settings["auto_stop_minutes"], 0)

    def test_settings_persistence(self):
        """Test that settings are properly saved and loaded"""
        # Set some custom settings
        test_settings = {"x_coord": 500, "y_coord": 600, "interval": 500, "mouse_button": "right"}

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
        valid, error = self.manager.validate_coordinate(100, 100, 1920, 1080)
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid coordinates (negative)
        valid, _ = self.manager.validate_coordinate(-1, 100, 1920, 1080)
        self.assertFalse(valid)
        valid, _ = self.manager.validate_coordinate(100, -1, 1920, 1080)
        self.assertFalse(valid)

        # Invalid coordinates (too large)
        valid, _ = self.manager.validate_coordinate(2000, 100, 1920, 1080)
        self.assertFalse(valid)
        valid, _ = self.manager.validate_coordinate(100, 1200, 1920, 1080)
        self.assertFalse(valid)

    def test_interval_validation(self):
        """Test interval validation"""
        # Valid intervals
        valid, error = self.manager.validate_interval(500, "ms")
        self.assertTrue(valid)
        self.assertEqual(error, "")

        valid, error = self.manager.validate_interval(1.5, "seconds")
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid unit
        valid, error = self.manager.validate_interval(500, "invalid")
        self.assertFalse(valid)
        self.assertIn("Invalid unit", error)

        # Zero ms = no delay between bursts (max speed)
        valid, error = self.manager.validate_interval(0, "ms")
        self.assertTrue(valid)
        self.assertEqual(error, "")

        valid, error = self.manager.validate_interval(0.5, "ms")
        self.assertTrue(valid)

        valid, error = self.manager.validate_interval(-1, "ms")
        self.assertFalse(valid)
        self.assertIn("between 0 and 60000", error)

        valid, error = self.manager.validate_interval(70000, "ms")
        self.assertFalse(valid)
        self.assertIn("between 0 and 60000", error)

        # Invalid range for seconds
        valid, error = self.manager.validate_interval(0.0005, "seconds")
        self.assertFalse(valid)
        self.assertIn("between 0.001 and 60", error)

        valid, error = self.manager.validate_interval(70, "seconds")
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
        self.assertIn("Must be a number", error)

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
        self.assertIn("Must be a number", error)

    def test_variation_validation(self):
        """Test variation validation"""
        # Valid variation
        valid, error = self.manager.validate_variation(50, 1000, "ms")
        self.assertTrue(valid)
        self.assertEqual(error, "")

        # Invalid variation
        valid, error = self.manager.validate_variation(-1, 1000, "ms")
        self.assertFalse(valid)
        self.assertIn("cannot be negative", error)

        valid, error = self.manager.validate_variation(1000, 500, "ms")
        self.assertFalse(valid)
        self.assertIn("cannot be greater than or equal to interval", error)

        valid, error = self.manager.validate_variation(0, 0, "ms")
        self.assertTrue(valid)

        valid, error = self.manager.validate_variation(50, 0, "ms")
        self.assertFalse(valid)
        self.assertIn("positive interval", error)

        valid, error = self.manager.validate_variation("not_a_number", 1000, "ms")
        self.assertFalse(valid)
        self.assertIn("Must be a number", error)

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

    def test_parse_input_never_clamps_or_defaults(self):
        """#39: parsing reports bad input instead of rewriting it."""
        self.assertEqual(self.manager.parse_input("x_coord", "500"), (500, None))
        self.assertEqual(self.manager.parse_input("x_coord", " -50 "), (-50, None))
        self.assertEqual(self.manager.parse_input("x_coord", 20000), (20000, None))
        self.assertEqual(self.manager.parse_input("x_coord", "invalid")[1], "Must be a number")
        self.assertEqual(self.manager.parse_input("x_coord", "2.5")[1], "Must be a whole number")
        self.assertEqual(self.manager.parse_input("interval", "70000"), (70000, None))
        self.assertEqual(self.manager.parse_input("interval", "0.5"), (0.5, None))
        self.assertEqual(self.manager.parse_input("interval", "")[1], "Enter a number")
        self.assertEqual(self.manager.parse_input("interval", "nan")[1], "Must be a number")
        self.assertEqual(self.manager.parse_input("mouse_button", "left"), ("left", None))
        self.assertIsNotNone(self.manager.parse_input("mouse_button", "invalid")[1])
        self.assertIsNotNone(self.manager.parse_input("click_type", "invalid")[1])
        self.assertEqual(self.manager.parse_input("enable_failsafe", True), (True, None))

    def _ui_settings(self, **overrides):
        base = {
            "x_coord": "100",
            "y_coord": "100",
            "interval": "500",
            "interval_unit": "ms",
            "variation": "0",
            "mouse_button": "left",
            "click_type": "single",
            "burst_clicks": "1",
            "burst_pause": "0",
            "max_clicks": "0",
            "auto_stop_minutes": "0",
            "max_cps_ceiling": 50,
        }
        base.update(overrides)
        return base

    def test_bad_input_is_reported_not_rewritten(self):
        """#39: typos must not turn into a different (possibly faster) run."""
        cases = {
            "interval": ["-500", "1OO", "abc", "999999", ""],
            "x_coord": ["-1200", "abc", "5000"],
            "variation": ["-1", "x"],
            "burst_clicks": ["0", "101", "abc"],
            "burst_pause": ["-1", "70000"],
            "max_clicks": ["-1", "abc"],
            "auto_stop_minutes": ["-1", "1441", "abc"],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    result = self.manager.validate_all_settings(
                        self._ui_settings(**{field: value}), 1920, 1080
                    )
                    self.assertFalse(result["valid"])
                    self.assertTrue(result["errors"])

    def test_cursor_mode_ignores_coordinate_fields(self):
        """#48: X/Y are unused in cursor mode, so bad values there are fine."""
        result = self.manager.validate_all_settings(
            self._ui_settings(target_mode="cursor", x_coord="", y_coord="-99999"), 1920, 1080
        )
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["sanitized_settings"]["target_mode"], "cursor")
        self.assertNotIn("x_coord", result["sanitized_settings"])

    def test_unknown_target_mode_rejected(self):
        result = self.manager.validate_all_settings(self._ui_settings(target_mode="nope"))
        self.assertIn("target_mode", result["errors"])

    def test_valid_ui_strings_parse_to_numbers(self):
        result = self.manager.validate_all_settings(self._ui_settings(interval="0"), 1920, 1080)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["sanitized_settings"]["interval"], 0.0)
        self.assertEqual(result["sanitized_settings"]["x_coord"], 100)

    def test_comprehensive_validation(self):
        """Test comprehensive validation of all settings"""
        # Valid settings
        valid_settings = {
            "x_coord": 500,
            "y_coord": 600,
            "interval": 1000,
            "interval_unit": "ms",
            "variation": 100,
            "burst_clicks": 5,
            "burst_pause": 2000,
            "max_clicks": 1000,
            "auto_stop_minutes": 30,
        }

        result = self.manager.validate_all_settings(valid_settings)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

        # Invalid settings
        invalid_settings = {
            "x_coord": -50,
            "y_coord": 600,
            "interval": 70000,
            "interval_unit": "invalid",
            "variation": -10,
            "burst_clicks": 150,
            "burst_pause": -500,
            "max_clicks": -100,
            "auto_stop_minutes": 2000,
        }

        result = self.manager.validate_all_settings(invalid_settings)
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

        # Parsed values are kept as entered, never clamped or defaulted
        sanitized = result["sanitized_settings"]
        self.assertEqual(sanitized["x_coord"], -50)
        self.assertNotIn("interval_unit", sanitized)
        self.assertIn("interval_unit", result["errors"])

    def test_defaults_are_not_shared_between_instances(self):
        """Presets saved by one manager must not leak into another's defaults."""
        from autoclicker.utils.profiles import PresetManager

        with tempfile.TemporaryDirectory() as tmp:
            first = SettingsManager(os.path.join(tmp, "a.json"))
            PresetManager(first).save_preset("Leaky", 1, 2)
            second = SettingsManager(os.path.join(tmp, "b.json"))
            self.assertEqual(second.get("presets"), {})
            first.reset_to_defaults()
            self.assertEqual(first.get("presets"), {})
        self.assertEqual(SettingsManager.DEFAULT_SETTINGS["presets"], {})

    def test_non_dict_json_uses_defaults(self):
        with open(self.settings_file, "w", encoding="utf-8") as fh:
            fh.write("[1, 2, 3]")
        mgr = SettingsManager(self.settings_file)
        self.assertEqual(mgr.get("x_coord"), 100)

    def test_atomic_save_keeps_last_good_on_dump_failure(self):
        self.manager.set("x_coord", 111)
        with open(self.settings_file, encoding="utf-8") as fh:
            good = fh.read()
        with patch("autoclicker.core.settings_paths.json.dump", side_effect=OSError("disk")):
            self.manager.set("x_coord", 222)
        with open(self.settings_file, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), good)
        self.assertEqual(self.manager.get("x_coord"), 222)

    def test_max_cps_validation(self):
        valid, _error = self.manager.validate_max_cps(0)
        self.assertTrue(valid)
        valid, _error = self.manager.validate_max_cps(50)
        self.assertTrue(valid)
        valid, _error = self.manager.validate_max_cps(-1)
        self.assertFalse(valid)
        valid, _error = self.manager.validate_max_cps(20000)
        self.assertFalse(valid)
        result = self.manager.validate_all_settings({"max_cps_ceiling": 20000})
        self.assertFalse(result["valid"])
        self.assertIn("max_cps_ceiling", result["errors"])


if __name__ == "__main__":
    unittest.main()


class TestUnreadableSettingsFile(unittest.TestCase):
    """#65: a bad settings file is moved aside, never silently overwritten."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, "autoclicker_settings.json")

    def tearDown(self):
        self._dir.cleanup()

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def _backups(self):
        return [n for n in os.listdir(self._dir.name) if ".corrupt-" in n]

    def test_invalid_json_is_preserved_and_reported(self):
        original = '{"presets": {"Home": {"x": 1, "y": 2}},'  # trailing comma, truncated
        self._write(original)
        manager = SettingsManager(self.path)
        self.assertEqual(manager.get("presets"), {})
        backups = self._backups()
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self._dir.name, backups[0]), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original)
        self.assertIn(backups[0], manager.load_warning)
        manager.set("theme", "dark")  # a later save must not touch the backup
        self.assertEqual(len(self._backups()), 1)

    def test_non_object_json_is_preserved(self):
        self._write("[1, 2, 3]")
        manager = SettingsManager(self.path)
        self.assertEqual(len(self._backups()), 1)
        self.assertIn("not a JSON object", manager.load_warning)

    def test_empty_file_is_not_quarantined(self):
        self._write("")
        manager = SettingsManager(self.path)
        self.assertEqual(self._backups(), [])
        self.assertIsNone(manager.load_warning)

    def test_wrong_typed_values_fall_back_per_key(self):
        self._write(
            '{"presets": [], "hotkeys": "F6", "enable_failsafe": "no",'
            ' "interval": 250, "mouse_button": 3, "custom": 1}'
        )
        manager = SettingsManager(self.path)
        self.assertEqual(manager.get("presets"), {})
        self.assertEqual(manager.get("hotkeys")["start"], "F6")
        self.assertIs(manager.get("enable_failsafe"), True)
        self.assertEqual(manager.get("mouse_button"), "left")
        self.assertEqual(manager.get("interval"), 250)  # good values are kept
        self.assertEqual(manager.get("custom"), 1)  # unknown keys are kept
        self.assertEqual(self._backups(), [])
        self.assertIsNone(manager.load_warning)

    def test_malformed_presets_are_dropped(self):
        self._write('{"presets": {"ok": {"x": 5, "y": 6}, "bad": {"x": "a"}, "worse": 7}}')
        manager = SettingsManager(self.path)
        self.assertEqual(manager.get("presets"), {"ok": {"x": 5, "y": 6}})
