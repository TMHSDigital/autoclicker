"""GUI callback marshaling, picker, emergency, and hotkey tests (no live Tk)."""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.app.hotkeys import setup_hotkeys
from autoclicker.gui.main_window import AutoclickerApp


def _bare_app() -> AutoclickerApp:
    app = AutoclickerApp.__new__(AutoclickerApp)
    app.root = MagicMock()
    app.controller = MagicMock()
    app.click_engine = MagicMock()
    app.click_engine.is_running = False
    app.coordinate_picker = MagicMock()
    app.status_var = MagicMock()
    app.pick_btn = MagicMock()
    app.start_btn = MagicMock()
    app.stop_btn = MagicMock()
    app.preset_var = MagicMock()
    app.preset_manager = MagicMock()
    app.settings = MagicMock()
    app._hotkeys = MagicMock()
    app.tray_icon = None
    return app


class TestUiMarshal(unittest.TestCase):
    def test_ui_schedules_after_zero(self):
        app = _bare_app()
        fn = MagicMock()
        app._ui(fn, 1, 2)
        app.root.after.assert_called_once()
        delay, callback = app.root.after.call_args[0]
        self.assertEqual(delay, 0)
        callback()
        fn.assert_called_once_with(1, 2)


class TestCoordinatePickerUi(unittest.TestCase):
    def test_picker_failure_does_not_withdraw(self):
        app = _bare_app()
        app.coordinate_picker.is_picking.return_value = False
        app.coordinate_picker.start_picking.return_value = False
        app.start_coordinate_picker()
        app.root.withdraw.assert_not_called()
        app.pick_btn.config.assert_any_call(state=tk.NORMAL)
        app.status_var.set.assert_called_with("Could not start coordinate picker")

    def test_picker_success_withdraws(self):
        app = _bare_app()
        app.coordinate_picker.is_picking.return_value = False
        app.coordinate_picker.start_picking.return_value = True
        app.start_coordinate_picker()
        app.root.withdraw.assert_called_once()


class TestEmergencyVsPicker(unittest.TestCase):
    def test_emergency_while_picking_cancels_picker(self):
        app = _bare_app()
        app.coordinate_picker.is_picking.return_value = True
        app.emergency_stop()
        app.coordinate_picker.stop_picking.assert_called_once_with(cancelled=True)
        app.controller.emergency_stop.assert_not_called()


class TestHotkeys(unittest.TestCase):
    def test_partial_register_unwinds(self):
        with patch("autoclicker.app.hotkeys.keyboard") as kb:
            kb.add_hotkey.side_effect = [None, RuntimeError("fail")]
            err = MagicMock()
            handle = setup_hotkeys(MagicMock(), MagicMock(), MagicMock(), err)
            err.assert_called_once()
            kb.remove_hotkey.assert_called()
            handle.unregister()

    def test_setup_registers_three_keys(self):
        with patch("autoclicker.app.hotkeys.keyboard") as kb:
            handle = setup_hotkeys(MagicMock(), MagicMock(), MagicMock(), MagicMock())
            self.assertEqual(kb.add_hotkey.call_count, 3)
            handle.unregister()
            self.assertEqual(kb.remove_hotkey.call_count, 3)
