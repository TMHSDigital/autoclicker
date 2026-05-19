"""
Unit tests for ClickEngine with mocked pyautogui and time.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import ClickEngine
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
        engine.start_time = time.time() - 65

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
        mock_pyautogui.moveTo.assert_called_once_with(100, 200, duration=0)
        mock_pyautogui.click.assert_called_once()
        self.assertEqual(self.engine.click_count, 1)
        self.assertEqual(self.engine._last_click_xy, (100, 200))

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_skips_move_when_same_coordinates(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        self.engine._last_click_xy = (50, 50)
        self.engine._perform_click(50, 50, "left", "single")
        mock_pyautogui.moveTo.assert_not_called()
        mock_pyautogui.click.assert_called_once()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_left_double_click(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        self.engine._perform_click(10, 10, "left", "double")
        mock_pyautogui.doubleClick.assert_called_once()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_right_and_middle_click(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        self.engine._perform_click(10, 10, "right", "single")
        mock_pyautogui.rightClick.assert_called_once()
        self.engine._perform_click(10, 10, "middle", "single")
        mock_pyautogui.middleClick.assert_called_once()

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
        engine._perform_burst(1, 1, 3, 0.05, "left", "single")
        self.assertEqual(engine.click_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("autoclicker.core.click_engine.random.randint", return_value=10)
    @patch("autoclicker.core.click_engine.time.sleep")
    def test_wait_with_variation(self, mock_sleep, mock_randint):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._wait_with_variation(100, 20)
        mock_sleep.assert_called_once()
        args, _ = mock_sleep.call_args
        self.assertAlmostEqual(args[0], 0.11)

    @patch("autoclicker.core.click_engine.time.sleep")
    def test_wait_zero_interval_no_sleep(self, mock_sleep):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._wait_with_variation(0, 0)
        mock_sleep.assert_not_called()

    def test_should_stop_max_clicks(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.click_count = 10
        self.assertTrue(engine._should_stop(10, 0))

    @patch("autoclicker.core.click_engine.time.time")
    def test_should_stop_auto_stop_minutes(self, mock_time):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.start_time = 1000.0
        mock_time.return_value = 1000.0 + 61 * 60
        self.assertTrue(engine._should_stop(0, 1))

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
            engine._click_loop(1, 1, 10, 0, 1, 0, 0, 0, "left", "single", complete, None)
        complete.assert_called_once()


class TestClickEnginePerformance(unittest.TestCase):
    """Metrics helpers."""

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_performance_metrics_after_clicks(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        engine.start_time = time.time()
        engine._perform_click(5, 5, "left", "single")
        engine._perform_click(5, 5, "left", "single")

        metrics = engine.get_performance_metrics()
        self.assertEqual(metrics["click_success_count"], 2)
        self.assertGreater(metrics["success_rate"], 0)
        self.assertIn("average_click_time", metrics)

    def test_reset_performance_metrics(self):
        engine = ClickEngine(enable_performance_monitoring=True)
        engine.performance_metrics["click_success_count"] = 99
        engine.reset_performance_metrics()
        self.assertEqual(engine.performance_metrics["click_success_count"], 0)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_welford_timing_stats(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        for _ in range(5):
            engine._perform_click(1, 1, "left", "single")
        metrics = engine.get_performance_metrics()
        self.assertEqual(metrics["_timing_count"], 5)
        self.assertGreater(metrics["average_click_time"], 0)
        self.assertIn("click_time_std_dev", metrics)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_status_includes_performance_when_enabled(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=True)
        engine.start_time = time.time()
        engine._perform_click(1, 1, "left", "single")
        status = engine.get_status()
        self.assertIn("performance", status)


class TestClickEngineQueuing(unittest.TestCase):
    """Queue processor and enable_click_queuing."""

    @patch("autoclicker.core.click_engine.time.sleep")
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_enable_click_queuing_starts_processor(self, mock_pyautogui, mock_sleep):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.enable_click_queuing(True, max_queue_size=10)
        self.assertTrue(engine.enable_queuing)
        engine.click_queue.append((1, 1, "left", "single"))
        time.sleep(0.05)
        engine.enable_click_queuing(False)
        self.assertGreaterEqual(engine.click_count, 1)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_queue_full_counts_as_dropped(self, mock_pyautogui):
        """Queue saturation must be observable, not silently bypassed.

        Old behavior fell through and clicked directly on overflow, which
        doubled the effective rate exactly when the user was already over
        capacity. New contract: drop the click and increment the counter.
        """
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.enable_queuing = True
        engine.max_queue_size = 1
        engine.click_queue.append((1, 1, "left", "single"))
        engine._perform_click(2, 2, "left", "single")
        mock_pyautogui.click.assert_not_called()
        self.assertEqual(engine.dropped_click_count, 1)


class TestMainImport(unittest.TestCase):
    """Smoke import for modular entry point."""

    @patch("autoclicker.main.AutoclickerApp")
    def test_main_starts_app(self, mock_app_cls):
        from autoclicker.main import main

        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        main()
        mock_app.run.assert_called_once()
