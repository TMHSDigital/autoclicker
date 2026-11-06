"""Image mode: stop when the image has not been seen for N seconds (#174)."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import pyautogui

from autoclicker.cli import build_overrides, parse_args
from autoclicker.core.click_engine import STOP_COMPLETED, ClickEngine
from autoclicker.core.image_match import ImageTarget
from autoclicker.core.settings_manager import SettingsManager
from autoclicker.utils.profiles import PROFILE_KEYS


def _mock(m):
    m.size.return_value = (1920, 1080)
    m.FailSafeException = pyautogui.FailSafeException
    m.PyAutoGUIException = pyautogui.PyAutoGUIException


def _target(timeout, positions):
    target = MagicMock(spec=ImageTarget)
    target.locate.side_effect = lambda: positions[0]
    target.missing_stop_seconds = timeout
    return target


class TestImageTimeout(unittest.TestCase):
    def run_engine(self, target, seconds=5):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.configure_safety(failsafe=False, max_cps=0)
        done = threading.Event()
        outcomes = []
        engine.start_clicking(
            None, None, 0, 0, 1, 0, 0, 0, "left", "single",
            lambda o: (outcomes.append(o), done.set()), image=target,
        )  # fmt: skip
        try:
            finished = done.wait(seconds)
        finally:
            engine.emergency_stop()
            engine.stop_clicking()
        return finished, outcomes, engine

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_stops_once_the_image_stays_away(self, m):
        _mock(m)
        started = time.monotonic()
        finished, outcomes, _engine = self.run_engine(_target(0.3, [None]))
        self.assertTrue(finished)
        self.assertGreaterEqual(time.monotonic() - started, 0.3)
        self.assertEqual(outcomes[0].reason, STOP_COMPLETED)
        self.assertEqual(outcomes[0].message, "Stopped: image not seen for 0.3 s")
        m.click.assert_not_called()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_zero_keeps_waiting(self, m):
        _mock(m)
        finished, _outcomes, _engine = self.run_engine(_target(0, [None]), seconds=0.5)
        self.assertFalse(finished)

    def test_seeing_the_image_resets_the_clock(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._image = _target(10, [None])
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=100.0):
            self.assertIsNone(engine._image_gone_message())
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=109.0):
            self.assertIsNone(engine._image_gone_message())
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=110.0):
            self.assertEqual(engine._image_gone_message(), "Stopped: image not seen for 10 s")
        engine._image_missing_since = 0.0  # what the loop does when it is found
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=115.0):
            self.assertIsNone(engine._image_gone_message())


class TestSettingAndFlag(unittest.TestCase):
    def test_validation(self):
        settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
        self.assertEqual(settings.get("image_missing_stop_seconds"), 0)
        for value, ok in (("0", True), ("30", True), ("86400", True), ("-1", False), ("x", False)):
            with self.subTest(value=value):
                result = settings.validate_all_settings(
                    {"target_mode": "cursor", "image_missing_stop_seconds": value}, 1920, 1080
                )
                self.assertEqual("image_missing_stop_seconds" not in result["errors"], ok)

    def test_flag_and_profile_key(self):
        args = parse_args(["--image", "--image-timeout", "45"])
        self.assertEqual(
            build_overrides(args, lambda _name: None)["image_missing_stop_seconds"], "45"
        )
        self.assertIn("image_missing_stop_seconds", PROFILE_KEYS)


if __name__ == "__main__":
    unittest.main()
