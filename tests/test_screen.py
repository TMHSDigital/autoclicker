"""Desktop bounds across monitors (#40)."""

import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import ClickEngine
from autoclicker.core.exceptions import CoordinateError
from autoclicker.core.screen import ScreenBounds, _query_virtual_screen, virtual_screen_bounds
from autoclicker.core.settings_manager import SettingsManager

# Secondary 1920x1080 monitor to the left of a 2560x1440 primary.
LEFT_SECONDARY = ScreenBounds(-1920, 0, 1920 + 2560, 1440)


class TestScreenBounds(unittest.TestCase):
    def test_half_open(self):
        bounds = ScreenBounds(0, 0, 1920, 1080)
        self.assertTrue(bounds.contains(0, 0))
        self.assertTrue(bounds.contains(1919, 1079))
        self.assertFalse(bounds.contains(1920, 500))
        self.assertFalse(bounds.contains(500, 1080))
        self.assertFalse(bounds.contains(-1, 0))

    def test_negative_origin(self):
        self.assertTrue(LEFT_SECONDARY.contains(-1200, 300))
        self.assertTrue(LEFT_SECONDARY.contains(2559, 1439))
        self.assertFalse(LEFT_SECONDARY.contains(-1921, 300))
        self.assertEqual(LEFT_SECONDARY.describe(), "X -1920 to 2559, Y 0 to 1439")

    def test_falls_back_to_primary_size(self):
        bounds = virtual_screen_bounds(lambda: (1920, 1080))
        self.assertEqual(bounds, ScreenBounds(0, 0, 1920, 1080))

    def test_uses_virtual_screen_when_available(self):
        with patch("autoclicker.core.screen._query_virtual_screen", return_value=LEFT_SECONDARY):
            self.assertEqual(virtual_screen_bounds(lambda: (1, 1)), LEFT_SECONDARY)

    def test_query_reads_system_metrics(self):
        windll = MagicMock()
        windll.user32.GetSystemMetrics.side_effect = {76: -1920, 77: 0, 78: 4480, 79: 1440}.get
        with patch("autoclicker.core.screen.ctypes") as ctypes_mock:
            ctypes_mock.windll = windll
            self.assertEqual(_query_virtual_screen(), LEFT_SECONDARY)

    def test_query_rejects_empty_metrics(self):
        windll = MagicMock()
        windll.user32.GetSystemMetrics.return_value = 0
        with patch("autoclicker.core.screen.ctypes") as ctypes_mock:
            ctypes_mock.windll = windll
            self.assertIsNone(_query_virtual_screen())


class TestMultiMonitorValidation(unittest.TestCase):
    def setUp(self):
        self.manager = SettingsManager.__new__(SettingsManager)

    def _validate(self, x, y, bounds=LEFT_SECONDARY):
        return self.manager.validate_all_settings(
            {"x_coord": x, "y_coord": y}, bounds.width, bounds.height, bounds.left, bounds.top
        )

    def test_left_monitor_coordinates_kept_and_valid(self):
        result = self._validate("-1200", "300")
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["sanitized_settings"]["x_coord"], -1200)

    def test_right_of_primary_valid(self):
        right = ScreenBounds(0, 0, 1920 + 1920, 1080)
        self.assertTrue(self._validate("2500", "500", right)["valid"])

    def test_off_desktop_rejected(self):
        result = self._validate("-2000", "300")
        self.assertFalse(result["valid"])
        self.assertIn("coordinates", result["errors"])


class TestEngineMultiMonitor(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_clicks_on_left_monitor(self, mock_pyautogui):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine._screen_bounds = LEFT_SECONDARY
        engine._perform_click(-1200, 300, "left", "single")
        mock_pyautogui.click.assert_called_once_with(x=-1200, y=300, button="left", clicks=1)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_edge_pixel_is_off_screen(self, mock_pyautogui):
        mock_pyautogui.size.return_value = (1920, 1080)
        engine = ClickEngine(enable_performance_monitoring=False)
        with self.assertRaises(CoordinateError):
            engine._perform_click(1920, 10, "left", "single")


if __name__ == "__main__":
    unittest.main()
