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


class TestFocusWindowSelection(unittest.TestCase):
    """#63: a Start-button run must not remember the autoclicker as the target window."""

    OWN = 1
    TARGET = 200
    OTHER = 300

    def _own(self, hwnd):
        return hwnd == self.OWN

    def _engine(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.pause_when_unfocused = True
        return engine

    def test_hotkey_start_keeps_the_window_in_front(self):
        with patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own):
            self.assertEqual(self._engine()._pick_focus_window(self.TARGET, 10, 10), self.TARGET)

    def test_button_start_uses_the_window_under_the_target(self):
        with (
            patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own),
            patch("autoclicker.core.click_engine.root_window_at", return_value=self.TARGET),
        ):
            self.assertEqual(self._engine()._pick_focus_window(self.OWN, 10, 10), self.TARGET)

    def test_button_start_adopts_when_our_window_covers_the_target(self):
        with (
            patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own),
            patch("autoclicker.core.click_engine.root_window_at", return_value=self.OWN),
        ):
            self.assertIsNone(self._engine()._pick_focus_window(self.OWN, 10, 10))

    def test_cursor_mode_button_start_adopts_next_window(self):
        with patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own):
            self.assertIsNone(self._engine()._pick_focus_window(self.OWN, None, None))

    def test_launcher_window_counts_as_ours(self):
        """#94: a headless run uses the window under the target, not its terminal."""
        engine = self._engine()
        engine.launcher_windows = frozenset({self.OTHER})
        with (
            patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own),
            patch("autoclicker.core.click_engine.root_window_at", return_value=self.TARGET),
        ):
            self.assertEqual(engine._pick_focus_window(self.OTHER, 10, 10), self.TARGET)
            self.assertIsNone(engine._pick_focus_window(self.OTHER, None, None))

    def test_launcher_window_is_never_adopted(self):
        engine = self._engine()
        engine.launcher_windows = frozenset({self.OTHER})
        engine._foreground_hwnd = None
        foreground = [self.OTHER]
        with (
            patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own),
            patch(
                "autoclicker.core.click_engine.get_foreground_window_handle",
                side_effect=lambda: foreground[0],
            ),
            patch(
                "autoclicker.core.click_engine.is_foreground_window",
                side_effect=lambda hwnd: hwnd == foreground[0],
            ),
        ):
            self.assertTrue(engine._should_pause_for_foreground())
            self.assertIsNone(engine._foreground_hwnd)
            foreground[0] = self.TARGET
            self.assertFalse(engine._should_pause_for_foreground())
            self.assertEqual(engine._foreground_hwnd, self.TARGET)

    def test_adopt_waits_while_our_window_is_in_front_then_follows_the_next(self):
        engine = self._engine()
        engine._foreground_hwnd = None
        foreground = [self.OWN]
        with (
            patch("autoclicker.core.click_engine.is_own_window", side_effect=self._own),
            patch(
                "autoclicker.core.click_engine.get_foreground_window_handle",
                side_effect=lambda: foreground[0],
            ),
            patch(
                "autoclicker.core.click_engine.is_foreground_window",
                side_effect=lambda hwnd: hwnd == foreground[0],
            ),
        ):
            self.assertTrue(engine._should_pause_for_foreground())
            self.assertTrue(engine.is_paused)
            foreground[0] = self.TARGET
            self.assertFalse(engine._should_pause_for_foreground())
            self.assertFalse(engine.is_paused)
            self.assertEqual(engine._foreground_hwnd, self.TARGET)
            foreground[0] = self.OTHER  # user switched away: pause, don't re-adopt
            self.assertTrue(engine._should_pause_for_foreground())
            self.assertEqual(engine._foreground_hwnd, self.TARGET)

    def test_unreadable_foreground_while_adopting_pauses(self):
        engine = self._engine()
        with patch("autoclicker.core.click_engine.get_foreground_window_handle", return_value=None):
            self.assertTrue(engine._should_pause_for_foreground())

    def test_status_reports_paused(self):
        engine = self._engine()
        engine.is_paused = True
        self.assertTrue(engine.get_status()["is_paused"])


class TestForegroundFailsClosed(unittest.TestCase):
    """#111: every way the foreground lookup can fail means "not in front"."""

    def test_without_win32gui(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32gui", None):
            self.assertIsNone(safety.get_foreground_window_handle())
            self.assertFalse(safety.is_foreground_window(5))
            self.assertIsNone(safety.root_window_at(1, 1))

    def test_lookup_error(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32gui") as gui:
            gui.GetForegroundWindow.side_effect = OSError("access denied")
            self.assertIsNone(safety.get_foreground_window_handle())
            self.assertFalse(safety.is_foreground_window(5))

    def test_no_handle_and_another_window(self):
        from autoclicker.core import safety

        self.assertFalse(safety.is_foreground_window(None))
        with patch.object(safety, "win32gui") as gui:
            gui.GetForegroundWindow.return_value = 7
            self.assertFalse(safety.is_foreground_window(5))
            self.assertTrue(safety.is_foreground_window(7))

    def test_own_window_without_win32process_counts_as_ours(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32process", None):
            self.assertTrue(safety.is_own_window(5))

    def test_root_window_at_nothing(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32gui") as gui:
            gui.WindowFromPoint.return_value = 0
            self.assertIsNone(safety.root_window_at(1, 2))


class TestWindowHelpers(unittest.TestCase):
    def test_own_window_lookup_failure_counts_as_ours(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32process") as proc:
            proc.GetWindowThreadProcessId.side_effect = OSError("gone")
            self.assertTrue(safety.is_own_window(5))

    def test_own_window_compares_pid(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32process") as proc:
            proc.GetWindowThreadProcessId.return_value = (1, os.getpid())
            self.assertTrue(safety.is_own_window(5))
            proc.GetWindowThreadProcessId.return_value = (1, os.getpid() + 1)
            self.assertFalse(safety.is_own_window(5))

    def test_root_window_at(self):
        from autoclicker.core import safety

        with patch.object(safety, "win32gui") as gui:
            gui.WindowFromPoint.return_value = 11
            gui.GetAncestor.return_value = 22
            self.assertEqual(safety.root_window_at(1, 2), 22)
            gui.GetAncestor.assert_called_once_with(11, safety.GA_ROOT)
            gui.WindowFromPoint.side_effect = OSError("nope")
            self.assertIsNone(safety.root_window_at(1, 2))


class TestRunawayGuardCounting(unittest.TestCase):
    """#64: the guard counts button presses and works at any accepted ceiling."""

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_double_click_counts_two_presses(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._perform_click(10, 10, "left", "double")
        self.assertEqual(engine.click_count, 1)  # limits still count one click
        self.assertEqual(len(engine._recent_click_ts), 2)

    def test_highest_ceiling_can_trip(self):
        from autoclicker.core.settings_manager import MAX_CPS_CEILING

        engine = ClickEngine(enable_performance_monitoring=False)
        engine.max_cps_ceiling = MAX_CPS_CEILING
        engine.start_time = 1.0
        with patch("autoclicker.core.click_engine.time.monotonic", return_value=2.0):
            for _ in range(MAX_CPS_CEILING + 1):
                engine._recent_click_ts.append(1.5)
            self.assertTrue(engine._check_runaway_cps())


class TestOwnWindowAtStart(unittest.TestCase):
    """#81: started from our own button, the first click may bring the target forward."""

    OWN, TARGET = 1, 200

    def _engine(self, point_target=True):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.pause_when_unfocused = True
        engine._foreground_hwnd = self.TARGET
        engine._point_target = point_target
        return engine

    def _check(self, engine, current):
        with (
            patch(
                "autoclicker.core.click_engine.get_foreground_window_handle", return_value=current
            ),
            patch(
                "autoclicker.core.click_engine.is_own_window", side_effect=lambda h: h == self.OWN
            ),
            patch(
                "autoclicker.core.click_engine.is_foreground_window",
                side_effect=lambda h: h == current,
            ),
        ):
            return engine._should_pause_for_foreground()

    def test_own_window_allowed_until_target_seen(self):
        engine = self._engine()
        self.assertFalse(self._check(engine, self.OWN))  # first click activates the target
        self.assertFalse(self._check(engine, self.TARGET))
        self.assertTrue(self._check(engine, self.OWN))  # user switched back to us: pause

    def test_cursor_mode_never_allows_own_window(self):
        engine = self._engine(point_target=False)
        self.assertTrue(self._check(engine, self.OWN))
