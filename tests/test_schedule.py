"""Start at a time of day (#121)."""

import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from autoclicker.core.schedule import describe_wait, next_start, parse_start_at
from autoclicker.core.settings_manager import SettingsManager


class TestSchedule(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_start_at("09:30"), (9, 30))
        self.assertEqual(parse_start_at(" 9:05 "), (9, 5))
        self.assertEqual(parse_start_at("23:59"), (23, 59))
        for bad in ("", "24:00", "9:5", "12:60", "noon", "9.30", "-1:00"):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_start_at(bad))

    def test_next_start_today_or_tomorrow(self):
        now = datetime(2026, 10, 5, 14, 0, 30)
        self.assertEqual(next_start(15, 0, now), datetime(2026, 10, 5, 15, 0))
        self.assertEqual(next_start(14, 0, now), datetime(2026, 10, 6, 14, 0))  # just passed
        self.assertEqual(next_start(9, 0, now), datetime(2026, 10, 6, 9, 0))

    def test_describe_wait(self):
        self.assertEqual(describe_wait(59.2), "1:00")
        self.assertEqual(describe_wait(3 * 3600 + 5 * 60 + 9), "3:05:09")
        self.assertEqual(describe_wait(-3), "0:00")

    def test_validation(self):
        settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
        for value, ok in (("", True), ("07:15", True), ("7:15", True), ("25:00", False)):
            with self.subTest(value=value):
                result = settings.validate_all_settings(
                    {"target_mode": "cursor", "start_at": value}, 1920, 1080
                )
                self.assertEqual("start_at" not in result["errors"], ok)


class FakeClock:
    """Stands in for datetime in a module; only now() is used."""

    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


class TestHeadlessStartAt(unittest.TestCase):
    def test_waits_for_the_time_then_runs(self):
        from autoclicker import cli

        clock = FakeClock(datetime(2026, 10, 5, 8, 59, 58))

        def sleep(seconds):
            from datetime import timedelta

            clock.current += timedelta(seconds=seconds)

        args = cli.parse_args(["--headless", "--start-at", "09:00", "--at", "5,5", "--clicks", "1"])
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"APPDATA": tmp}),
            patch("autoclicker.core.single_instance.SingleInstance.acquire", return_value=True),
            patch("autoclicker.app.hotkeys.HotkeyManager"),
            patch("autoclicker.core.click_engine.pyautogui") as m,
            patch.object(cli, "datetime", clock),
            patch.object(cli.time, "sleep", side_effect=sleep) as slept,
            patch.object(cli, "_emit") as emit,
        ):
            m.size.return_value = (1920, 1080)
            code = cli.run_headless(args)
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(clock.current, datetime(2026, 10, 5, 9, 0))
        self.assertGreaterEqual(slept.call_count, 2)
        emit.assert_any_call("Starting at 09:00. Ctrl+C to cancel.")
        m.click.assert_called_once()


if __name__ == "__main__":
    unittest.main()
