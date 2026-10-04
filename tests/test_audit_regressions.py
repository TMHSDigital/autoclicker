"""
Regression tests for audit findings (phase 1).
Verify fixes from phase 2 correctness pass.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import ClickEngine
from autoclicker.core.exceptions import CoordinateError, create_user_friendly_error
from autoclicker.core.settings_manager import SettingsManager


class TestStopHaltsClicking(unittest.TestCase):
    """#38: no click may be emitted after a stop call returns."""

    def _run_and_stop(self, stop_name: str) -> int:
        clicks: list[int] = []
        with patch("autoclicker.core.click_engine.pyautogui") as mock_pyautogui:
            mock_pyautogui.size.return_value = (1920, 1080)
            mock_pyautogui.click.side_effect = lambda *a, **k: clicks.append(1)
            engine = ClickEngine(enable_performance_monitoring=False)
            engine.configure_safety(max_cps=0)
            self.assertTrue(engine.start_clicking(10, 10, 0, 0, 1, 0, 0, 0, "left", "single"))
            deadline = time.monotonic() + 2.0
            while not clicks and time.monotonic() < deadline:
                time.sleep(0.005)
            getattr(engine, stop_name)()
            thread = engine.click_thread
            if thread is not None:
                thread.join(timeout=2.0)
            at_stop = len(clicks)
            time.sleep(0.2)
            return len(clicks) - at_stop

    def test_no_clicks_after_stop_clicking(self):
        self.assertEqual(self._run_and_stop("stop_clicking"), 0)

    def test_no_clicks_after_emergency_stop_thread_exits(self):
        self.assertEqual(self._run_and_stop("emergency_stop"), 0)

    def test_queue_api_removed(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        self.assertFalse(hasattr(engine, "enable_click_queuing"))
        self.assertNotIn("queue_size", engine.get_status())


class TestQuitPersistence(unittest.TestCase):
    """C9: quit must persist UI field values via the controller."""

    def test_quit_application_persists_via_controller(self):
        from autoclicker.gui.main_window import AutoclickerApp

        app = AutoclickerApp.__new__(AutoclickerApp)
        app.controller = MagicMock()
        app.settings = MagicMock()
        app.click_engine = MagicMock()
        app.click_engine.is_running = False
        app.stop_clicking = MagicMock()
        app.coordinate_picker = MagicMock()
        app._hotkeys = MagicMock()
        app.root = MagicMock()
        app.tray_icon = None
        app._collect_ui_settings = MagicMock(return_value={"x_coord": 321, "y_coord": 654})

        app.quit_application()

        app.controller.persist_settings_on_quit.assert_called_once()
        kwargs = app.controller.persist_settings_on_quit.call_args
        self.assertEqual(kwargs.kwargs["settings_manager"], app.settings)
        self.assertEqual(kwargs.args[0]["x_coord"], 321)
        app._hotkeys.unregister.assert_called_once()
        app.coordinate_picker.stop_picking.assert_called_once_with(cancelled=False)


class TestSettingsValidationGaps(unittest.TestCase):
    """C11: invalid interval_unit must be reported, not silently defaulted."""

    def test_invalid_interval_unit_reported_in_validate_all(self):
        manager = SettingsManager()
        result = manager.validate_all_settings(
            {"interval": 500, "interval_unit": "invalid"},
            screen_width=1920,
            screen_height=1080,
        )
        self.assertFalse(result["valid"])
        self.assertIn("interval_unit", result["errors"])


class TestUserFriendlyErrors(unittest.TestCase):
    """C10: CoordinateError must work with create_user_friendly_error."""

    def test_coordinate_error_user_message(self):
        error = CoordinateError(10, 20, "Out of bounds")
        message = create_user_friendly_error(error)
        self.assertIn("Out of bounds", message)
