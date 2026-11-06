"""Win32 failure paths of the screen helpers (#166).

``tests/conftest.py`` stubs ``click_engine.cursor_position`` and
``screen._query_virtual_screen`` for every test. The real functions are
captured here at import time (collection runs before any fixture), and the
Win32 layer is faked by swapping the ``ctypes`` the screen module sees, so
the process-wide ``ctypes`` is never touched.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from autoclicker.core import screen
from autoclicker.core.click_engine import ClickEngine
from autoclicker.core.screen import (
    SM_CXVIRTUALSCREEN,
    SM_CYVIRTUALSCREEN,
    SM_XVIRTUALSCREEN,
    SM_YVIRTUALSCREEN,
    ScreenBounds,
    _query_virtual_screen,
    cursor_position,
    failsafe_corners,
    monitor_rects,
)


def _fake_ctypes(windll=None, *, with_windll: bool = True) -> SimpleNamespace:
    fake = SimpleNamespace(wintypes=ctypes.wintypes, byref=lambda obj: obj)
    if with_windll:
        fake.windll = windll
    return fake


class TestCursorPosition(unittest.TestCase):
    def _call(self, fake) -> tuple[int, int] | None:
        with patch.object(screen, "ctypes", fake):
            return cursor_position()

    def test_no_windll_returns_none(self):
        self.assertIsNone(self._call(_fake_ctypes(with_windll=False)))

    def test_get_cursor_pos_failure_returns_none(self):
        windll = MagicMock()
        windll.user32.GetCursorPos.return_value = 0
        self.assertIsNone(self._call(_fake_ctypes(windll)))

    def test_get_cursor_pos_raising_returns_none(self):
        windll = MagicMock()
        windll.user32.GetCursorPos.side_effect = OSError("access denied")
        self.assertIsNone(self._call(_fake_ctypes(windll)))

    def test_success_returns_ints(self):
        def fill(point):
            point.x, point.y = -1920, 1079
            return 1

        windll = MagicMock()
        windll.user32.GetCursorPos.side_effect = fill
        position = self._call(_fake_ctypes(windll))
        self.assertEqual(position, (-1920, 1079))
        assert position is not None
        self.assertTrue(all(type(v) is int for v in position))


class TestMonitorRects(unittest.TestCase):
    def test_enum_display_monitors_raising_returns_empty(self):
        fake = SimpleNamespace(EnumDisplayMonitors=MagicMock(side_effect=OSError("no desktop")))
        with patch.dict(sys.modules, {"win32api": fake}):
            self.assertEqual(monitor_rects(), [])

    def test_missing_win32api_returns_empty(self):
        with patch.dict(sys.modules, {"win32api": None}):  # import raises ImportError
            self.assertEqual(monitor_rects(), [])

    def test_rects_from_enum_display_monitors(self):
        fake = SimpleNamespace(
            EnumDisplayMonitors=lambda: [(1, 2, (-1920, 0, 0, 1080)), (3, 4, (0, 0, 2560, 1440))]
        )
        with patch.dict(sys.modules, {"win32api": fake}):
            self.assertEqual(
                monitor_rects(),
                [ScreenBounds(-1920, 0, 1920, 1080), ScreenBounds(0, 0, 2560, 1440)],
            )


class TestQueryVirtualScreen(unittest.TestCase):
    def _metrics(self, values: dict[int, int]) -> MagicMock:
        windll = MagicMock()
        windll.user32.GetSystemMetrics.side_effect = lambda index: values[index]
        return windll

    def _call(self, fake) -> ScreenBounds | None:
        with patch.object(screen, "ctypes", fake):
            return _query_virtual_screen()

    def test_zero_width_returns_none(self):
        windll = self._metrics(
            {SM_XVIRTUALSCREEN: 0, SM_YVIRTUALSCREEN: 0, SM_CXVIRTUALSCREEN: 0,
             SM_CYVIRTUALSCREEN: 1080}
        )  # fmt: skip
        self.assertIsNone(self._call(_fake_ctypes(windll)))

    def test_no_windll_returns_none(self):
        self.assertIsNone(self._call(_fake_ctypes(with_windll=False)))

    def test_raising_returns_none(self):
        windll = MagicMock()
        windll.user32.GetSystemMetrics.side_effect = OSError("boom")
        self.assertIsNone(self._call(_fake_ctypes(windll)))

    def test_virtual_screen_bounds(self):
        windll = self._metrics(
            {SM_XVIRTUALSCREEN: -1920, SM_YVIRTUALSCREEN: 0, SM_CXVIRTUALSCREEN: 3840,
             SM_CYVIRTUALSCREEN: 1080}
        )  # fmt: skip
        self.assertEqual(self._call(_fake_ctypes(windll)), ScreenBounds(-1920, 0, 3840, 1080))


class TestUnknownCursorNeverTripsFailsafe(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_unreadable_cursor_does_not_stop_clicking(self, mock_pyautogui):
        """A cursor that cannot be read (None) is never treated as a corner."""
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.failsafe_enabled = True
        engine._failsafe_corners = failsafe_corners([ScreenBounds(0, 0, 1920, 1080)])
        engine._screen_bounds = ScreenBounds(0, 0, 1920, 1080)
        with patch("autoclicker.core.click_engine.cursor_position", return_value=None):
            self.assertFalse(engine._cursor_in_failsafe_corner(100, 100))
            engine._perform_click(100, 100, "left", "single")
        mock_pyautogui.click.assert_called_once()


if __name__ == "__main__":
    unittest.main()
