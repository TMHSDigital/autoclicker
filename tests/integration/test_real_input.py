"""Real input end to end (#83): the engine drives the real mouse and keyboard.

These tests move the real cursor and click, so they only run when
AUTOCLICKER_REAL_INPUT=1 (set by the "real-input" CI job on a Windows
runner). Each test opens its own topmost Tk target window, runs the real
ClickEngine against it with real PyAutoGUI, and checks which events arrived.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import unittest

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AUTOCLICKER_REAL_INPUT") != "1" or sys.platform != "win32",
        reason="moves the real mouse; set AUTOCLICKER_REAL_INPUT=1 on Windows",
    ),
]

if os.environ.get("AUTOCLICKER_REAL_INPUT") == "1" and sys.platform == "win32":
    # Same order as the app: per-monitor DPI awareness before PyAutoGUI loads.
    from autoclicker.core.dpi import enable_per_monitor_dpi_awareness

    enable_per_monitor_dpi_awareness()

import tkinter as tk  # noqa: E402

TARGET_BG = "#3366cc"


class Target:
    """A topmost window that records mouse and key events in screen coordinates."""

    def __init__(self, root: tk.Misc, x: int, y: int, w: int = 240, h: int = 160) -> None:
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.configure(bg=TARGET_BG)
        self.window.attributes("-topmost", True)
        self.events: list[tuple] = []
        for sequence in (
            "<ButtonPress-1>",
            "<ButtonPress-3>",
            "<ButtonRelease-1>",
            "<Double-Button-3>",
        ):
            self.window.bind(sequence, self._record(sequence))
        self.window.bind(
            "<KeyPress>", lambda e: self.events.append(("key", e.keysym, time.monotonic()))
        )
        self.window.update()
        self.cx = x + w // 2
        self.cy = y + h // 2

    def _record(self, sequence):
        def handler(event):
            self.events.append((sequence, event.x_root, event.y_root, time.monotonic()))

        return handler

    def of(self, sequence: str) -> list[tuple]:
        return [e for e in self.events if e[0] == sequence]


class RealInputCase(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def run_engine(self, timeout=10.0, **kwargs):
        """Start the real engine and pump Tk until the run ends."""
        from autoclicker.core.click_engine import ClickEngine

        engine = ClickEngine(enable_performance_monitoring=False)
        engine.configure_safety(failsafe=True, max_cps=0)
        done = threading.Event()
        outcomes = []
        args = dict(
            interval=150, variation=0, burst_clicks=1, burst_pause=0, max_clicks=0,
            auto_stop_minutes=0, mouse_button="left", click_type="single",
        )  # fmt: skip
        args.update(kwargs)
        x, y = args.pop("x", None), args.pop("y", None)
        self.assertTrue(
            engine.start_clicking(
                x, y, on_finished=lambda o: (outcomes.append(o), done.set()), **args
            )
        )
        deadline = time.monotonic() + timeout
        while not done.is_set():
            self.root.update()
            if time.monotonic() > deadline:
                engine.emergency_stop()
                self.fail("run did not finish")
            time.sleep(0.01)
        for _ in range(30):  # let the last events arrive
            self.root.update()
            time.sleep(0.01)
        engine.stop_clicking()
        return outcomes[0]


class TestRealClicks(RealInputCase):
    def test_fixed_point_lands_exactly(self):
        target = Target(self.root, 200, 200)
        outcome = self.run_engine(x=target.cx, y=target.cy, max_clicks=3)
        presses = target.of("<ButtonPress-1>")
        self.assertEqual(outcome.clicks, 3)
        self.assertEqual(len(presses), 3)
        for _seq, x, y, _t in presses:
            self.assertEqual((x, y), (target.cx, target.cy))

    def test_clicks_return_to_the_target_after_the_mouse_moves(self):
        """#62 regression with real input."""
        import pyautogui

        target = Target(self.root, 200, 200)
        decoy = Target(self.root, 500, 200)

        def move_away():
            time.sleep(0.2)
            pyautogui.moveTo(decoy.cx, decoy.cy)

        threading.Thread(target=move_away, daemon=True).start()
        self.run_engine(x=target.cx, y=target.cy, max_clicks=4, interval=200)
        self.assertEqual(len(target.of("<ButtonPress-1>")), 4)
        self.assertEqual(decoy.of("<ButtonPress-1>"), [])

    def test_right_double_click(self):
        target = Target(self.root, 200, 200)
        self.run_engine(
            x=target.cx, y=target.cy, max_clicks=1, mouse_button="right", click_type="double"
        )
        self.assertEqual(len(target.of("<Double-Button-3>")), 1)

    def test_sequence_clicks_each_window_in_order(self):
        from autoclicker.core.click_engine import ClickStep

        first = Target(self.root, 200, 200)
        second = Target(self.root, 500, 200)
        self.run_engine(
            steps=[ClickStep(first.cx, first.cy, delay_ms=100), ClickStep(second.cx, second.cy)],
            repeat=2,
        )
        times = sorted(
            [("a", e[3]) for e in first.of("<ButtonPress-1>")]
            + [("b", e[3]) for e in second.of("<ButtonPress-1>")],
            key=lambda item: item[1],
        )
        self.assertEqual([name for name, _ in times], ["a", "b", "a", "b"])

    def test_hold_presses_for_the_hold_time(self):
        target = Target(self.root, 200, 200)
        self.run_engine(x=target.cx, y=target.cy, max_clicks=1, action="hold", hold_ms=400)
        (press,) = target.of("<ButtonPress-1>")
        (release,) = target.of("<ButtonRelease-1>")
        self.assertGreaterEqual(release[3] - press[3], 0.3)

    def test_key_press_reaches_the_focused_window(self):
        target = Target(self.root, 200, 200)
        target.window.focus_force()
        target.window.update()
        self.run_engine(max_clicks=2, action="key", key="f5")
        self.assertEqual([e[1] for e in target.events if e[0] == "key"], ["F5", "F5"])


class TestRealPixel(RealInputCase):
    def test_pixel_condition_reads_the_window_color(self):
        import pyautogui

        from autoclicker.core.click_engine import PixelCondition

        target = Target(self.root, 200, 200)
        rgb = (0x33, 0x66, 0xCC)
        for _ in range(20):  # let the window paint
            self.root.update()
            time.sleep(0.02)
        seen = tuple(pyautogui.pixel(target.cx + 60, target.cy))[:3]
        self.assertTrue(
            all(abs(a - b) <= 8 for a, b in zip(seen, rgb, strict=True)),
            f"screen pixel is {seen}, window color is {rgb}",
        )
        condition = PixelCondition(target.cx + 60, target.cy, rgb, tolerance=8, on_mismatch="stop")
        outcome = self.run_engine(x=target.cx, y=target.cy, max_clicks=2, condition=condition)
        self.assertEqual(outcome.message, "Done: reached 2 clicks")

        mismatch = PixelCondition(target.cx + 60, target.cy, (255, 0, 0), on_mismatch="stop")
        outcome = self.run_engine(x=target.cx, y=target.cy, condition=mismatch)
        self.assertEqual(outcome.message, "Stopped: the watched pixel changed")
