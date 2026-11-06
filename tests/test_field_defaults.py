"""Run fields, their defaults and limits stated once (#169)."""

import os
import tempfile
import unittest

from autoclicker.app.controller import _RUN_FIELDS, AutoclickerController
from autoclicker.core import settings_manager as sm
from autoclicker.core.settings_manager import SettingsManager, setting_key


class TestRunFields(unittest.TestCase):
    def test_every_run_field_has_a_saved_default(self):
        missing = [key for key in _RUN_FIELDS if key not in SettingsManager.DEFAULT_SETTINGS]
        self.assertEqual(missing, [])

    def test_missing_fields_get_the_saved_defaults(self):
        raw = AutoclickerController.collect_raw_settings({"interval": "250"})
        self.assertEqual(raw["interval"], "250")
        self.assertEqual(raw["start_delay_seconds"], 3)  # was 0 here, 3 in the defaults
        self.assertEqual(set(raw), set(_RUN_FIELDS))

    def test_point_keys(self):
        self.assertEqual(setting_key("x"), "x_coord")
        self.assertEqual(setting_key("y"), "y_coord")
        self.assertEqual(setting_key("interval"), "interval")


class TestNamedLimits(unittest.TestCase):
    def setUp(self):
        self.settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))

    def test_edges(self):
        s = self.settings
        self.assertTrue(s.validate_interval(sm.MAX_INTERVAL_MS, "ms")[0])
        self.assertFalse(s.validate_interval(sm.MAX_INTERVAL_MS + 1, "ms")[0])
        self.assertTrue(s.validate_interval(sm.MAX_INTERVAL_SECONDS, "seconds")[0])
        self.assertFalse(s.validate_interval(sm.MIN_INTERVAL_SECONDS / 2, "seconds")[0])
        self.assertTrue(s.validate_clicks(sm.MAX_CLICKS)[0])
        self.assertFalse(s.validate_clicks(sm.MAX_CLICKS + 1)[0])
        self.assertTrue(s.validate_minutes(sm.MAX_AUTO_STOP_MINUTES)[0])
        self.assertFalse(s.validate_minutes(sm.MAX_AUTO_STOP_MINUTES + 1)[0])
        self.assertTrue(s.validate_burst_settings(sm.MAX_BURST_CLICKS, sm.MAX_BURST_PAUSE_MS)[0])
        self.assertFalse(s.validate_burst_settings(sm.MAX_BURST_CLICKS + 1, 0)[0])
        self.assertFalse(s.validate_burst_settings(1, sm.MAX_BURST_PAUSE_MS + 1)[0])

    def test_messages_are_unchanged(self):
        s = self.settings
        self.assertEqual(
            s.validate_clicks(sm.MAX_CLICKS + 1)[1],
            "Click count cannot exceed 1,000,000 to prevent system overload",
        )
        self.assertEqual(
            s.validate_interval(60001, "ms")[1],
            "Interval in milliseconds must be between 0 and 60000 (0 = no delay between bursts)",
        )
        self.assertEqual(
            s.validate_burst_settings(1, 60001)[1],
            "Burst pause cannot exceed 60,000 milliseconds (1 minute)",
        )


if __name__ == "__main__":
    unittest.main()
