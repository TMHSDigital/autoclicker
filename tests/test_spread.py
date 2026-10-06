"""Click spread: each click lands up to N px from its target (#120)."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from autoclicker.cli import build_overrides, parse_args
from autoclicker.core.click_engine import ClickEngine, ClickStep
from autoclicker.core.image_match import ImageTarget
from autoclicker.core.screen import ScreenBounds
from autoclicker.core.settings_manager import SettingsManager


def _clicks(m):
    return [(c.kwargs["x"], c.kwargs["y"]) for c in m.click.call_args_list]


class EngineCase(unittest.TestCase):
    def setUp(self):
        p = patch("autoclicker.core.click_engine.pyautogui")
        self.m = p.start()
        self.addCleanup(p.stop)
        self.m.size.return_value = (1920, 1080)
        self.engine = ClickEngine(enable_performance_monitoring=False)
        self.engine.configure_safety(failsafe=False, max_cps=0)
        self.engine._screen_bounds = ScreenBounds(0, 0, 1920, 1080)

    def run_clicks(self, x, y, spread, n=60, image=None):
        self.engine._spread = spread
        self.engine._image = image
        for _ in range(n):
            self.engine._perform_click(x, y, "left", "single")
        return _clicks(self.m)


class TestSpreadEngine(EngineCase):
    def test_off_means_the_exact_point(self):
        self.assertEqual(set(self.run_clicks(500, 400, 0)), {(500, 400)})

    def test_clicks_stay_within_the_spread(self):
        points = self.run_clicks(500, 400, 5)
        self.assertTrue(all(abs(x - 500) <= 5 and abs(y - 400) <= 5 for x, y in points))
        self.assertGreater(len(set(points)), 5)  # actually varies

    def test_kept_on_screen(self):
        points = self.run_clicks(0, 1079, 20)
        self.assertTrue(all(0 <= x <= 1919 and 0 <= y <= 1079 for x, y in points))

    def test_kept_on_the_image(self):
        target = ImageTarget(Image.new("RGB", (11, 5)), ScreenBounds(0, 0, 100, 100))
        points = self.run_clicks(300, 300, 40, image=target)
        self.assertTrue(all(abs(x - 300) <= 5 and abs(y - 300) <= 2 for x, y in points))

    def test_sequence_steps_are_spread_too(self):
        engine = self.engine
        engine._spread = 3
        engine._steps = (ClickStep(100, 100), ClickStep(800, 600))
        engine.is_running = True
        engine._perform_sequence(0, 0)
        (x1, y1), (x2, y2) = _clicks(self.m)
        self.assertTrue(abs(x1 - 100) <= 3 and abs(y1 - 100) <= 3)
        self.assertTrue(abs(x2 - 800) <= 3 and abs(y2 - 600) <= 3)

    def test_resting_where_the_last_click_landed_is_not_a_failsafe(self):
        engine = self.engine
        engine.failsafe_enabled = True
        engine._failsafe_corners = frozenset({(0, 0)})
        engine._last_click_pos = (2, 1)
        with patch("autoclicker.core.click_engine.cursor_position", return_value=(2, 1)):
            self.assertFalse(engine._cursor_in_failsafe_corner(0, 0))
        with patch("autoclicker.core.click_engine.cursor_position", return_value=(1, 1)):
            self.assertTrue(engine._cursor_in_failsafe_corner(0, 0))

    def test_start_clicking_takes_the_setting(self):
        engine = self.engine
        engine.start_clicking(10, 10, 1000, 0, 1, 0, 1, 0, "left", "single", spread=7)
        engine.stop_clicking()
        self.assertEqual(engine._spread, 7)


class TestSpreadSettings(unittest.TestCase):
    def setUp(self):
        self.settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))

    def errors(self, **raw):
        base = {"target_mode": "fixed", "x_coord": "5", "y_coord": "5"}
        return self.settings.validate_all_settings({**base, **raw}, 1920, 1080)["errors"]

    def test_range(self):
        for value, ok in (("0", True), ("50", True), ("51", False), ("-1", False), ("x", False)):
            with self.subTest(value=value):
                self.assertEqual("click_spread" not in self.errors(click_spread=value), ok)

    def test_ignored_at_the_cursor_and_for_keys(self):
        self.assertNotIn("click_spread", self.errors(target_mode="cursor", click_spread="x"))
        self.assertNotIn("click_spread", self.errors(action="key", key="f5", click_spread="x"))

    def test_cli_flag_and_profile_key(self):
        from autoclicker.utils.profiles import PROFILE_KEYS

        values = build_overrides(parse_args(["--at", "5,5", "--spread", "4"]), {}.get)
        self.assertEqual(values["click_spread"], "4")
        self.assertIn("click_spread", PROFILE_KEYS)


class TestSpreadForm(unittest.TestCase):
    def test_disabled_where_it_does_not_apply(self):
        from autoclicker.gui.main_window import AutoclickerApp

        app = AutoclickerApp.__new__(AutoclickerApp)
        app.target_mode_var, app.action_var = MagicMock(), MagicMock()
        app.x_entry, app.y_entry, app.pick_btn = MagicMock(), MagicMock(), MagicMock()
        app.spread_entry = MagicMock()
        for mode, action, state in (
            ("fixed", "click", "normal"),
            ("image", "hold", "normal"),
            ("cursor", "click", "disabled"),
            ("fixed", "key", "disabled"),
        ):
            with self.subTest(mode=mode, action=action):
                app.target_mode_var.get.return_value = mode
                app.action_var.get.return_value = action
                app._apply_target_mode_state()
                app.spread_entry.configure.assert_called_with(state=state)


if __name__ == "__main__":
    unittest.main()
