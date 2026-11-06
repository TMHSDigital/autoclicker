"""Progress toward the click and time limits while running (#173)."""

import time
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import ClickEngine
from autoclicker.gui.main_window import AutoclickerApp
from autoclicker.gui.summaries import format_stats


def _status(**overrides):
    return {
        "is_running": True,
        "click_count": 57,
        "runtime": "00:01:10",
        "max_clicks": 0,
        "seconds_left": None,
        **overrides,
    }


class TestFormatStats(unittest.TestCase):
    def test_click_limit_shows_n_of_max(self):
        self.assertEqual(format_stats(_status(max_clicks=200)).clicks, "57 / 200")
        self.assertEqual(format_stats(_status(max_clicks=2000)).clicks, "57 / 2,000")

    def test_no_limit_or_not_running_shows_the_count(self):
        self.assertEqual(format_stats(_status()).clicks, "57")
        self.assertEqual(format_stats(_status(is_running=False, max_clicks=200)).clicks, "57")

    def test_time_left(self):
        self.assertEqual(format_stats(_status(seconds_left=1730)).time_left, "28:50 left")
        self.assertEqual(format_stats(_status(seconds_left=7300)).time_left, "2:01:40 left")
        self.assertEqual(format_stats(_status()).time_left, "")
        self.assertEqual(format_stats(_status(is_running=False, seconds_left=5)).time_left, "")

    def test_older_status_without_limits_still_formats(self):
        stats = format_stats({"click_count": 3, "runtime": "00:00:01"})
        self.assertEqual((stats.clicks, stats.time_left), ("3", ""))


class TestEngineSecondsLeft(unittest.TestCase):
    def engine(self, minutes=0.0, stop_in=None):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine.start_time = 1000.0
        engine._limits = (0, minutes)
        engine._stop_at = (1000.0 + stop_in, "17:30") if stop_in is not None else None
        return engine

    def test_earliest_time_limit_wins(self):
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=1060.0):
            self.assertEqual(self.engine(minutes=30).seconds_left(), 1740)
            self.assertEqual(self.engine(minutes=30, stop_in=600).seconds_left(), 540)
            self.assertIsNone(self.engine().seconds_left())

    def test_none_when_idle(self):
        engine = self.engine(minutes=30)
        engine.is_running = False
        self.assertIsNone(engine.seconds_left())

    def test_status_carries_the_limits(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running, engine.start_time = True, time.monotonic()
        engine._limits = (200, 0.0)
        status = engine.get_status()
        self.assertEqual(status["max_clicks"], 200)
        self.assertIsNone(status["seconds_left"])


class TestTilesAndTray(unittest.TestCase):
    def test_runtime_caption_and_tray_show_time_left(self):
        app = AutoclickerApp.__new__(AutoclickerApp)
        app.click_engine = MagicMock()
        app.click_engine.get_status.return_value = _status(max_clicks=200, seconds_left=90)
        app.click_count_var, app.runtime_var, app.performance_var = (MagicMock() for _ in "abc")
        app.runtime_tile = MagicMock()
        app._set_tray_title = MagicMock()
        app._on_status_update()
        app.click_count_var.set.assert_called_with("57 / 200")
        app.runtime_tile.set_caption.assert_called_with("Runtime · 1:30 left")
        app._set_tray_title.assert_called_with("running, 57 / 200 clicks, 1:30 left")

        app.click_engine.get_status.return_value = _status(is_running=False)
        app._on_status_update()
        app.runtime_tile.set_caption.assert_called_with("Runtime")


if __name__ == "__main__":
    unittest.main()
