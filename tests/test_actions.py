"""Hold mode and key repeat (#78)."""

import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import pyautogui

from autoclicker.app.controller import AutoclickerController
from autoclicker.core.click_engine import (
    STOP_COMPLETED,
    STOP_EMERGENCY,
    STOP_SAFETY,
    STOP_USER,
    ClickEngine,
    ClickEngineError,
)
from autoclicker.core.screen import ScreenBounds
from autoclicker.core.settings_manager import SettingsManager

BOUNDS = ScreenBounds(0, 0, 1920, 1080)


def _mock(m):
    m.size.return_value = (1920, 1080)
    m.FailSafeException = pyautogui.FailSafeException
    m.PyAutoGUIException = pyautogui.PyAutoGUIException
    m.FAILSAFE = True


class Run:
    def __init__(self, **kwargs):
        self.engine = ClickEngine(enable_performance_monitoring=False)
        self.engine.configure_safety(failsafe=False, max_cps=0)
        self.done = threading.Event()
        self.outcome = None
        args = dict(
            x=50, y=60, interval=0, variation=0, burst_clicks=1, burst_pause=0,
            max_clicks=0, auto_stop_minutes=0, mouse_button="left", click_type="single",
        )  # fmt: skip
        args.update(kwargs)
        assert self.engine.start_clicking(on_finished=self._finished, **args)

    def _finished(self, outcome):
        self.outcome = outcome
        self.done.set()

    def wait(self):
        assert self.done.wait(3)
        return self.outcome


class TestHold(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_hold_presses_and_releases_each_time(self, m):
        _mock(m)
        outcome = Run(action="hold", hold_ms=1, max_clicks=3, mouse_button="right").wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(m.mouseDown.call_count, 3)
        self.assertEqual(m.mouseUp.call_count, 3)
        m.mouseDown.assert_called_with(x=50, y=60, button="right")
        m.mouseUp.assert_called_with(button="right")
        m.click.assert_not_called()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_stop_and_emergency_release_a_long_hold(self, m):
        _mock(m)
        for stop, reason in (("stop_clicking", STOP_USER), ("emergency_stop", STOP_EMERGENCY)):
            with self.subTest(stop=stop):
                m.reset_mock()
                run = Run(action="hold", hold_ms=30_000)
                threading.Timer(0.1, getattr(run.engine, stop)).start()
                outcome = run.wait()
                self.assertEqual(outcome.reason, reason)
                m.mouseUp.assert_called_once_with(button="left")

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_failsafe_on_release_still_releases(self, m):
        _mock(m)
        m.mouseUp.side_effect = [pyautogui.FailSafeException(), None]
        outcome = Run(action="hold", hold_ms=1).wait()
        self.assertEqual(outcome.reason, STOP_SAFETY)
        self.assertEqual(m.mouseUp.call_count, 2)  # retried with the failsafe off
        self.assertIs(m.FAILSAFE, True)  # and restored


class TestKey(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_single_key_and_combo(self, m):
        _mock(m)
        Run(action="key", key="f5", max_clicks=2, x=None, y=None).wait()
        self.assertEqual(m.press.call_count, 2)
        m.press.assert_called_with("f5")
        m.reset_mock()
        Run(action="key", key="ctrl+r", max_clicks=1, x=None, y=None).wait()
        m.hotkey.assert_called_once_with("ctrl", "r")
        m.click.assert_not_called()

    def test_unknown_action_rejected(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        with self.assertRaises(ClickEngineError):
            engine.start_clicking(1, 1, 0, 0, 1, 0, 0, 0, "left", "single", action="wiggle")


class TestValidation(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = SettingsManager(os.path.join(self._dir.name, "s.json"))

    def validate(self, **raw):
        base = {"target_mode": "fixed", "x_coord": "10", "y_coord": "10", "action": "click"}
        return self.settings.validate_all_settings({**base, **raw}, 1920, 1080)

    def test_hold_range(self):
        self.assertTrue(self.validate(action="hold", hold_ms="250")["valid"])
        self.assertIn("hold_ms", self.validate(action="hold", hold_ms="0")["errors"])
        self.assertIn("hold_ms", self.validate(action="hold", hold_ms="70000")["errors"])

    def test_key_names(self):
        result = self.validate(action="key", key=" Ctrl + R ", x_coord="not used")
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["sanitized_settings"]["key"], "ctrl+r")
        self.assertIn("Unknown key", self.validate(action="key", key="hyper")["errors"]["key"])
        self.assertIn("key", self.validate(action="key", key="")["errors"])

    def test_unused_fields_are_ignored(self):
        result = self.validate(action="click", key="???", hold_ms="x")
        self.assertTrue(result["valid"], result["errors"])

    def test_sequences_only_click(self):
        result = self.validate(
            target_mode="sequence", sequence=[{"x": 1, "y": 1}], action="key", key="f5"
        )
        self.assertIn("action", result["errors"])


class TestHotkeyClash(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        patcher = patch.dict(os.environ, {"APPDATA": self._dir.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.controller = AutoclickerController()

    def test_pressing_an_own_hotkey_is_refused(self):
        raw = {"target_mode": "fixed", "action": "key", "key": "f6"}
        result = self.controller.validate(raw, BOUNDS)
        self.assertIn("F6 is the start hotkey", result["errors"]["key"])

    def test_other_keys_are_fine(self):
        for key in ("f5", "space", "a", "ctrl+r"):
            with self.subTest(key=key):
                raw = {"target_mode": "fixed", "action": "key", "key": key}
                self.assertTrue(self.controller.validate(raw, BOUNDS)["valid"])


class TestHoldFailsafe(unittest.TestCase):
    """#82: the corner failsafe works during a long hold."""

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_corner_during_hold_releases_and_stops(self, m):
        from autoclicker.core.screen import ScreenBounds

        _mock(m)
        positions = [None]  # cursor away from corners at first
        with (
            patch(
                "autoclicker.core.click_engine.monitor_rects",
                return_value=[ScreenBounds(0, 0, 1920, 1080)],
            ),
            patch(
                "autoclicker.core.click_engine.cursor_position", side_effect=lambda: positions[0]
            ),
        ):
            run = Run.__new__(Run)
            run.engine = ClickEngine(enable_performance_monitoring=False)
            run.engine.configure_safety(failsafe=True, max_cps=0)
            run.done = threading.Event()
            run.outcome = None
            run.engine.start_clicking(
                50, 60, 0, 0, 1, 0, 0, 0, "left", "single", run._finished,
                action="hold", hold_ms=30_000,
            )  # fmt: skip
            threading.Event().wait(0.2)
            positions[0] = (0, 0)  # slam into the corner mid-hold
            outcome = run.wait()
        self.assertEqual(outcome.reason, STOP_SAFETY)
        m.mouseUp.assert_called_once_with(button="left")
