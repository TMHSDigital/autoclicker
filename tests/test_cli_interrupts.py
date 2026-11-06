"""Ctrl+C and late validation paths of headless runs (#166)."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pyautogui

from autoclicker import cli
from autoclicker.app.controller import AutoclickerController, StartClickResult
from autoclicker.cli import EXIT_OK, EXIT_USAGE, parse_args


class HeadlessCase(unittest.TestCase):
    """Same setup as ``HeadlessCase`` in tests/test_cli.py: temp APPDATA, no real input."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        env = patch.dict(os.environ, {"APPDATA": self._dir.name})
        env.start()
        self.addCleanup(env.stop)
        cwd = os.getcwd()
        os.chdir(self._dir.name)
        self.addCleanup(os.chdir, cwd)

        p = patch("autoclicker.core.single_instance.SingleInstance.acquire", return_value=True)
        p.start()
        self.addCleanup(p.stop)
        p = patch("autoclicker.app.hotkeys.HotkeyManager")
        self.HotkeyManager = p.start()
        self.addCleanup(p.stop)
        p = patch("autoclicker.core.click_engine.pyautogui")
        self.pyautogui = p.start()
        self.addCleanup(p.stop)
        self.pyautogui.size.return_value = (1920, 1080)
        self.pyautogui.FailSafeException = pyautogui.FailSafeException
        self.pyautogui.PyAutoGUIException = pyautogui.PyAutoGUIException
        p = patch("autoclicker.core.click_engine.monitor_rects", return_value=[])
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(cli, "_launcher_window", return_value=None)
        p.start()
        self.addCleanup(p.stop)
        # The engine must never start in these tests unless one says otherwise.
        p = patch.object(AutoclickerController, "validate_and_start_clicking")
        self.start = p.start()
        self.addCleanup(p.stop)

    def run_cli(self, *argv):
        return cli.run_headless(parse_args(["--headless", *argv]))


class TestCtrlCBeforeStart(HeadlessCase):
    def test_ctrl_c_during_countdown_exits_ok_without_starting(self):
        fake_time = MagicMock()
        fake_time.sleep.side_effect = KeyboardInterrupt
        out = io.StringIO()
        with patch.object(cli, "time", fake_time), contextlib.redirect_stdout(out):
            code = self.run_cli("--at", "10,10", "--delay", "3")
        self.assertEqual(code, EXIT_OK)
        fake_time.sleep.assert_called_once_with(1)
        self.assertIn("Cancelled.", out.getvalue())
        self.start.assert_not_called()
        self.HotkeyManager.assert_not_called()
        self.pyautogui.click.assert_not_called()

    def test_ctrl_c_during_start_at_wait_exits_ok_without_starting(self):
        fake_time = MagicMock()
        fake_time.sleep.side_effect = KeyboardInterrupt
        out = io.StringIO()
        with patch.object(cli, "time", fake_time), contextlib.redirect_stdout(out):
            code = self.run_cli("--at", "10,10", "--start-at", "23:59", "--delay", "0")
        self.assertEqual(code, EXIT_OK)
        fake_time.sleep.assert_called_once()
        self.assertIn("Starting at", out.getvalue())
        self.assertIn("Cancelled.", out.getvalue())
        self.start.assert_not_called()
        self.HotkeyManager.assert_not_called()


class TestStartDelayParsing(HeadlessCase):
    def test_non_numeric_start_delay_is_treated_as_zero(self):
        self.start.return_value = StartClickResult(success=False, validation_errors={})
        validated = {
            "valid": True,
            "errors": {},
            "sanitized_settings": {"start_delay_seconds": "abc"},
        }
        fake_time = MagicMock()
        with (
            patch.object(AutoclickerController, "validate", return_value=validated),
            patch.object(cli, "time", fake_time),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = self.run_cli("--at", "10,10")
        self.assertEqual(code, EXIT_USAGE)
        fake_time.sleep.assert_not_called()  # no countdown at all
        self.start.assert_called_once()  # went straight to start


class TestLateValidationErrors(HeadlessCase):
    def test_errors_after_start_print_to_stderr_and_exit_usage(self):
        self.start.return_value = StartClickResult(
            success=False, validation_errors={"x_coord": "off screen"}
        )
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.run_cli("--at", "10,10", "--delay", "0")
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("off screen", err.getvalue())
        self.assertTrue(err.getvalue().startswith("autoclicker: "))
        self.HotkeyManager.return_value.unregister.assert_called_once()


class TestCtrlCDuringRun(HeadlessCase):
    def test_ctrl_c_emergency_stops_then_releases_hotkeys_and_finishes(self):
        self.start.return_value = StartClickResult(success=True)
        hotkeys = self.HotkeyManager.return_value
        order = MagicMock()
        fake_threading = MagicMock()
        done = fake_threading.Event.return_value
        # First poll is interrupted; the post-emergency wait then returns.
        done.wait.side_effect = [KeyboardInterrupt, True]
        with (
            patch.object(AutoclickerController, "emergency_stop") as emergency,
            patch.object(AutoclickerController, "finish_run") as finish,
            patch.object(cli, "threading", fake_threading),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            order.attach_mock(emergency, "emergency_stop")
            order.attach_mock(hotkeys.unregister, "unregister")
            order.attach_mock(finish, "finish_run")
            self.run_cli("--at", "10,10", "--delay", "0")
        self.assertEqual(
            [c[0] for c in order.mock_calls], ["emergency_stop", "unregister", "finish_run"]
        )
        self.assertEqual(done.wait.call_count, 2)
        self.assertEqual(done.wait.call_args.args, (2,))


if __name__ == "__main__":
    unittest.main()
