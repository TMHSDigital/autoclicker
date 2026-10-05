"""Recording sequences (#86)."""

import threading
import unittest
from unittest.mock import MagicMock

from autoclicker.core.recorder import ClickRecorder, RecordedClick, clicks_to_steps


def click(x, y, t, button="left"):
    return RecordedClick(x, y, button, t)


class TestClicksToSteps(unittest.TestCase):
    def test_gaps_become_rounded_waits(self):
        steps = clicks_to_steps(
            [click(10, 10, 0.0), click(20, 20, 0.512), click(30, 30, 1.9)],
            double_click_window=0.3,
        )
        self.assertEqual([s["delay_ms"] for s in steps], [500, 1400, 0])
        self.assertEqual([(s["x"], s["y"]) for s in steps], [(10, 10), (20, 20), (30, 30)])
        self.assertTrue(all(s["click_type"] == "single" for s in steps))

    def test_double_click_is_merged(self):
        steps = clicks_to_steps(
            [click(10, 10, 0.0, "right"), click(11, 12, 0.2, "right"), click(50, 50, 1.0)],
            double_click_window=0.3,
        )
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["click_type"], "double")
        self.assertEqual(steps[0]["button"], "right")
        self.assertEqual(steps[0]["delay_ms"], 1000)

    def test_not_merged_when_far_apart_slow_or_other_button(self):
        for second in (click(40, 10, 0.1), click(10, 10, 0.9), click(10, 10, 0.1, "right")):
            with self.subTest(second=second):
                steps = clicks_to_steps([click(10, 10, 0.0), second], double_click_window=0.3)
                self.assertEqual(len(steps), 2)

    def test_long_gaps_are_capped(self):
        steps = clicks_to_steps([click(1, 1, 0.0), click(2, 2, 500.0)], double_click_window=0.3)
        self.assertEqual(steps[0]["delay_ms"], 60_000)

    def test_empty(self):
        self.assertEqual(clicks_to_steps([], double_click_window=0.3), [])


class FakeUser32:
    """Just enough of user32 for the hook thread: a message loop ended by WM_QUIT."""

    def __init__(self, hook_ok=True):
        self._quit = threading.Event()
        self.hook_ok = hook_ok
        self.unhooked = []
        for name in ("CallNextHookEx", "SetWindowsHookExW", "UnhookWindowsHookEx"):
            setattr(self, name, MagicMock())
        self.SetWindowsHookExW.side_effect = lambda *a: 1234 if self.hook_ok else 0
        self.UnhookWindowsHookEx.side_effect = self.unhooked.append

    def GetMessageW(self, *_args):
        self._quit.wait(5)
        return 0

    def PostThreadMessageW(self, *_args):
        self._quit.set()
        return 1


class TestRecorderLifecycle(unittest.TestCase):
    def test_hook_is_removed_on_stop(self):
        user32 = FakeUser32()
        recorder = ClickRecorder(on_click=lambda c: None, user32=user32)
        self.assertTrue(recorder.start())
        self.assertTrue(recorder.recording)
        recorder.stop()
        self.assertFalse(recorder.recording)
        self.assertEqual(user32.unhooked, [1234])
        recorder.stop()  # idempotent

    def test_failed_hook_reports_false(self):
        recorder = ClickRecorder(on_click=lambda c: None, user32=FakeUser32(hook_ok=False))
        self.assertFalse(recorder.start())
