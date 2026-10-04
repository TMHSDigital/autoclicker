"""Tests for AutoclickerController persist and start-gate behavior."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.app.controller import AutoclickerController
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
                on_safety_stop=MagicMock(),
                on_click_complete=MagicMock(),
                screen_bounds=ScreenBounds(0, 0, 1920, 1080),
            )
        self.assertFalse(result.success)
        self.assertIn("pause_when_unfocused", result.validation_errors)
        controller.click_engine.start_clicking.assert_not_called()


class TestNotifyClickComplete(unittest.TestCase):
    def test_notify_halts_engine_and_logs(self):
        controller = AutoclickerController.__new__(AutoclickerController)
        controller.click_engine = MagicMock()
        controller.click_engine.click_count = 7
        with patch("autoclicker.app.controller.append_session_event") as log:
            controller.notify_click_complete()
        controller.click_engine.stop_clicking.assert_called_once()
        log.assert_called_once()
        self.assertEqual(log.call_args.args[0], "stop")
        self.assertEqual(log.call_args.kwargs["reason"], "completed")
        self.assertEqual(log.call_args.kwargs["clicks"], 7)
