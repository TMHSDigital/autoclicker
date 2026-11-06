"""Switch profiles from the tray menu (#178)."""

import unittest
from unittest.mock import MagicMock

from autoclicker.app import tray
from autoclicker.gui.main_window import AutoclickerApp


class TestProfileItems(unittest.TestCase):
    def test_lists_names_sorted_and_loads_on_click(self):
        loaded = []
        items = tray._profile_items(lambda: ["Work", "alpha"], loaded.append, lambda: True)
        self.assertEqual([item.text for item in items], ["alpha", "Work"])
        items[1](MagicMock())  # pystray calls the item with the icon
        self.assertEqual(loaded, ["Work"])
        self.assertTrue(items[0].enabled)

    def test_disabled_while_switching_is_not_allowed(self):
        items = tray._profile_items(lambda: ["Work"], MagicMock(), lambda: False)
        self.assertFalse(items[0].enabled)

    def test_placeholder_when_there_are_none(self):
        items = tray._profile_items(lambda: [], MagicMock(), lambda: True)
        self.assertEqual([item.text for item in items], ["No saved profiles"])
        self.assertFalse(items[0].enabled)


def _app(running=False):
    app = AutoclickerApp.__new__(AutoclickerApp)
    app.click_engine = MagicMock(is_running=running)
    app._countdown_job = None
    app._recorder = None
    app.preset_manager = MagicMock()
    app.preset_var = MagicMock()
    app.load_preset = MagicMock()
    app._set_status_message = MagicMock()
    app.tray_icon = MagicMock()
    return app


class TestLoadFromTray(unittest.TestCase):
    def test_loads_the_profile_into_the_form(self):
        app = _app()
        app._load_profile_from_tray("Work")
        app.preset_var.set.assert_called_once_with("Work")
        app.load_preset.assert_called_once()
        app._set_status_message.assert_called_with("Loaded profile 'Work'")

    def test_refused_while_running_or_counting_down(self):
        for setup in ("running", "countdown", "recording"):
            with self.subTest(setup=setup):
                app = _app(running=setup == "running")
                if setup == "countdown":
                    app._countdown_job = "after#1"
                if setup == "recording":
                    app._recorder = MagicMock()
                self.assertFalse(app._can_switch_profile())
                app._load_profile_from_tray("Work")
                app.load_preset.assert_not_called()

    def test_missing_profile(self):
        app = _app()
        app.preset_manager.load_profile.return_value = None
        app._load_profile_from_tray("Gone")
        app.load_preset.assert_not_called()
        self.assertEqual(app._set_status_message.call_args.args[1], "error")

    def test_menu_refreshes_when_the_run_mode_changes(self):
        app = _app()
        app.run_button = MagicMock()
        app._paint_run_mode("running")
        app._paint_run_mode("running")
        app._paint_run_mode("idle")
        self.assertEqual(app.tray_icon.update_menu.call_count, 2)


if __name__ == "__main__":
    unittest.main()
