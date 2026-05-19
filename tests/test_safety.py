"""Tests for safety controls and session logging."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    def test_runaway_triggers_when_cps_exceeds_ceiling(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.max_cps_ceiling = 10
        engine.start_time = 1.0
        engine.click_count = 100
        with patch("autoclicker.core.click_engine.time.time", return_value=2.0):
            self.assertTrue(engine._check_runaway_cps())

    def test_runaway_not_triggered_when_below_ceiling(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.max_cps_ceiling = 50
        engine.start_time = 1.0
        engine.click_count = 10
        with patch("autoclicker.core.click_engine.time.time", return_value=2.0):
            self.assertFalse(engine._check_runaway_cps())


class TestForegroundPause(unittest.TestCase):
    @patch("autoclicker.core.click_engine.is_foreground_window", return_value=False)
    def test_pause_when_unfocused(self, _mock_is_fg):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.pause_when_unfocused = True
        engine._foreground_hwnd = 100
        self.assertTrue(engine._should_pause_for_foreground())


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


class TestSafetyStopCallback(unittest.TestCase):
    def test_trigger_safety_stop_invokes_callback(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        cb = MagicMock()
        engine.on_safety_stop = cb
        engine._trigger_safety_stop("test reason")
        cb.assert_called_once_with("test reason")
        self.assertFalse(engine.is_running)
