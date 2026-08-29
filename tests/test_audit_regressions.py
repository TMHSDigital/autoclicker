"""
Regression tests for audit findings (phase 1).
Verify fixes from phase 2 correctness pass.
"""

import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import ClickEngine
from autoclicker.core.exceptions import CoordinateError, create_user_friendly_error
from autoclicker.core.settings_manager import SettingsManager
from autoclicker.utils.coordinate_picker import CoordinatePicker


class TestClickEngineQueueBugs(unittest.TestCase):
    """C1, C2: queue mode counter and processor behavior."""

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_queue_mode_does_not_increment_count_without_executing(self, mock_pyautogui):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.enable_queuing = True
        engine.is_running = True

        engine._perform_burst(100, 100, 3, 0.01, "left", "single")

        self.assertEqual(engine.click_count, 0)
        mock_pyautogui.click.assert_not_called()
        self.assertEqual(len(engine.click_queue), 3)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_queue_processor_executes_clicks(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.enable_queuing = True

        engine._perform_click(50, 50, "left", "single", from_queue=True)

        mock_pyautogui.click.assert_called_once()
        self.assertEqual(engine.click_count, 1)


class TestCoordinatePickerHooks(unittest.TestCase):
    """C7, C8: hook API and cancel paths."""

    def test_stop_picking_unhooks_by_handle_not_callback(self):
        mock_hook = MagicMock()
        picker = CoordinatePicker()

        with (
            patch("mouse.on_button", return_value=mock_hook) as mock_on_button,
            patch("mouse.unhook") as mock_unhook,
            patch("keyboard.add_hotkey", return_value=MagicMock()),
        ):
            picker.start_picking(lambda x, y: None)
            mock_on_button.assert_called_once()
            picker.stop_picking(cancelled=True)
            mock_unhook.assert_called_once_with(mock_hook)

    def test_keyboard_cancel_handler_registered_on_start(self):
        picker = CoordinatePicker()
        with (
            patch("mouse.on_button", return_value=MagicMock()),
            patch("keyboard.add_hotkey", return_value=MagicMock()) as mock_hotkey,
        ):
            picker.start_picking(lambda x, y: None, on_cancelled=lambda: None)
        mock_hotkey.assert_called_once_with("esc", picker._on_cancel_hotkey)


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

        with patch("autoclicker.gui.main_window.pyautogui.size", return_value=(1920, 1080)):
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
        self.assertIn("interval", result["errors"])


class TestUserFriendlyErrors(unittest.TestCase):
    """C10: CoordinateError must work with create_user_friendly_error."""

    def test_coordinate_error_user_message(self):
        error = CoordinateError(10, 20, "Out of bounds")
        message = create_user_friendly_error(error)
        self.assertIn("Out of bounds", message)
