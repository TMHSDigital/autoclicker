"""Failsafe confirmation, start-error dialogs, quit cleanup and the status loop (#165)."""

from __future__ import annotations

import queue
import unittest
from unittest.mock import MagicMock, call, patch

from autoclicker.core.exceptions import AutoclickerError
from autoclicker.gui.main_window import AutoclickerApp


def _bare_app() -> AutoclickerApp:
    """Same shape as ``_bare_app`` in tests/test_gui_callbacks.py (no live Tk)."""
    app = AutoclickerApp.__new__(AutoclickerApp)
    app.root = MagicMock()
    app._ui_calls = queue.SimpleQueue()
    app.controller = MagicMock()
    app.click_engine = MagicMock()
    app.click_engine.is_running = False
    app.coordinate_picker = MagicMock()
    app.coordinate_picker.is_picking.return_value = False
    app.status_var = MagicMock()
    app.settings = MagicMock()
    app._hotkeys = MagicMock()
    app.tray_icon = None
    return app


def _start_app() -> AutoclickerApp:
    """A bare app whose ``_try_start`` can run without Tk."""
    app = _bare_app()
    app.failsafe_var = MagicMock()
    app.pause_unfocused_var = MagicMock()
    app._collect_ui_settings = MagicMock(return_value={})
    app._set_status_message = MagicMock()
    app._paint_run_mode = MagicMock()
    app._set_settings_locked = MagicMock()
    app._start_status_timer = MagicMock()
    app._refresh_target_summary = MagicMock()
    return app


class TestFailsafeToggle(unittest.TestCase):
    def setUp(self):
        self.app = _bare_app()
        self.app.failsafe_var = MagicMock()
        self.app._sync_safety_from_ui = MagicMock()

    @patch("autoclicker.gui.dialogs.messagebox")
    def test_cancel_turns_failsafe_back_on_and_does_not_sync(self, mb):
        self.app.failsafe_var.get.return_value = False
        mb.askokcancel.return_value = False
        self.app._on_failsafe_toggle()
        mb.askokcancel.assert_called_once()
        self.app.failsafe_var.set.assert_called_once_with(True)
        self.app._sync_safety_from_ui.assert_not_called()

    @patch("autoclicker.gui.dialogs.messagebox")
    def test_confirm_keeps_failsafe_off_and_syncs(self, mb):
        self.app.failsafe_var.get.return_value = False
        mb.askokcancel.return_value = True
        self.app._on_failsafe_toggle()
        self.app.failsafe_var.set.assert_not_called()
        self.app._sync_safety_from_ui.assert_called_once()

    @patch("autoclicker.gui.dialogs.messagebox")
    def test_turning_failsafe_on_shows_no_dialog(self, mb):
        self.app.failsafe_var.get.return_value = True
        self.app._on_failsafe_toggle()
        mb.askokcancel.assert_not_called()
        self.app._sync_safety_from_ui.assert_called_once()


class TestStartErrorDialogs(unittest.TestCase):
    def _assert_not_running(self, app: AutoclickerApp) -> None:
        app._paint_run_mode.assert_not_called()
        for c in app._set_status_message.call_args_list:
            self.assertNotEqual(c.args[0], "Running...")
        app._hotkeys.set_running.assert_not_called()
        app._start_status_timer.assert_not_called()

    @patch("autoclicker.gui.dialogs.messagebox")
    def test_autoclicker_error_shows_autoclicker_error_dialog(self, mb):
        app = _start_app()
        app.controller.validate_and_start_clicking.side_effect = AutoclickerError("bad start")
        app._try_start()
        mb.showerror.assert_called_once()
        self.assertEqual(mb.showerror.call_args.args[0], "Autoclicker Error")
        self._assert_not_running(app)

    @patch("autoclicker.gui.dialogs.messagebox")
    def test_other_exception_shows_unexpected_error_dialog(self, mb):
        app = _start_app()
        app.controller.validate_and_start_clicking.side_effect = RuntimeError("boom")
        app._try_start()
        mb.showerror.assert_called_once()
        self.assertEqual(mb.showerror.call_args.args[0], "Unexpected Error")
        self._assert_not_running(app)

    @patch("autoclicker.gui.dialogs.messagebox")
    def test_start_clicking_reports_errors_and_never_raises(self, mb):
        app = _start_app()
        app._start_blocked_reason = MagicMock(return_value=None)
        app._cancel_countdown = MagicMock(return_value=False)
        app._confirm_guard_off = MagicMock(return_value=True)
        app.controller.validate_and_start_clicking.side_effect = AutoclickerError("bad start")
        app.start_clicking()
        self.assertEqual(mb.showerror.call_args.args[0], "Autoclicker Error")
        self._assert_not_running(app)


class TestQuitCleanup(unittest.TestCase):
    def test_quit_stops_recorder_before_stop_clicking_then_tray_and_hotkeys(self):
        app = _bare_app()
        order = MagicMock()
        recorder = MagicMock()
        app._recorder = recorder
        app.stop_clicking = MagicMock()
        app._collect_ui_settings = MagicMock(return_value={})
        app.tray_icon = MagicMock()
        order.attach_mock(recorder.stop, "recorder_stop")
        order.attach_mock(app.stop_clicking, "stop_clicking")
        order.attach_mock(app._hotkeys.unregister, "unregister")
        order.attach_mock(app.tray_icon.stop, "tray_stop")

        app.quit_application()

        self.assertIsNone(app._recorder)
        names = [c[0] for c in order.mock_calls]
        self.assertEqual(names, ["recorder_stop", "stop_clicking", "unregister", "tray_stop"])
        app.root.quit.assert_called_once()
        app.root.destroy.assert_called_once()

    def test_quit_without_recorder_still_cleans_up(self):
        app = _bare_app()
        app._recorder = None
        app.stop_clicking = MagicMock()
        app._collect_ui_settings = MagicMock(return_value={})
        app.tray_icon = MagicMock()
        app.quit_application()
        app.stop_clicking.assert_called_once()
        app._hotkeys.unregister.assert_called_once()
        app.tray_icon.stop.assert_called_once()


class TestUpdateStatusLoop(unittest.TestCase):
    def setUp(self):
        self.app = _bare_app()
        self.app._on_status_update = MagicMock()
        self.app._show_pause_state = MagicMock()

    def test_reschedules_while_running(self):
        self.app.click_engine.is_running = True
        self.app.click_engine.is_paused = True
        self.app._update_status_loop()
        self.app._on_status_update.assert_called_once()
        self.app._show_pause_state.assert_called_once_with(True)
        self.assertEqual(
            self.app.root.after.call_args_list, [call(1000, self.app._update_status_loop)]
        )
        self.assertIs(self.app._status_timer, self.app.root.after.return_value)

    def test_does_not_reschedule_when_stopped(self):
        self.app.click_engine.is_running = False
        self.app._update_status_loop()
        self.app._on_status_update.assert_not_called()
        self.app._show_pause_state.assert_not_called()
        self.app.root.after.assert_not_called()


if __name__ == "__main__":
    unittest.main()
