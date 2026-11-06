"""Defaults stated once and agreeing everywhere (#172)."""

import unittest

from autoclicker.app.hotkeys import DEFAULT_HOTKEYS, saved_bindings
from autoclicker.core.image_match import DEFAULT_MARGIN
from autoclicker.core.safety import DEFAULT_MAX_CPS
from autoclicker.core.settings_manager import SettingsManager
from autoclicker.gui import summaries


class TestDefaults(unittest.TestCase):
    def test_settings_defaults_match_their_owners(self):
        defaults = SettingsManager.DEFAULT_SETTINGS
        self.assertEqual(defaults["hotkeys"], DEFAULT_HOTKEYS)
        self.assertEqual(defaults["max_cps_ceiling"], DEFAULT_MAX_CPS)
        self.assertEqual(defaults["image_margin"], DEFAULT_MARGIN)
        self.assertEqual(summaries.DEFAULT_MAX_CPS, DEFAULT_MAX_CPS)

    def test_unused_theme_setting_is_gone(self):
        self.assertNotIn("theme", SettingsManager.DEFAULT_SETTINGS)

    def test_saved_bindings_fall_back_to_the_defaults(self):
        self.assertEqual(saved_bindings(None), DEFAULT_HOTKEYS)
        self.assertEqual(
            saved_bindings({"start": "F6", "stop": "f6", "emergency": "Esc"}), DEFAULT_HOTKEYS
        )
        custom = {"start": "F8", "stop": "F9", "emergency": "Esc", "toggle": ""}
        self.assertEqual(saved_bindings(custom), custom)


if __name__ == "__main__":
    unittest.main()
