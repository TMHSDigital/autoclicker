"""
Regression tests for audit findings (phase 1).
Each test should fail until the corresponding fix lands in phase 2.
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
    def test_queue_mode_increments_count_without_executing_clicks(self, mock_pyautogui):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.enable_queuing(True)
        engine.is_running = True

        engine._perform_burst(100, 100, 3, 0.01, "left", "single")

        self.assertEqual(engine.click_count, 3)
        mock_pyautogui.click.assert_not_called()
        self.assertEqual(len(engine.click_queue), 3)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_queue_processor_does_not_execute_clicks(self, mock_pyautogui):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.enable_queuing(True)
        engine.click_queue.append((50, 50, "left", "single"))

        engine._perform_click(50, 50, "left", "single")

        mock_pyautogui.click.assert_not_called()
        self.assertGreaterEqual(len(engine.click_queue), 1)


class TestCoordinatePickerHooks(unittest.TestCase):
    """C7, C8: hook API and cancel paths."""

    def test_stop_picking_unhooks_by_handle_not_callback(self):
        mock_hook = MagicMock()
        picker = CoordinatePicker()

        with (
            patch("mouse.on_button", return_value=mock_hook) as mock_on_button,
            patch("mouse.unhook") as mock_unhook,
        ):
            picker.start_picking(lambda x, y: None)
            mock_on_button.assert_called_once()
            picker.stop_picking(cancelled=True)
            mock_unhook.assert_called_once_with(mock_hook)

    def test_no_keyboard_cancel_handler_registered(self):
        picker = CoordinatePicker()
        with patch("mouse.on_button", return_value=MagicMock()):
            picker.start_picking(lambda x, y: None, on_cancelled=lambda: None)
        self.assertTrue(hasattr(picker, "_keyboard_hook") and picker._keyboard_hook is not None)


class TestQuitPersistence(unittest.TestCase):
    """C9: quit must persist UI field values."""

    def test_quit_application_persists_ui_values_not_empty_update(self):
        from autoclicker.gui.main_window import AutoclickerApp

        app = AutoclickerApp.__new__(AutoclickerApp)
        app.click_engine = MagicMock()
        app.click_engine.is_running = False
        app.coordinate_picker = MagicMock()
        app.settings = MagicMock()
        app.root = MagicMock()
        app.tray_icon = None

        app.x_entry = MagicMock()
        app.x_entry.get.return_value = "321"
        app.y_entry = MagicMock()
        app.y_entry.get.return_value = "654"

        app.quit_application()

        app.settings.update.assert_called_once()
        saved = app.settings.update.call_args[0][0]
        self.assertEqual(saved.get("x_coord"), 321)
        self.assertEqual(saved.get("y_coord"), 654)


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
