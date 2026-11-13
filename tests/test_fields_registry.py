# SPDX-License-Identifier: CC-BY-NC-4.0
"""The field registry reproduces the key lists that used to be written by hand (#169)."""

import unittest

from autoclicker.app import controller
from autoclicker.core import fields
from autoclicker.core import settings_manager as sm
from autoclicker.core.image_match import DEFAULT_MARGIN
from autoclicker.core.safety import DEFAULT_MAX_CPS
from autoclicker.utils.profiles import PROFILE_KEYS

# The values as they were before the registry, kept here as the snapshot.
_PROFILE_KEYS = (
    "target_mode", "interval", "interval_unit", "variation", "mouse_button", "click_type",
    "burst_clicks", "burst_pause", "max_clicks", "auto_stop_minutes", "sequence",
    "sequence_repeat", "action", "hold_ms", "key", "condition", "condition_x", "condition_y",
    "condition_color", "condition_tolerance", "image_path", "image_region", "image_margin",
    "image_tolerance", "image_missing_stop_seconds", "click_spread",
)  # fmt: skip
_RUN_FIELDS = (
    "target_mode", "x_coord", "y_coord", "interval", "interval_unit", "variation",
    "mouse_button", "click_type", "burst_clicks", "burst_pause", "max_clicks",
    "auto_stop_minutes", "enable_failsafe", "pause_when_unfocused", "max_cps_ceiling",
    "start_delay_seconds", "start_at", "stop_at", "sequence", "sequence_repeat", "action",
    "hold_ms", "key", "condition", "condition_x", "condition_y", "condition_color",
    "condition_tolerance", "image_path", "image_region", "image_margin", "image_tolerance",
    "image_missing_stop_seconds", "click_spread",
)  # fmt: skip
_INT_FIELDS = {
    "x_coord", "y_coord", "variation", "burst_clicks", "max_clicks", "auto_stop_minutes",
    "max_cps_ceiling", "start_delay_seconds", "sequence_repeat", "condition_x", "condition_y",
    "condition_tolerance", "image_margin", "image_tolerance", "image_missing_stop_seconds",
    "click_spread",
}  # fmt: skip
_CHOICES = {
    "mouse_button": ("left", "right", "middle"),
    "click_type": ("single", "double"),
    "interval_unit": ("ms", "seconds"),
    "target_mode": ("fixed", "cursor", "sequence", "image"),
    "action": ("click", "hold", "key"),
    "condition": ("none", "wait", "stop"),
}
_DEFAULTS = {
    "target_mode": "fixed", "x_coord": 100, "y_coord": 100, "interval": 1000,
    "interval_unit": "ms", "variation": 0, "mouse_button": "left", "click_type": "single",
    "burst_clicks": 1, "burst_pause": 1000, "max_clicks": 0, "auto_stop_minutes": 0,
    "enable_failsafe": True, "max_cps_ceiling": DEFAULT_MAX_CPS, "start_delay_seconds": 3,
    "start_at": "", "stop_at": "", "sequence": [], "sequence_repeat": 0, "action": "click",
    "hold_ms": 500, "key": "", "condition": "none", "condition_x": 0, "condition_y": 0,
    "condition_color": "#000000", "condition_tolerance": 16, "image_path": "",
    "image_region": [], "image_margin": DEFAULT_MARGIN, "image_tolerance": 0,
    "image_missing_stop_seconds": 0, "click_spread": 0, "pause_when_unfocused": False,
    "minimize_to_tray": True, "check_for_updates": None, "last_update_check": 0,
    "first_run_hint_dismissed": False,
    "hotkeys": {"start": "F6", "stop": "F7", "emergency": "Esc", "toggle": ""},
    "presets": {},
}  # fmt: skip


class TestRegistrySnapshot(unittest.TestCase):
    def test_profile_and_run_keys_keep_their_order(self):
        self.assertEqual(PROFILE_KEYS, _PROFILE_KEYS)
        self.assertEqual(controller._RUN_FIELDS, _RUN_FIELDS)

    def test_parse_kinds(self):
        self.assertEqual(sm._INT_FIELDS, _INT_FIELDS)
        self.assertEqual(sm._FLOAT_FIELDS, {"interval", "burst_pause", "hold_ms"})
        self.assertEqual(sm._CHOICE_FIELDS, _CHOICES)

    def test_stored_types(self):
        self.assertEqual(
            sm._BOOL_KEYS, {"enable_failsafe", "pause_when_unfocused", "minimize_to_tray"}
        )
        self.assertEqual(sm._LIST_KEYS, {"sequence", "image_region"})
        self.assertEqual(
            sm._STR_KEYS,
            {*_CHOICES, "key", "condition_color", "image_path", "start_at", "stop_at"},
        )

    def test_defaults(self):
        self.assertEqual(sm.SettingsManager.DEFAULT_SETTINGS, _DEFAULTS)

    def test_default_lists_are_not_shared_with_the_registry(self):
        self.assertIsNot(
            sm.SettingsManager.DEFAULT_SETTINGS["sequence"], fields.DEFAULTS["sequence"]
        )

    def test_every_field_has_a_label_except_the_failsafe(self):
        unlabeled = [f.key for f in fields.FIELDS if f.key not in sm.FIELD_LABELS]
        self.assertEqual(unlabeled, ["enable_failsafe"])
        self.assertEqual(sm.field_label("auto_stop"), "Auto-stop")
        self.assertEqual(sm.field_label("image_margin"), "Search margin")

    def test_choice_fields_have_choices_and_only_they_do(self):
        for f in fields.FIELDS:
            with self.subTest(key=f.key):
                self.assertEqual(f.kind == "choice", bool(f.choices))
                if f.kind == "choice":
                    self.assertIn(f.default, f.choices)


if __name__ == "__main__":
    unittest.main()
