"""Stop at a time of day (#177)."""

import time
import unittest
from datetime import datetime
from unittest.mock import patch

from autoclicker.app.controller import _stop_deadline
from autoclicker.cli import parse_args
from autoclicker.core.click_engine import ClickEngine
from autoclicker.core.settings_manager import SettingsManager
from autoclicker.gui.summaries import timing_summary


class TestDeadline(unittest.TestCase):
    def deadline_in(self, stop_at, now):
        with (
            patch("autoclicker.app.controller.datetime") as clock,
            patch("autoclicker.app.controller.time.monotonic", return_value=1000.0),
        ):
            clock.now.return_value = now
            return _stop_deadline(stop_at)

    def test_later_today(self):
        deadline, label = self.deadline_in("17:30", datetime(2026, 11, 6, 9, 0))
        self.assertEqual(deadline, 1000.0 + 8.5 * 3600)
        self.assertEqual(label, "17:30")

    def test_across_midnight(self):
        deadline, label = self.deadline_in("1:15", datetime(2026, 11, 6, 23, 45))
        self.assertEqual(deadline, 1000.0 + 90 * 60)
        self.assertEqual(label, "01:15")

    def test_blank_or_bad_is_none(self):
        self.assertIsNone(_stop_deadline(""))
        self.assertIsNone(_stop_deadline("25:00"))


class TestEngineStopsAtTheDeadline(unittest.TestCase):
    def test_limit_message(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = time.monotonic()
        engine._stop_at = (time.monotonic() + 60, "17:30")
        self.assertIsNone(engine._limit_reached(0, 0))
        engine._stop_at = (time.monotonic() - 1, "17:30")
        self.assertEqual(engine._limit_reached(0, 0), "Done: stopped at 17:30")

    def test_click_limit_still_wins_first(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = time.monotonic()
        engine.click_count = 5
        engine._stop_at = (time.monotonic() - 1, "17:30")
        self.assertIn("reached 5 clicks", engine._limit_reached(5, 0))


class TestSettingsAndCli(unittest.TestCase):
    def test_validation(self):
        import os
        import tempfile

        settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
        for value, ok in (
            ("", True),
            ("17:30", True),
            ("7:05", True),
            ("24:00", False),
            ("x", False),
        ):
            with self.subTest(value=value):
                result = settings.validate_all_settings(
                    {"target_mode": "cursor", "stop_at": value}, 1920, 1080
                )
                self.assertEqual("stop_at" not in result["errors"], ok)

    def test_flag(self):
        from autoclicker.cli import build_overrides, has_overrides

        args = parse_args(["--stop-at", "17:30"])
        self.assertTrue(has_overrides(args))
        self.assertEqual(build_overrides(args, lambda _name: None)["stop_at"], "17:30")

    def test_summary(self):
        text = timing_summary(
            burst_clicks="1", burst_pause="0", start_delay="0", start_at="09:00", stop_at="17:30"
        )
        self.assertEqual(text, "at 09:00 · until 17:30")


if __name__ == "__main__":
    unittest.main()
