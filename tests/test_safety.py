"""Tests for safety controls and session logging."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoclicker.core import session_log
from autoclicker.core.click_engine import ClickEngine
from autoclicker.core.safety import apply_failsafe


class TestFailsafe(unittest.TestCase):
    @patch("autoclicker.core.safety.pyautogui")
    def test_apply_failsafe(self, mock_pyautogui):
        apply_failsafe(True)
        self.assertTrue(mock_pyautogui.FAILSAFE)
        apply_failsafe(False)
        self.assertFalse(mock_pyautogui.FAILSAFE)


class TestRunawayGuard(unittest.TestCase):
    """Sliding-window guard: trips on recent rate, not lifetime average."""

    def test_runaway_triggers_when_cps_exceeds_ceiling(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.max_cps_ceiling = 10
        engine.start_time = 1.0
        # 100 click timestamps within the last 1s
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=2.0):
            for i in range(100):
                engine._recent_click_ts.append(1.0 + i * 0.005)
            self.assertTrue(engine._check_runaway_cps())

    def test_runaway_not_triggered_when_below_ceiling(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.max_cps_ceiling = 50
        engine.start_time = 1.0
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=2.0):
            for i in range(10):
                engine._recent_click_ts.append(1.0 + i * 0.1)
            self.assertFalse(engine._check_runaway_cps())


class TestForegroundPause(unittest.TestCase):
    @patch("autoclicker.core.click_engine.is_foreground_window", return_value=False)
    def test_pause_when_unfocused(self, _mock_is_fg):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.pause_when_unfocused = True
        engine._foreground_hwnd = 100
        self.assertTrue(engine._should_pause_for_foreground())


class TestForegroundFailClosed(unittest.TestCase):
    def test_none_hwnd_is_unfocused(self):
        from autoclicker.core.safety import is_foreground_window

        self.assertFalse(is_foreground_window(None))

    @patch("autoclicker.core.safety.get_foreground_window_handle", return_value=None)
    def test_lookup_failure_is_unfocused(self, _mock_hwnd):
        from autoclicker.core.safety import is_foreground_window

        self.assertFalse(is_foreground_window(123))

    @patch("autoclicker.core.click_engine.get_foreground_window_handle", return_value=None)
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_start_refuses_unfocused_pause_without_hwnd(self, mock_pyautogui, _mock_hwnd):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.pause_when_unfocused = True
        self.assertFalse(engine.start_clicking(1, 1, 100, 0, 1, 0, 0, 0, "left", "single"))
        self.assertFalse(engine.is_running)


class TestSessionLog(unittest.TestCase):
    def test_append_session_event_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "WindowsAutoclicker"
            log_path = log_dir / "sessions.log"
            with (
                patch.dict(os.environ, {"APPDATA": tmp}),
                patch.object(session_log, "session_log_path", return_value=log_path),
            ):
                session_log.append_session_event("start", x=1, y=2)
            self.assertTrue(log_path.exists())
            content = log_path.read_text(encoding="utf-8")
            self.assertIn("event=start", content)
            self.assertIn("x=1", content)

    def test_append_session_event_escapes_tabs_and_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "WindowsAutoclicker"
            log_path = log_dir / "sessions.log"
            with (
                patch.dict(os.environ, {"APPDATA": tmp}),
                patch.object(session_log, "session_log_path", return_value=log_path),
            ):
                session_log.append_session_event("stop", reason="a\tb\nc")
            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertNotIn("\treason=a\t", log_path.read_text(encoding="utf-8"))
            self.assertIn("reason=a b c", lines[0])


class TestSafetyStopReason(unittest.TestCase):
    def test_trigger_safety_stop_records_reason(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._trigger_safety_stop("test reason")
        self.assertEqual(engine._stop_reason, ("safety", "test reason"))
        self.assertFalse(engine.is_running)

    def test_first_stop_reason_wins(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.is_running = True
        engine._trigger_safety_stop("runaway")
        engine.stop_clicking()
        self.assertEqual(engine._stop_reason, ("safety", "runaway"))
