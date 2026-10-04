"""Conditional clicking: only click while a pixel matches a color (#80)."""

import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import pyautogui

from autoclicker.app.controller import _pixel_condition
from autoclicker.core.click_engine import (
    PAUSE_PIXEL,
    STOP_COMPLETED,
    STOP_USER,
    ClickEngine,
    ClickStep,
    PixelCondition,
)
from autoclicker.core.settings_manager import SettingsManager

GREEN = (0, 200, 0)


def _mock(m):
    m.size.return_value = (1920, 1080)
    m.FailSafeException = pyautogui.FailSafeException
    m.PyAutoGUIException = pyautogui.PyAutoGUIException


class Run:
    def __init__(self, condition, **kwargs):
        self.engine = ClickEngine(enable_performance_monitoring=False)
        self.engine.configure_safety(failsafe=False, max_cps=0)
        self.done = threading.Event()
        self.outcome = None
        args = dict(
            x=10, y=10, interval=0, variation=0, burst_clicks=1, burst_pause=0,
            max_clicks=0, auto_stop_minutes=0, mouse_button="left", click_type="single",
        )  # fmt: skip
        args.update(kwargs)
        assert self.engine.start_clicking(on_finished=self._done, condition=condition, **args)

    def _done(self, outcome):
        self.outcome = outcome
        self.done.set()

    def wait(self, timeout=3):
        assert self.done.wait(timeout)
        return self.outcome


class TestPixelCondition(unittest.TestCase):
    def test_tolerance(self):
        cond = PixelCondition(1, 1, GREEN, tolerance=10)
        self.assertTrue(cond.matches((5, 195, 8)))
        self.assertFalse(cond.matches((0, 180, 0)))

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_clicks_while_matching(self, m):
        _mock(m)
        m.pixel.return_value = GREEN
        outcome = Run(PixelCondition(5, 5, GREEN), max_clicks=3).wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(m.click.call_count, 3)
        m.pixel.assert_called_with(5, 5)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_stop_mode_ends_the_run_when_it_changes(self, m):
        _mock(m)
        m.pixel.return_value = (255, 0, 0)
        outcome = Run(PixelCondition(5, 5, GREEN, on_mismatch="stop")).wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(outcome.message, "Stopped: the watched pixel changed")
        m.click.assert_not_called()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_wait_mode_pauses_then_resumes(self, m):
        _mock(m)
        colors = [(255, 0, 0)]
        m.pixel.side_effect = lambda *_: colors[0]
        run = Run(PixelCondition(5, 5, GREEN, on_mismatch="wait"), max_clicks=2)
        deadline = threading.Event()
        deadline.wait(0.3)
        self.assertTrue(run.engine.is_paused)
        self.assertEqual(run.engine.pause_reason, PAUSE_PIXEL)
        m.click.assert_not_called()
        colors[0] = GREEN
        outcome = run.wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(m.click.call_count, 2)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_unreadable_screen_does_not_click(self, m):
        _mock(m)
        m.pixel.side_effect = OSError("no screen")
        run = Run(PixelCondition(5, 5, GREEN, on_mismatch="wait"))
        threading.Event().wait(0.2)
        m.click.assert_not_called()
        run.engine.stop_clicking()
        self.assertEqual(run.wait().reason, STOP_USER)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_checked_before_each_sequence_step(self, m):
        _mock(m)
        m.pixel.return_value = GREEN
        run = Run.__new__(Run)
        run.engine = ClickEngine(enable_performance_monitoring=False)
        run.engine.configure_safety(failsafe=False, max_cps=0)
        run.done = threading.Event()
        run.outcome = None
        # Once before the round, then before each step: go, go, stop.
        with patch.object(run.engine, "_check_condition", side_effect=["go", "go", "stop"]):
            run.engine.start_clicking(
                None, None, 0, 0, 1, 0, 0, 0, "left", "single", run._done,
                steps=[ClickStep(1, 1), ClickStep(2, 2)],
                condition=PixelCondition(5, 5, GREEN, on_mismatch="stop"),
            )  # fmt: skip
            run.wait()
        self.assertEqual(m.click.call_count, 1)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_reads_happen_off_the_click_thread(self, m):
        _mock(m)
        threads = set()

        def pixel(*_):
            threads.add(threading.current_thread().name)
            return GREEN

        m.pixel.side_effect = pixel
        Run(PixelCondition(5, 5, GREEN), max_clicks=3).wait()
        self.assertEqual(threads, {"PixelWatch"})

    def test_stale_watcher_from_a_previous_run_exits(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine._run_id = 2
        with patch.object(engine, "_read_condition") as read:
            engine._watch_condition(PixelCondition(1, 1, GREEN), run_id=1)
        read.assert_not_called()
        self.assertIsNone(engine._condition_state)


class TestConditionSettings(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = SettingsManager(os.path.join(self._dir.name, "s.json"))

    def validate(self, **raw):
        base = {"target_mode": "fixed", "x_coord": "10", "y_coord": "10"}
        return self.settings.validate_all_settings({**base, **raw}, 1920, 1080)

    def test_valid_and_converted(self):
        result = self.validate(
            condition="wait",
            condition_x="100",
            condition_y="200",
            condition_color="#00c800",
            condition_tolerance="20",
        )
        self.assertTrue(result["valid"], result["errors"])
        cond = _pixel_condition(result["sanitized_settings"])
        self.assertEqual(cond, PixelCondition(100, 200, (0, 200, 0), 20, "wait"))

    def test_errors(self):
        result = self.validate(
            condition="stop",
            condition_x="5000",
            condition_y="1",
            condition_color="green",
            condition_tolerance="300",
        )
        for key in ("condition_x", "condition_color", "condition_tolerance"):
            self.assertIn(key, result["errors"])

    def test_off_ignores_the_fields(self):
        result = self.validate(condition="none", condition_color="??", condition_x="x")
        self.assertTrue(result["valid"], result["errors"])
        self.assertIsNone(_pixel_condition(result["sanitized_settings"]))
