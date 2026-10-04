"""Desktop bounds across monitors (#40)."""

import threading
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.click_engine import STOP_SAFETY, ClickEngine
from autoclicker.core.exceptions import CoordinateError, SafetyError
from autoclicker.core.screen import (
    ScreenBounds,
    _query_virtual_screen,
    failsafe_corners,
    virtual_screen_bounds,
)
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


class TestFailsafeCorners(unittest.TestCase):
    """#66: corner failsafe on every monitor, but not where screens meet."""

    def test_side_by_side_monitors_only_outer_corners(self):
        left = ScreenBounds(-1920, 0, 1920, 1080)
        primary = ScreenBounds(0, 0, 1920, 1080)
        self.assertEqual(
            failsafe_corners([left, primary]),
            {(-1920, 0), (-1920, 1079), (1919, 0), (1919, 1079)},
        )

    def test_offset_monitor_exposes_its_own_corners(self):
        primary = ScreenBounds(0, 0, 1920, 1080)
        lower_right = ScreenBounds(1920, 300, 1280, 1024)  # top edge starts lower
        corners = failsafe_corners([primary, lower_right])
        self.assertIn((3199, 300), corners)
        self.assertIn((3199, 1323), corners)
        self.assertIn((1919, 0), corners)  # nothing above or right of it
        self.assertNotIn((1920, 300), corners)  # slides back onto the primary

    def test_no_monitors_no_corners(self):
        self.assertEqual(failsafe_corners([]), frozenset())


class TestEngineCornerFailsafe(unittest.TestCase):
    def _engine(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.failsafe_enabled = True
        engine._failsafe_corners = failsafe_corners(
            [ScreenBounds(-1920, 0, 1920, 1080), ScreenBounds(0, 0, 1920, 1080)]
        )
        engine._screen_bounds = ScreenBounds(-1920, 0, 3840, 1080)
        return engine

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_corner_of_secondary_monitor_stops(self, mock_pyautogui):
        engine = self._engine()
        with (
            patch("autoclicker.core.click_engine.cursor_position", return_value=(-1919, 1)),
            self.assertRaises(SafetyError),
        ):
            engine._perform_click(100, 100, "left", "single")
        mock_pyautogui.click.assert_not_called()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_where_screens_meet_does_not_stop(self, mock_pyautogui):
        engine = self._engine()
        with patch("autoclicker.core.click_engine.cursor_position", return_value=(-1, 0)):
            engine._perform_click(100, 100, "left", "single")
        mock_pyautogui.click.assert_called_once()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_failsafe_off_ignores_corners(self, mock_pyautogui):
        engine = self._engine()
        engine.failsafe_enabled = False
        with patch("autoclicker.core.click_engine.cursor_position", return_value=(-1920, 0)):
            engine._perform_click(100, 100, "left", "single")
        mock_pyautogui.click.assert_called_once()

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_resting_on_a_corner_target_is_not_a_stop(self, mock_pyautogui):
        engine = self._engine()
        with patch("autoclicker.core.click_engine.cursor_position", return_value=(1919, 0)):
            engine._perform_click(1919, 0, "left", "single")
        mock_pyautogui.click.assert_called_once()

    def test_configure_safety_refreshes_corners(self):
        engine = ClickEngine(enable_performance_monitoring=False)
        with patch(
            "autoclicker.core.click_engine.monitor_rects",
            return_value=[ScreenBounds(0, 0, 800, 600)],
        ):
            engine.configure_safety(failsafe=True)
            self.assertEqual(len(engine._failsafe_corners), 4)
            engine.configure_safety(failsafe=False)
            self.assertEqual(engine._failsafe_corners, frozenset())

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_corner_ends_the_run_as_a_failsafe_stop(self, mock_pyautogui):
        import pyautogui

        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.FailSafeException = pyautogui.FailSafeException
        mock_pyautogui.PyAutoGUIException = pyautogui.PyAutoGUIException
        engine = ClickEngine(enable_performance_monitoring=False)
        done = threading.Event()
        outcomes = []

        def finished(outcome):
            outcomes.append(outcome)
            done.set()

        monitors = [ScreenBounds(-1920, 0, 1920, 1080), ScreenBounds(0, 0, 1920, 1080)]
        with (
            patch("autoclicker.core.click_engine.monitor_rects", return_value=monitors),
            patch("autoclicker.core.click_engine.cursor_position", return_value=(-1920, 1079)),
        ):
            engine.configure_safety(failsafe=True)
            engine.start_clicking(None, None, 10, 0, 1, 0, 0, 0, "left", "single", finished)
            self.assertTrue(done.wait(2))
        self.assertEqual(outcomes[0].reason, STOP_SAFETY)
        self.assertIn("corner", outcomes[0].message)
