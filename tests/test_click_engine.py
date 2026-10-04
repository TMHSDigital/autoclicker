"""
Unit tests for ClickEngine with mocked pyautogui and time.
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import (
    STOP_COMPLETED,
    STOP_EMERGENCY,
    STOP_ERROR,
    STOP_SAFETY,
    STOP_USER,
    ClickEngine,
)
from autoclicker.core.exceptions import ClickEngineError, CoordinateError, SafetyError


class TestClickEngineLifecycle(unittest.TestCase):
    """Start/stop and status."""

    def test_start_returns_false_when_already_running(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        self.assertFalse(engine.start_clicking(0, 0, 100, 0, 1, 0, 0, 0, "left", "single"))

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_start_and_stop_clicking(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._click_loop = MagicMock()

        self.assertTrue(engine.start_clicking(10, 10, 100, 0, 1, 0, 0, 0, "left", "single"))
        self.assertTrue(engine.is_running)
        self.assertIsNotNone(engine.click_thread)

        engine.stop_clicking()
        self.assertFalse(engine.is_running)
        self.assertIsNone(engine.click_thread)

    def test_emergency_stop(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine.emergency_stop()
        self.assertFalse(engine.is_running)
        self.assertTrue(engine._stop_event.is_set())

    def test_get_status_format(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine.click_count = 5
        engine.start_time = time.monotonic() - 65

        status = engine.get_status()
        self.assertTrue(status["is_running"])
        self.assertEqual(status["click_count"], 5)
        self.assertRegex(status["runtime"], r"\d{2}:\d{2}:\d{2}")


class TestClickEnginePerformClick(unittest.TestCase):
    """Single-click paths and errors."""

    def setUp(self):
        self.engine = ClickEngine(enable_performance_monitoring=True)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_left_single_click(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        self.engine._perform_click(100, 200, "left", "single")
        mock_pyautogui.click.assert_called_once_with(x=100, y=200, button="left", clicks=1)
        self.assertEqual(self.engine.click_count, 1)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_every_click_targets_the_point_after_the_mouse_moves(self, mock_pyautogui):
        """#62: a mouse moved mid-run must not drag later clicks with it."""
        mock_pyautogui.size.return_value = (1920, 1080)
        self.engine._perform_click(50, 50, "left", "single")
        mock_pyautogui.position.return_value = (900, 700)  # user moved the mouse
        self.engine._perform_click(50, 50, "left", "single")
        self.assertEqual(mock_pyautogui.click.call_count, 2)
        for call in mock_pyautogui.click.call_args_list:
            self.assertEqual((call.kwargs["x"], call.kwargs["y"]), (50, 50))

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_left_double_click(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        self.engine._perform_click(10, 10, "left", "double")
        mock_pyautogui.click.assert_called_once_with(x=10, y=10, button="left", clicks=2)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_every_button_and_click_type(self, mock_pyautogui):
        """#51: double click works for right and middle too."""
        mock_pyautogui.size.return_value = (1920, 1080)
        for button in ("left", "right", "middle"):
            for click_type, clicks in (("single", 1), ("double", 2)):
                with self.subTest(button=button, click_type=click_type):
                    mock_pyautogui.click.reset_mock()
                    self.engine._perform_click(10, 10, button, click_type)
                    mock_pyautogui.click.assert_called_once_with(
                        x=10, y=10, button=button, clicks=clicks
                    )

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_out_of_bounds_raises_coordinate_error(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (100, 100)
        with self.assertRaises(CoordinateError):
            self.engine._perform_click(200, 50, "left", "single")

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_unsupported_button_raises(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        with self.assertRaises(ClickEngineError):
            self.engine._perform_click(10, 10, "side", "single")

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_failsafe_raises_safety_error(self, mock_pyautogui):
        import pyautogui

        mock_pyautogui.FailSafeException = pyautogui.FailSafeException
        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.click.side_effect = pyautogui.FailSafeException()
        with self.assertRaises(SafetyError):
            self.engine._perform_click(10, 10, "left", "single")

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_pyautogui_exception_wrapped(self, mock_pyautogui):
        import pyautogui

        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.click.side_effect = pyautogui.PyAutoGUIException("boom")
        with self.assertRaises(ClickEngineError):
            self.engine._perform_click(10, 10, "left", "single")


class TestClickEngineLoopAndLimits(unittest.TestCase):
    """Burst, wait, should_stop, click loop."""

    @patch("autoclicker.core.click_engine.time.sleep")
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_perform_burst_multiple_clicks(self, mock_pyautogui, mock_sleep):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        with patch.object(engine._stop_event, "wait") as mock_wait:
            engine._perform_burst(1, 1, 3, 0.05, "left", "single")
        self.assertEqual(engine.click_count, 3)
        self.assertEqual(mock_wait.call_count, 2)
        mock_sleep.assert_not_called()

    @patch("autoclicker.core.click_engine.random.randint", return_value=10)
    def test_wait_with_variation(self, mock_randint):
        engine = ClickEngine(enable_performance_monitoring=False)
        with patch.object(engine._stop_event, "wait") as mock_wait:
            engine._wait_with_variation(100, 20)
        mock_wait.assert_called_once()
        self.assertAlmostEqual(mock_wait.call_args.kwargs["timeout"], 0.11)

    def test_wait_zero_interval_no_sleep(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        with patch.object(engine._stop_event, "wait") as mock_wait:
            engine._wait_with_variation(0, 0)
        mock_wait.assert_not_called()

    def test_limit_max_clicks(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.click_count = 10
        self.assertEqual(engine._limit_reached(10, 0), "Done: reached 10 clicks")

    @patch("autoclicker.core.click_engine.time.monotonic")
    def test_limit_auto_stop_minutes(self, mock_time):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = 1000.0
        mock_time.return_value = 1000.0 + 61 * 60
        self.assertIsNotNone(engine._limit_reached(0, 1))

    def test_wall_clock_jump_does_not_affect_auto_stop(self):
        """#52: elapsed time uses a monotonic clock, not the wall clock."""
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = time.monotonic()
        with patch("autoclicker.core.click_engine.time.time", return_value=time.time() + 86400):
            self.assertIsNone(engine._limit_reached(0, 1))
            self.assertEqual(engine.get_status()["runtime"], "00:00:00")

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_click_loop_invokes_callbacks(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        complete = MagicMock()

        def stop_after_burst(*_args, **_kwargs):
            engine.is_running = False

        with (
            patch.object(engine, "_perform_burst", side_effect=stop_after_burst),
            patch.object(engine, "_wait_with_variation"),
        ):
            engine._click_loop(1, 1, 10, 0, 1, 0, 0, 0, "left", "single", complete)
        complete.assert_called_once()
        self.assertFalse(engine.is_running)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_max_clicks_clears_running_and_allows_restart(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        complete = MagicMock()
        self.assertTrue(engine.start_clicking(1, 1, 0, 0, 1, 0, 1, 0, "left", "single", complete))
        self.assertIsNotNone(engine.click_thread)
        engine.click_thread.join(timeout=2.0)
        self.assertFalse(engine.is_running)
        complete.assert_called_once()
        engine.stop_clicking()
        self.assertTrue(engine.start_clicking(1, 1, 0, 0, 1, 0, 1, 0, "left", "single"))
        engine.stop_clicking()

    def test_start_returns_false_when_click_thread_still_alive(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        alive = MagicMock()
        alive.is_alive.return_value = True
        engine.click_thread = alive
        engine.is_running = False
        self.assertFalse(engine.start_clicking(0, 0, 100, 0, 1, 0, 0, 0, "left", "single"))

    def test_emergency_stop_signals_without_joining(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        thread = MagicMock()
        thread.is_alive.return_value = True
        engine.click_thread = thread
        engine.is_running = True
        engine.emergency_stop()
        self.assertFalse(engine.is_running)
        self.assertTrue(engine._stop_event.is_set())
        thread.join.assert_not_called()

    def test_safety_stop_from_click_thread_does_not_join_self(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine.click_thread = threading.current_thread()
        engine._trigger_safety_stop("test reason")
        engine.stop_clicking()  # must not try to join the current thread
        self.assertFalse(engine.is_running)
        self.assertIs(engine.click_thread, threading.current_thread())

    def test_runaway_reports_safety_outcome(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine.start_time = time.monotonic()
        finished = MagicMock()
        with patch.object(engine, "_check_runaway_cps", return_value=True):
            engine._click_loop(1, 1, 10, 0, 1, 0, 0, 0, "left", "single", finished)
        finished.assert_called_once()
        outcome = finished.call_args.args[0]
        self.assertEqual(outcome.reason, STOP_SAFETY)
        self.assertIn("Runaway guard", outcome.message)
        self.assertFalse(engine.is_running)
        self.assertTrue(engine._safety_fired)

    def test_failsafe_in_loop_reports_safety_outcome(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        finished = MagicMock()
        with patch.object(
            engine,
            "_perform_burst",
            side_effect=SafetyError("fail_safe", "detected", "corner"),
        ):
            engine._click_loop(1, 1, 10, 0, 1, 0, 0, 0, "left", "single", finished)
        outcome = finished.call_args.args[0]
        self.assertEqual(outcome.reason, STOP_SAFETY)
        self.assertIn("Failsafe", outcome.message)
        self.assertFalse(engine.is_running)


class TestRunOutcome(unittest.TestCase):
    """#41/#42: every run reports exactly one outcome with the right reason."""

    def _run(self, *, max_clicks=0, stop=None, click_error=None, interval=5):
        outcomes: list = []
        with patch("autoclicker.core.click_engine.pyautogui") as mock_pyautogui:
            mock_pyautogui.size.return_value = (1920, 1080)
            mock_pyautogui.FailSafeException = type("FailSafeException", (Exception,), {})
            mock_pyautogui.PyAutoGUIException = type("PyAutoGUIException", (Exception,), {})
            if click_error is not None:
                mock_pyautogui.click.side_effect = click_error
            engine = ClickEngine(enable_performance_monitoring=False)
            engine.configure_safety(max_cps=0)
            self.assertTrue(
                engine.start_clicking(
                    10, 10, interval, 0, 1, 0, max_clicks, 0, "left", "single", outcomes.append
                )
            )
            thread = engine.click_thread
            assert thread is not None
            if stop is not None:
                time.sleep(0.05)
                getattr(engine, stop)()
            thread.join(timeout=2.0)
            time.sleep(0.05)
        self.assertEqual(len(outcomes), 1, outcomes)
        return outcomes[0]

    def test_user_stop(self):
        self.assertEqual(self._run(stop="stop_clicking").reason, STOP_USER)

    def test_emergency_stop(self):
        outcome = self._run(stop="emergency_stop")
        self.assertEqual(outcome.reason, STOP_EMERGENCY)
        self.assertEqual(outcome.message, "Emergency stop")

    def test_max_clicks(self):
        outcome = self._run(max_clicks=3, interval=0)
        self.assertEqual(outcome.reason, STOP_COMPLETED)
        self.assertEqual(outcome.message, "Done: reached 3 clicks")
        self.assertEqual(outcome.clicks, 3)

    def test_click_error_is_reported_not_swallowed(self):
        outcome = self._run(click_error=RuntimeError("boom"))
        self.assertEqual(outcome.reason, STOP_ERROR)
        self.assertIsInstance(outcome.error, ClickEngineError)
        self.assertIn("boom", outcome.message)

    def test_auto_stop_message(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = time.monotonic() - 61
        self.assertEqual(engine._limit_reached(0, 1), "Done: auto-stopped after 1 minute")


class TestClickEnginePerformance(unittest.TestCase):
    """Metrics helpers."""

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_performance_metrics_after_clicks(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        engine.start_time = time.monotonic()
        engine._perform_click(5, 5, "left", "single")
        engine._perform_click(5, 5, "left", "single")

        metrics = engine.get_performance_metrics()
        self.assertEqual(metrics["click_success_count"], 2)
        self.assertGreater(metrics["success_rate"], 0)
        self.assertIn("average_click_time", metrics)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_stats_are_per_run(self, mock_pyautogui):
        """#68: each start resets the stats, so success rate is never a lifetime figure."""
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        engine.stats.successes = 99
        engine.stats.errors = 99
        engine.start_clicking(5, 5, 1000, 0, 1, 0, 1, 0, "left", "single")
        engine.click_thread.join(2)
        self.assertEqual(engine.stats.successes, 1)
        self.assertEqual(engine.stats.errors, 0)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_failed_click_counts_one_error(self, mock_pyautogui):
        """#68: a failed click used to be counted twice."""
        import pyautogui

        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.FailSafeException = pyautogui.FailSafeException
        mock_pyautogui.PyAutoGUIException = pyautogui.PyAutoGUIException
        mock_pyautogui.click.side_effect = pyautogui.PyAutoGUIException("boom")
        engine = ClickEngine(enable_performance_monitoring=True)
        with self.assertRaises(ClickEngineError):
            engine._perform_click(5, 5, "left", "single")
        self.assertEqual(engine.stats.errors, 1)
        self.assertEqual(engine.get_performance_metrics()["success_rate"], 0.0)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_welford_timing_stats(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        for _ in range(5):
            engine._perform_click(1, 1, "left", "single")
        metrics = engine.get_performance_metrics()
        self.assertEqual(engine.stats.timing_count, 5)
        self.assertGreater(metrics["average_click_time"], 0)
        self.assertIn("click_time_std_dev", metrics)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_status_includes_performance_when_enabled(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        engine.start_time = time.monotonic()
        engine._perform_click(1, 1, "left", "single")
        status = engine.get_status()
        self.assertIn("performance", status)


class TestMainImport(unittest.TestCase):
    """Smoke import for modular entry point."""

    def test_main_starts_app(self):
        from autoclicker import main as main_mod

        with (
            patch.object(main_mod, "AutoclickerApp") as mock_app_cls,
            patch.object(main_mod, "SingleInstance") as mock_instance_cls,
        ):
            mock_instance_cls.return_value.acquire.return_value = True
            mock_app = MagicMock()
            mock_app_cls.return_value = mock_app
            main_mod.main([])
            mock_app.run.assert_called_once()
            mock_instance_cls.return_value.watch.assert_called_once()

    def test_second_instance_signals_and_exits(self):
        from autoclicker import main as main_mod

        with (
            patch.object(main_mod, "AutoclickerApp") as mock_app_cls,
            patch.object(main_mod, "SingleInstance") as mock_instance_cls,
        ):
            mock_instance_cls.return_value.acquire.return_value = False
            main_mod.main([])
            mock_instance_cls.return_value.signal_existing.assert_called_once()
            mock_app_cls.assert_not_called()


class TestCursorMode(unittest.TestCase):
    """#48: click wherever the cursor is when no target is given."""

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_no_move_and_no_bounds_check(self, mock_pyautogui):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._perform_click(None, None, "left", "single")
        mock_pyautogui.size.assert_not_called()
        mock_pyautogui.click.assert_called_once_with(button="left", clicks=1)
        self.assertEqual(engine.click_count, 1)
