"""System tray icon and menu (#111)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoclicker.app import tray


class TestTrayMenu(unittest.TestCase):
    def _create(self, **kwargs):
        callbacks = {name: MagicMock(name=name) for name in ("show", "start", "stop", "quit")}
        self.on_error = MagicMock()
        with patch.object(tray, "pystray") as pystray:
            pystray.MenuItem.side_effect = lambda text, action, **kw: (text, action, kw)
            pystray.Menu.side_effect = lambda *items: list(items)
            icon = tray.create_tray_icon(
                callbacks["show"],
                callbacks["start"],
                callbacks["stop"],
                callbacks["quit"],
                self.on_error,
                **kwargs,
            )
            menu = pystray.Icon.call_args.kwargs["menu"]
        return icon, menu, callbacks

    def test_menu_items_and_actions(self):
        show_info = MagicMock()
        icon, menu, callbacks = self._create(
            start_label=lambda: "Start (F6)", stop_label=lambda: "Stop (F7)", show_info=show_info
        )
        self.assertIsNotNone(icon)
        show, start, stop, about, exit_item = menu
        self.assertEqual(show[:2], ("Show", callbacks["show"]))
        self.assertTrue(show[2]["default"])  # double-click restores the window
        # Start/Stop labels are callables so they follow hotkey changes.
        self.assertEqual(start[0](None), "Start (F6)")
        self.assertEqual(stop[0](None), "Stop (F7)")
        self.assertIs(start[1], callbacks["start"])
        self.assertIs(stop[1], callbacks["stop"])
        self.assertEqual(about[:2], ("About and diagnostics", show_info))
        self.assertTrue(about[2]["visible"])
        self.assertEqual(exit_item[:2], ("Exit", callbacks["quit"]))
        self.on_error.assert_not_called()

    def test_about_hidden_without_a_handler(self):
        _icon, menu, _callbacks = self._create()
        self.assertFalse(menu[3][2]["visible"])

    def test_failure_is_reported_not_raised(self):
        on_error = MagicMock()
        with patch.object(tray, "pystray") as pystray:
            pystray.Icon.side_effect = OSError("no shell")
            icon = tray.create_tray_icon(
                MagicMock(), MagicMock(), MagicMock(), MagicMock(), on_error
            )
        self.assertIsNone(icon)
        self.assertIn("no shell", on_error.call_args.args[0])


class TestTrayImage(unittest.TestCase):
    def test_uses_the_bundled_icon(self):
        image = tray._load_tray_image()
        self.assertEqual(image.mode, "RGBA")

    def test_falls_back_to_a_square(self):
        with patch.object(tray, "resource_path", return_value=Path("missing.png")):
            image = tray._load_tray_image()
        self.assertEqual(image.size, (64, 64))


if __name__ == "__main__":
    unittest.main()
