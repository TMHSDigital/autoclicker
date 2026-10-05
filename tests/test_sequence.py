"""Multi-point click sequences (#72)."""

import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import pyautogui

from autoclicker.core.click_engine import (
    STOP_COMPLETED,
    STOP_ERROR,
    STOP_USER,
    ClickEngine,
    ClickStep,
)
from autoclicker.core.settings_manager import MAX_SEQUENCE_STEPS, SettingsManager

STEPS = [
    ClickStep(10, 10, "left", "single", 0),
    ClickStep(20, 20, "right", "double", 0),
    ClickStep(30, 30, "middle", "single", 0),
]


def _mock(mock_pyautogui):
    mock_pyautogui.size.return_value = (1920, 1080)
    mock_pyautogui.FailSafeException = pyautogui.FailSafeException
    mock_pyautogui.PyAutoGUIException = pyautogui.PyAutoGUIException


class EngineRun:
    """Run the engine to completion and capture its single outcome."""

    def __init__(self, **start_kwargs):
        self.engine = ClickEngine(enable_performance_monitoring=False)
        self.engine.configure_safety(failsafe=False, max_cps=0)
        self.done = threading.Event()
        self.outcome = None
        defaults = dict(
            x=None,
            y=None,
            interval=0,
            variation=0,
            burst_clicks=1,
            burst_pause=0,
            max_clicks=0,
            auto_stop_minutes=0,
            mouse_button="left",
            click_type="single",
        )
        self.kwargs = {**defaults, **start_kwargs}

    def start(self):
        started = self.engine.start_clicking(on_finished=self._finished, **self.kwargs)
        assert started
        return self

    def _finished(self, outcome):
        self.outcome = outcome
        self.done.set()

    def wait(self):
        assert self.done.wait(3), "run did not finish"
        return self.outcome


class TestEngineSequence(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_steps_click_in_order_for_each_round(self, mock_pyautogui):
        _mock(mock_pyautogui)
        outcome = EngineRun(steps=STEPS, repeat=2).start().wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(outcome.message, "Done: ran the sequence 2 times")
        calls = [
            (c.kwargs["x"], c.kwargs["y"], c.kwargs["button"], c.kwargs["clicks"])
            for c in mock_pyautogui.click.call_args_list
        ]
        one_round = [(10, 10, "left", 1), (20, 20, "right", 2), (30, 30, "middle", 1)]
        self.assertEqual(calls, one_round * 2)
        self.assertEqual(outcome.clicks, 6)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_click_limit_can_end_mid_round(self, mock_pyautogui):
        _mock(mock_pyautogui)
        outcome = EngineRun(steps=STEPS, max_clicks=4).start().wait()
        self.assertEqual(outcome.message, "Done: reached 4 clicks")
        self.assertEqual(mock_pyautogui.click.call_count, 4)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_waits_between_steps_but_not_after_the_last(self, mock_pyautogui):
        _mock(mock_pyautogui)
        run = EngineRun(
            steps=[ClickStep(1, 1, delay_ms=40), ClickStep(2, 2, delay_ms=999)], repeat=1
        )
        with patch.object(run.engine._stop_event, "wait", return_value=False) as wait:
            run.start().wait()
        timeouts = [c.kwargs.get("timeout") for c in wait.call_args_list]
        self.assertIn(0.04, timeouts)
        self.assertNotIn(0.999, timeouts)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_stop_mid_sequence(self, mock_pyautogui):
        _mock(mock_pyautogui)
        run = EngineRun(steps=[ClickStep(1, 1, delay_ms=5000), ClickStep(2, 2)])
        run.start()
        threading.Timer(0.1, run.engine.stop_clicking).start()
        outcome = run.wait()
        self.assertEqual(outcome.reason, STOP_USER)
        self.assertEqual(mock_pyautogui.click.call_count, 1)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_error_names_the_step(self, mock_pyautogui):
        _mock(mock_pyautogui)
        steps = [ClickStep(1, 1), ClickStep(99_999, 1)]
        outcome = EngineRun(steps=steps).start().wait()
        self.assertEqual(outcome.reason, STOP_ERROR)
        self.assertTrue(outcome.message.startswith("Step 2:"), outcome.message)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_plain_run_after_a_sequence_is_not_a_sequence(self, mock_pyautogui):
        _mock(mock_pyautogui)
        run = EngineRun(steps=STEPS, repeat=1)
        run.start().wait()
        run.engine.click_thread.join(1)
        run.done.clear()
        mock_pyautogui.click.reset_mock()
        run.kwargs.update(x=5, y=6, max_clicks=1)
        run.kwargs.pop("steps")
        run.kwargs.pop("repeat")
        run.start().wait()
        mock_pyautogui.click.assert_called_once_with(x=5, y=6, button="left", clicks=1)


class TestSequenceValidation(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = SettingsManager(os.path.join(self._dir.name, "s.json"))

    def validate(self, sequence, repeat="0", mode="sequence"):
        raw = {
            "target_mode": mode,
            "x_coord": "not used",
            "y_coord": "",
            "interval": "100",
            "interval_unit": "ms",
            "sequence": sequence,
            "sequence_repeat": repeat,
        }
        return self.settings.validate_all_settings(raw, 1920, 1080)

    def test_valid_sequence_fills_defaults(self):
        result = self.validate([{"x": "5", "y": 6}, {"x": 7, "y": 8, "button": "right"}])
        self.assertTrue(result["valid"], result["errors"])
        first, second = result["sanitized_settings"]["sequence"]
        self.assertEqual(
            first, {"x": 5, "y": 6, "button": "left", "click_type": "single", "delay_ms": 0}
        )
        self.assertEqual(second["button"], "right")

    def test_empty_sequence_is_an_error(self):
        result = self.validate([])
        self.assertIn("Add at least one point", result["errors"]["sequence"])

    def test_off_screen_step(self):
        result = self.validate([{"x": 1, "y": 1}, {"x": 5000, "y": 1}])
        self.assertIn("Step 2", result["errors"]["sequence"])

    def test_bad_field_names_the_step(self):
        result = self.validate([{"x": 1, "y": 1, "click_type": "triple"}])
        self.assertIn("Step 1 click type", result["errors"]["sequence"])
        result = self.validate([{"x": 1, "y": 1, "delay_ms": 70_000}])
        self.assertIn("Step 1 wait", result["errors"]["sequence"])

    def test_too_many_steps(self):
        result = self.validate([{"x": 1, "y": 1}] * (MAX_SEQUENCE_STEPS + 1))
        self.assertIn(f"At most {MAX_SEQUENCE_STEPS}", result["errors"]["sequence"])

    def test_repeat_range(self):
        result = self.validate([{"x": 1, "y": 1}], repeat="-1")
        self.assertIn("sequence_repeat", result["errors"])

    def test_sequence_ignored_in_other_modes(self):
        raw = {
            "target_mode": "fixed",
            "x_coord": "10",
            "y_coord": "10",
            "sequence": "garbage",
            "sequence_repeat": "x",
        }
        result = self.settings.validate_all_settings(raw, 1920, 1080)
        self.assertTrue(result["valid"], result["errors"])
        self.assertNotIn("sequence", result["sanitized_settings"])


class TestSequenceFocus(unittest.TestCase):
    """#81: a sequence spanning two windows keeps running with Pause when unfocused."""

    OWN, WIN_A, WIN_B, OTHER = 1, 100, 200, 300

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_any_step_window_counts_as_in_front(self, m):
        _mock(m)
        windows = {(10, 10): self.WIN_A, (20, 20): self.WIN_B}
        foreground = [self.OWN]  # started from our own Start button

        def click(**kwargs):
            # Clicking a step activates the window under it
            foreground[0] = windows[(kwargs["x"], kwargs["y"])]

        m.click.side_effect = click
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.configure_safety(failsafe=False, max_cps=0, pause_when_unfocused=True)
        done = threading.Event()
        outcomes = []
        with (
            patch(
                "autoclicker.core.click_engine.is_own_window", side_effect=lambda h: h == self.OWN
            ),
            patch(
                "autoclicker.core.click_engine.root_window_at",
                side_effect=lambda x, y: windows.get((x, y)),
            ),
            patch(
                "autoclicker.core.click_engine.get_foreground_window_handle",
                side_effect=lambda: foreground[0],
            ),
        ):
            engine.start_clicking(
                None, None, 0, 0, 1, 0, 0, 0, "left", "single",
                lambda o: (outcomes.append(o), done.set()),
                steps=[ClickStep(10, 10), ClickStep(20, 20)],
                repeat=3,
            )  # fmt: skip
            self.assertTrue(done.wait(3))
        self.assertEqual(outcomes[0].message, "Done: ran the sequence 3 times")
        self.assertEqual(m.click.call_count, 6)

    def test_unrelated_window_pauses(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.pause_when_unfocused = True
        engine._step_hwnds = frozenset({self.WIN_A, self.WIN_B})
        engine._foreground_hwnd = self.WIN_A
        for current, paused in (
            (self.WIN_A, False),
            (self.WIN_B, False),
            (self.OTHER, True),
            (None, True),
        ):
            with (
                self.subTest(current=current),
                patch(
                    "autoclicker.core.click_engine.get_foreground_window_handle",
                    return_value=current,
                ),
            ):
                self.assertEqual(engine._should_pause_for_foreground(), paused)
