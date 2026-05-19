"""
Soak tests for ClickEngine: long-running behavior under sustained click load.

These tests are hermetic (pyautogui mocked, time real but compressed via
small intervals) and validate the engine's behavior over thousands of clicks
in a few seconds of wall time.

The full long-duration soak lives in scripts/soak_click_engine.py and is
opt-in (real pyautogui, real time).
"""

from __future__ import annotations

import gc
import threading
import time
import tracemalloc
import unittest
from unittest.mock import patch

from autoclicker.core.click_engine import ClickEngine


class TestSoakSustainedClicking(unittest.TestCase):
    """Engine should remain stable and bounded across thousands of clicks."""

    def test_sustained_clicking_is_stable(self):
        """Patch the pyautogui module attribute with a lightweight stub so
        Mock's call-tracking machinery doesn't dominate the allocation budget."""
        import pyautogui as real_pyautogui

        from autoclicker.core import click_engine as ce

        class _Stub:
            PAUSE = 0
            FAILSAFE = False
            FailSafeException = real_pyautogui.FailSafeException
            PyAutoGUIException = real_pyautogui.PyAutoGUIException

            @staticmethod
            def size():
                return (1920, 1080)

            click = doubleClick = rightClick = middleClick = staticmethod(lambda *a, **kw: None)
            moveTo = staticmethod(lambda *a, **kw: None)

        original = ce.pyautogui
        ce.pyautogui = _Stub()
        try:
            engine = ClickEngine(enable_performance_monitoring=True)
            engine.configure_safety(failsafe=False, max_cps=10_000, pause_when_unfocused=False)

            gc.collect()
            tracemalloc.start()
            snap_before = tracemalloc.take_snapshot()
            threads_before = threading.active_count()

            engine.start_clicking(
                x=100,
                y=100,
                interval=0,
                variation=0,
                burst_clicks=1,
                burst_pause=0,
                max_clicks=5_000,
                auto_stop_minutes=0,
                mouse_button="left",
                click_type="single",
            )

            deadline = time.time() + 10.0
            while engine.is_running and time.time() < deadline:
                time.sleep(0.05)

            engine.stop_clicking()
            gc.collect()

            snap_after = tracemalloc.take_snapshot()
            tracemalloc.stop()
            threads_after = threading.active_count()
        finally:
            ce.pyautogui = original

        self.assertGreaterEqual(engine.click_count, 5_000, "engine stopped before reaching max")
        self.assertLessEqual(
            len(engine.performance_metrics["click_timings"]),
            1000,
            "timings deque must stay bounded",
        )
        self.assertLessEqual(
            len(engine._recent_click_ts),
            1024,
            "recent-click ts deque must stay bounded",
        )
        self.assertEqual(
            threads_after,
            threads_before,
            "click thread must be joined and removed on stop",
        )

        # Budget: ~500 KiB for incidental Python/test machinery across 5k clicks.
        diff = snap_after.compare_to(snap_before, "filename")
        total_delta = sum(stat.size_diff for stat in diff)
        self.assertLess(
            total_delta,
            512 * 1024,
            f"unexpected heap growth: {total_delta} bytes",
        )

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_runaway_guard_uses_sliding_window(self, mock_pyautogui):
        """Lifetime-avg guard would never trip after a slow lead-in. Sliding
        window should detect the spike within ~1s of crossing the ceiling."""
        mock_pyautogui.size.return_value = (1920, 1080)

        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = time.time() - 60.0  # simulate 60s of warm runtime
        engine.click_count = 60  # 1 cps over the last minute
        engine.max_cps_ceiling = 20

        # Lifetime avg is 1 cps; old code would return False here even with a
        # huge spike. Fill recent_click_ts with a burst above ceiling.
        now = time.time()
        for i in range(40):
            engine._recent_click_ts.append(now - 0.5 + i * 0.01)

        self.assertTrue(
            engine._check_runaway_cps(),
            "sliding-window guard must trip on recent spike",
        )

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_queue_overflow_increments_drop_counter(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.max_queue_size = 3
        engine.enable_queuing = True  # do not start processor; want overflow

        for _ in range(10):
            engine._perform_click(50, 50, "left", "single")

        self.assertEqual(len(engine.click_queue), 3)
        self.assertEqual(engine.dropped_click_count, 7)
        status = engine.get_status()
        self.assertEqual(status["dropped_click_count"], 7)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_screen_size_is_cached_per_session(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._click_loop = lambda *a, **kw: None  # no real loop

        engine.start_clicking(10, 10, 0, 0, 1, 0, 1, 0, "left", "single")
        # start_clicking calls size() once; subsequent _perform_click calls
        # must not call it again because the cache is populated.
        mock_pyautogui.size.reset_mock()

        for _ in range(50):
            engine._perform_click(10, 10, "left", "single")

        mock_pyautogui.size.assert_not_called()
        engine.stop_clicking()


if __name__ == "__main__":
    unittest.main()
