"""Sequence step types: click, hold and key steps in one sequence (#119)."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, call, patch

from autoclicker.app.controller import _sequence_steps
from autoclicker.core.click_engine import (
    STOP_COMPLETED,
    STOP_ERROR,
    STOP_SAFETY,
    STOP_USER,
    ClickStep,
)
from autoclicker.core.screen import ScreenBounds
from autoclicker.core.settings_manager import SettingsManager
from autoclicker.gui.features.sequence import describe_step
from tests.test_sequence import EngineRun, _mock


class TestEngineStepTypes(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_each_step_does_its_own_action(self, m):
        _mock(m)
        steps = [
            ClickStep(10, 10),
            ClickStep(type="key", key="ctrl+s"),
            ClickStep(type="key", key="f5"),
            ClickStep(20, 20, "right", type="hold", hold_ms=1),
        ]
        outcome = EngineRun(steps=steps, repeat=1).start().wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        m.click.assert_called_once_with(x=10, y=10, button="left", clicks=1)
        m.hotkey.assert_called_once_with("ctrl", "s")
        m.press.assert_called_once_with("f5")
        m.mouseDown.assert_called_once_with(x=20, y=20, button="right")
        m.mouseUp.assert_called_once_with(button="right")
        # Clicks, holds and key presses all count toward the click limit.
        self.assertEqual(outcome.clicks, 4)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_key_step_does_not_move_the_mouse(self, m):
        _mock(m)
        EngineRun(steps=[ClickStep(type="key", key="enter")], repeat=1).start().wait()
        m.press.assert_called_once_with("enter")
        m.click.assert_not_called()
        m.moveTo.assert_not_called()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_steps_keep_their_order_across_rounds(self, m):
        _mock(m)
        order = []
        m.click.side_effect = lambda **kw: order.append("click")
        m.press.side_effect = lambda key: order.append(key)
        steps = [ClickStep(1, 1), ClickStep(type="key", key="tab")]
        EngineRun(steps=steps, repeat=2).start().wait()
        self.assertEqual(order, ["click", "tab", "click", "tab"])

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_only_point_steps_add_windows_for_pause_when_unfocused(self, m):
        _mock(m)
        run = EngineRun(steps=[ClickStep(type="key", key="a"), ClickStep(5, 6)])
        run.engine._steps = tuple(run.kwargs["steps"])
        with (
            patch("autoclicker.core.click_engine.root_window_at", return_value=42) as at,
            patch.object(run.engine, "_is_ours", return_value=False),
        ):
            self.assertEqual(run.engine._windows_under_steps(), frozenset({42}))
        self.assertEqual(at.call_args_list, [call(5, 6)])

    def test_point(self):
        self.assertEqual(ClickStep(3, 4).point, (3, 4))
        self.assertEqual(ClickStep(3, 4, type="hold").point, (3, 4))
        self.assertIsNone(ClickStep(type="key", key="a").point)


class TestEngineWaitSteps(unittest.TestCase):
    """wait_image and wait_pixel steps hold the sequence until their target shows."""

    @staticmethod
    def image(*results):
        image = MagicMock()
        image.locate.side_effect = list(results)
        return image

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_wait_image_then_click_where_it_was_found(self, m):
        _mock(m)
        image = self.image(None, None, (300, 400))
        steps = [ClickStep(type="wait_image", image=image, click=True, button="right")]
        outcome = EngineRun(steps=steps, repeat=1).start().wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(image.locate.call_count, 3)
        m.click.assert_called_once_with(x=300, y=400, button="right", clicks=1)
        self.assertEqual(outcome.clicks, 1)

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_a_wait_alone_is_not_a_click(self, m):
        _mock(m)
        steps = [ClickStep(type="wait_image", image=self.image((1, 1))), ClickStep(5, 5)]
        outcome = EngineRun(steps=steps, repeat=1).start().wait()
        m.click.assert_called_once_with(x=5, y=5, button="left", clicks=1)
        self.assertEqual(outcome.clicks, 1)

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_wait_pixel_until_it_matches(self, m):
        _mock(m)
        m.pixel.side_effect = [(0, 0, 0), (250, 10, 10), (255, 0, 0)]
        steps = [
            ClickStep(7, 8, type="wait_pixel", rgb=(255, 0, 0), tolerance=4),
            ClickStep(1, 1),
        ]
        EngineRun(steps=steps, repeat=1).start().wait()
        self.assertEqual(m.pixel.call_count, 3)  # (250, 10, 10) is outside the tolerance
        m.pixel.assert_called_with(7, 8)
        m.click.assert_called_once()

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_timeout_stops_the_run_with_the_step_named(self, m):
        _mock(m)
        image = MagicMock()
        image.locate.return_value = None
        steps = [ClickStep(1, 1), ClickStep(type="wait_image", image=image, timeout_ms=30)]
        outcome = EngineRun(steps=steps).start().wait()
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(outcome.message, "Step 2: the image didn't appear within 0.03 s")

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_timeout_with_skip_goes_on_to_the_next_step(self, m):
        _mock(m)
        m.pixel.return_value = (0, 0, 0)
        steps = [
            ClickStep(1, 1, type="wait_pixel", rgb=(9, 9, 9), tolerance=0, timeout_ms=20,
                      on_timeout="skip"),
            ClickStep(2, 2),
        ]  # fmt: skip
        outcome = EngineRun(steps=steps, repeat=2).start().wait()
        self.assertEqual(outcome.message, "Done: ran the sequence 2 times")
        self.assertEqual(m.click.call_count, 2)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_stop_ends_a_wait_without_a_timeout(self, m):
        _mock(m)
        image = MagicMock()
        image.locate.return_value = None
        run = EngineRun(steps=[ClickStep(type="wait_image", image=image)]).start()
        threading.Timer(0.2, run.engine.stop_clicking).start()
        outcome = run.wait()
        self.assertEqual(outcome.reason, STOP_USER)
        self.assertFalse(run.engine.is_paused)

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_failsafe_corner_ends_a_wait(self, m):
        _mock(m)
        image = MagicMock()
        image.locate.return_value = None
        run = EngineRun(steps=[ClickStep(type="wait_image", image=image)])
        with patch.object(run.engine, "_cursor_in_failsafe_corner", side_effect=[False, True]):
            outcome = run.start().wait()
        self.assertEqual(outcome.reason, STOP_SAFETY)

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_time_limit_ends_a_wait(self, m):
        _mock(m)
        image = MagicMock()
        image.locate.return_value = None
        run = EngineRun(steps=[ClickStep(type="wait_image", image=image)])
        with patch.object(run.engine, "_limit_reached", side_effect=[None, None, "Done: time"]):
            outcome = run.start().wait()
        self.assertEqual(outcome.message, "Done: time")

    @patch("autoclicker.core.click_engine._STEP_WAIT_POLL_SECONDS", 0.001)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_unreadable_screen_ends_the_run(self, m):
        _mock(m)
        image = MagicMock()
        image.locate.side_effect = OSError("no screen")
        outcome = EngineRun(steps=[ClickStep(type="wait_image", image=image)]).start().wait()
        self.assertEqual(outcome.reason, STOP_ERROR)
        self.assertIn("Could not read the screen", outcome.message)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_the_status_says_which_step_is_waiting(self, m):
        _mock(m)
        image = MagicMock()
        image.locate.return_value = None
        run = EngineRun(steps=[ClickStep(1, 1), ClickStep(type="wait_image", image=image)])
        run.start()
        deadline = time.monotonic() + 2
        while not run.engine.is_paused and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(run.engine.pause_reason, "the image in step 2")
        run.engine.stop_clicking()
        run.wait()


class TestStepValidation(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = SettingsManager(os.path.join(self._dir.name, "s.json"))

    def validate(self, sequence):
        raw = {
            "target_mode": "sequence",
            "x_coord": "",
            "y_coord": "",
            "interval": "100",
            "interval_unit": "ms",
            "sequence": sequence,
            "sequence_repeat": "0",
        }
        return self.settings.validate_all_settings(raw, 1920, 1080)

    def steps(self, sequence):
        result = self.validate(sequence)
        self.assertTrue(result["valid"], result["errors"])
        return result["sanitized_settings"]["sequence"]

    def error(self, sequence):
        result = self.validate(sequence)
        self.assertFalse(result["valid"])
        return result["errors"]["sequence"]

    def test_old_steps_load_unchanged_as_clicks(self):
        old = {"x": 5, "y": 6, "button": "right", "click_type": "double", "delay_ms": 250}
        self.assertEqual(self.steps([old]), [old])

    def test_click_steps_are_stored_without_a_type(self):
        (step,) = self.steps([{"type": "click", "x": 1, "y": 2}])
        self.assertNotIn("type", step)

    def test_key_step_keeps_only_its_fields(self):
        (step,) = self.steps([{"type": "key", "key": " Ctrl + S ", "x": 9, "button": "right"}])
        self.assertEqual(step, {"type": "key", "key": "ctrl+s", "delay_ms": 0})

    def test_hold_step(self):
        (step,) = self.steps([{"type": "hold", "x": 1, "y": 2, "hold_ms": "750"}])
        self.assertEqual(
            step, {"type": "hold", "x": 1, "y": 2, "button": "left", "hold_ms": 750, "delay_ms": 0}
        )

    def test_a_sequence_of_only_key_steps_is_valid(self):
        self.assertEqual(len(self.steps([{"type": "key", "key": "f5"}])), 1)

    def test_errors_name_the_step(self):
        self.assertIn("Step 2 type", self.error([{"x": 1, "y": 1}, {"type": "scroll"}]))
        self.assertIn("Step 1 key", self.error([{"type": "key"}]))
        self.assertIn("Unknown key: nope", self.error([{"type": "key", "key": "nope"}]))
        self.assertIn("Step 1 hold", self.error([{"type": "hold", "x": 1, "y": 1}]))
        self.assertIn("Step 1 hold", self.error([{"type": "hold", "x": 1, "y": 1, "hold_ms": 0}]))
        self.assertIn("Step 1 has no X", self.error([{"type": "hold", "y": 1, "hold_ms": 5}]))

    def test_wait_image_defaults_and_click_fields(self):
        region = [10, 20, 30, 40]
        (plain,) = self.steps(
            [{"type": "wait_image", "image_path": "a.png", "image_region": region}]
        )
        self.assertEqual(
            plain,
            {
                "type": "wait_image",
                "image_path": "a.png",
                "image_region": region,
                "image_tolerance": 0,
                "timeout_ms": 0,
                "on_timeout": "stop",
                "click": False,
                "delay_ms": 0,
            },
        )
        (clicking,) = self.steps(
            [
                {"type": "wait_image", "image_path": "a.png", "image_region": region,
                 "click": True, "button": "right", "timeout_ms": "5000", "on_timeout": "skip"}
            ]
        )  # fmt: skip
        self.assertEqual(
            (clicking["button"], clicking["click_type"], clicking["timeout_ms"]),
            ("right", "single", 5000),
        )
        self.assertEqual(clicking["on_timeout"], "skip")

    def test_wait_pixel(self):
        (step,) = self.steps([{"type": "wait_pixel", "x": 3, "y": 4, "color": "#3A7BD5"}])
        self.assertEqual(
            step,
            {
                "type": "wait_pixel",
                "x": 3,
                "y": 4,
                "color": "#3A7BD5",
                "tolerance": 16,
                "timeout_ms": 0,
                "on_timeout": "stop",
                "delay_ms": 0,
            },
        )

    def test_wait_errors_name_the_step(self):
        image = {"type": "wait_image", "image_path": "a.png", "image_region": [0, 0, 5, 5]}
        pixel = {"type": "wait_pixel", "x": 1, "y": 1, "color": "#000000"}
        self.assertIn("Step 1 image: Capture an image first", self.error([{"type": "wait_image"}]))
        self.assertIn("Step 1 color", self.error([{**pixel, "color": "blue"}]))
        self.assertIn("Step 1 color", self.error([{"type": "wait_pixel", "x": 1, "y": 1}]))
        self.assertIn("Step 1 tolerance", self.error([{**pixel, "tolerance": 300}]))
        self.assertIn("Step 1 tolerance", self.error([{**image, "image_tolerance": 99}]))
        self.assertIn("Step 1 timeout", self.error([{**pixel, "timeout_ms": -1}]))
        self.assertIn("Step 1 on timeout", self.error([{**pixel, "on_timeout": "retry"}]))
        self.assertIn("Step 1 click", self.error([{**image, "click": "yes"}]))
        self.assertIn("Step 2", self.error([pixel, {**pixel, "x": 5000}]))  # off screen

    def test_key_step_has_no_point_to_check(self):
        steps = [{"type": "key", "key": "a"}, {"x": 5000, "y": 1}]
        self.assertIn("Step 2", self.error(steps))


class TestControllerSteps(unittest.TestCase):
    DESKTOP = ScreenBounds(0, 0, 1920, 1080)

    def test_old_and_new_steps_become_engine_steps(self):
        steps, error = _sequence_steps(
            [
                {"x": 1, "y": 2, "button": "left", "click_type": "single", "delay_ms": 0},
                {"type": "key", "key": "f5", "delay_ms": 0},
                {"type": "wait_pixel", "x": 3, "y": 4, "color": "#3a7bd5", "tolerance": 9,
                 "timeout_ms": 0, "on_timeout": "stop", "delay_ms": 0},
            ],
            self.DESKTOP,
        )  # fmt: skip
        self.assertIsNone(error)
        assert steps is not None
        self.assertEqual(steps[0], ClickStep(1, 2))
        self.assertEqual(steps[1], ClickStep(type="key", key="f5"))
        self.assertEqual(steps[2].rgb, (0x3A, 0x7B, 0xD5))

    def test_wait_image_loads_its_capture(self):
        target = MagicMock()
        with patch(
            "autoclicker.app.controller._load_image_target", return_value=(target, None)
        ) as load:
            steps, error = _sequence_steps(
                [{"type": "wait_image", "image_path": "p.png", "image_region": [1, 2, 3, 4],
                  "image_tolerance": 5, "timeout_ms": 0, "on_timeout": "stop", "click": False,
                  "delay_ms": 0}],
                self.DESKTOP,
            )  # fmt: skip
        self.assertIsNone(error)
        assert steps is not None
        self.assertIs(steps[0].image, target)
        self.assertEqual(
            load.call_args.args[0],
            {"image_path": "p.png", "image_region": [1, 2, 3, 4], "image_tolerance": 5},
        )

    def test_a_missing_capture_names_the_step(self):
        steps, error = _sequence_steps(
            [{"type": "key", "key": "a"},
             {"type": "wait_image", "image_path": "C:/elsewhere.png", "image_region": [0, 0, 5, 5]}],
            self.DESKTOP,
        )  # fmt: skip
        self.assertIsNone(steps)
        assert error is not None
        self.assertTrue(error.startswith("Step 2: "), error)


class TestDescribeStep(unittest.TestCase):
    def test_each_type(self):
        self.assertEqual(
            describe_step({"x": 1, "y": 2, "button": "left", "click_type": "double"}),
            "(1, 2)  left double",
        )
        self.assertEqual(
            describe_step({"type": "hold", "x": 1, "y": 2, "button": "right", "hold_ms": 500}),
            "(1, 2)  right hold 500 ms",
        )
        self.assertEqual(
            describe_step({"type": "hold", "x": 1, "y": 2, "button": "left", "hold_ms": 1200}),
            "(1, 2)  left hold 1.2 s",
        )
        self.assertEqual(describe_step({"type": "key", "key": "ctrl+s"}), "key ctrl+s")
        self.assertEqual(describe_step({"type": "wait_image"}), "wait for image")
        self.assertEqual(
            describe_step({"type": "wait_image", "timeout_ms": 10000, "click": True}),
            "wait for image, click it",
        )
        self.assertEqual(
            describe_step({"type": "wait_pixel", "x": 3, "y": 4, "timeout_ms": 500}),
            "wait for pixel (3, 4)",
        )


if __name__ == "__main__":
    unittest.main()
