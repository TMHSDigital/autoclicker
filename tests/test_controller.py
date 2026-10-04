"""Tests for AutoclickerController persist and start-gate behavior."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.app.controller import AutoclickerController
from autoclicker.core.click_engine import STOP_EMERGENCY, RunOutcome
from autoclicker.core.screen import ScreenBounds
from autoclicker.core.settings_manager import SettingsManager


class TestPersistSettingsOnQuit(unittest.TestCase):
    def test_invalid_quit_keeps_last_good_file(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            settings = SettingsManager(path)
            settings.set("x_coord", 250)
            controller = AutoclickerController.__new__(AutoclickerController)
            controller.settings = settings
            raw = {
                "x_coord": 100,
                "y_coord": 100,
                "interval": 1000,
                "interval_unit": "ms",
                "variation": 0,
                "mouse_button": "left",
                "click_type": "single",
                "burst_clicks": 1,
                "burst_pause": 1000,
                "max_clicks": 0,
                "auto_stop_minutes": 2000,
            }
            controller.persist_settings_on_quit(
                raw,
                settings_manager=settings,
                screen_bounds=ScreenBounds(0, 0, 1920, 1080),
            )
            reloaded = SettingsManager(path)
            self.assertEqual(reloaded.get("x_coord"), 250)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_valid_quit_persists_sanitized(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            settings = SettingsManager(path)
            controller = AutoclickerController.__new__(AutoclickerController)
            controller.settings = settings
            raw = {
                "x_coord": 321,
                "y_coord": 654,
                "interval": 1000,
                "interval_unit": "ms",
                "variation": 0,
                "mouse_button": "left",
                "click_type": "single",
                "burst_clicks": 1,
                "burst_pause": 1000,
                "max_clicks": 0,
                "auto_stop_minutes": 0,
            }
            controller.persist_settings_on_quit(
                raw,
                settings_manager=settings,
                screen_bounds=ScreenBounds(0, 0, 1920, 1080),
            )
            reloaded = SettingsManager(path)
            self.assertEqual(reloaded.get("x_coord"), 321)
            self.assertEqual(reloaded.get("y_coord"), 654)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestStartClickForegroundGate(unittest.TestCase):
    def test_pause_unfocused_without_hwnd_returns_validation_error(self):
        controller = AutoclickerController.__new__(AutoclickerController)
        controller.settings = MagicMock()
        controller.settings.validate_all_settings.return_value = {
            "valid": True,
            "errors": {},
            "sanitized_settings": {
                "x_coord": 1,
                "y_coord": 1,
                "interval": 1000,
                "interval_unit": "ms",
                "variation": 0,
                "burst_clicks": 1,
                "burst_pause": 1000,
                "max_clicks": 0,
                "auto_stop_minutes": 0,
                "mouse_button": "left",
                "click_type": "single",
            },
        }
        controller.settings.update = MagicMock()
        controller.click_engine = MagicMock()
        controller.click_engine.is_running = False
        controller.apply_safety_from_settings = MagicMock()
        controller.configure_safety_from_ui = MagicMock()

        with patch(
            "autoclicker.app.controller.get_foreground_window_handle",
            return_value=None,
        ):
            result = controller.validate_and_start_clicking(
                {},
                failsafe=True,
                pause_when_unfocused=True,
                on_finished=MagicMock(),
                screen_bounds=ScreenBounds(0, 0, 1920, 1080),
            )
        self.assertFalse(result.success)
        self.assertIn("pause_when_unfocused", result.validation_errors)
        controller.click_engine.start_clicking.assert_not_called()


class TestRunFinishedLogging(unittest.TestCase):
    """#41: exactly one session-log stop event per run, with the real reason."""

    def test_logs_once_then_forwards(self):
        outcome = RunOutcome(STOP_EMERGENCY, "Emergency stop", 7)
        ui = MagicMock()
        with patch("autoclicker.app.controller.append_session_event") as log:
            AutoclickerController._run_finished(outcome, ui)
        log.assert_called_once_with("stop", reason="emergency", clicks=7, detail="Emergency stop")
        ui.assert_called_once_with(outcome)

    def test_stop_clicking_does_not_log(self):
        controller = AutoclickerController.__new__(AutoclickerController)
        controller.click_engine = MagicMock()
        controller.click_engine.is_running = True
        with patch("autoclicker.app.controller.append_session_event") as log:
            self.assertTrue(controller.stop_clicking())
            self.assertTrue(controller.emergency_stop())
        log.assert_not_called()

    def test_start_while_running_is_refused(self):
        controller = AutoclickerController.__new__(AutoclickerController)
        controller.click_engine = MagicMock()
        controller.click_engine.is_running = True
        controller.settings = MagicMock()
        result = controller.validate_and_start_clicking(
            {}, failsafe=True, pause_when_unfocused=False
        )
        self.assertFalse(result.success)
        controller.settings.validate_all_settings.assert_not_called()


class TestCursorModeStart(unittest.TestCase):
    """#48: cursor mode starts the engine without a fixed target."""

    def test_passes_none_target_and_logs_cursor(self):
        controller = AutoclickerController.__new__(AutoclickerController)
        controller.settings = SettingsManager.__new__(SettingsManager)
        controller.settings._settings = {}
        controller.settings._save_settings = MagicMock()
        controller.click_engine = MagicMock()
        controller.click_engine.is_running = False
        controller.click_engine.start_clicking.return_value = True
        raw = {
            "target_mode": "cursor",
            "x_coord": "",
            "y_coord": "",
            "interval": "100",
            "interval_unit": "ms",
            "variation": "0",
            "mouse_button": "left",
            "click_type": "single",
            "burst_clicks": "1",
            "burst_pause": "0",
            "max_clicks": "0",
            "auto_stop_minutes": "0",
            "max_cps_ceiling": 50,
        }
        with patch("autoclicker.app.controller.append_session_event") as log:
            result = controller.validate_and_start_clicking(
                raw,
                failsafe=True,
                pause_when_unfocused=False,
                screen_bounds=ScreenBounds(0, 0, 1920, 1080),
            )
        self.assertTrue(result.success, result.validation_errors)
        kwargs = controller.click_engine.start_clicking.call_args.kwargs
        self.assertIsNone(kwargs["x"])
        self.assertIsNone(kwargs["y"])
        self.assertEqual(log.call_args.kwargs["target"], "cursor")
