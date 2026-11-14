"""Sequence step types: click, hold and key steps in one sequence (#119)."""

import os
import tempfile
import unittest
from unittest.mock import call, patch

from autoclicker.core.click_engine import STOP_COMPLETED, ClickStep
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

    def test_key_step_has_no_point_to_check(self):
        steps = [{"type": "key", "key": "a"}, {"x": 5000, "y": 1}]
        self.assertIn("Step 2", self.error(steps))


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


if __name__ == "__main__":
    unittest.main()
