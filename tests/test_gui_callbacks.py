"""GUI callback marshaling, picker, emergency, and hotkey tests (no live Tk)."""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.app.controller import StartClickResult
from autoclicker.app.hotkeys import DEFAULT_HOTKEYS
from autoclicker.core.click_engine import (
    STOP_COMPLETED,
    STOP_EMERGENCY,
    STOP_ERROR,
    STOP_SAFETY,
    RunOutcome,
)
from autoclicker.gui.main_window import AutoclickerApp
from autoclicker.gui.sections.status import STATUS_COLORS


def _bare_app() -> AutoclickerApp:
    app = AutoclickerApp.__new__(AutoclickerApp)
    app.root = MagicMock()
    app.controller = MagicMock()
    app.click_engine = MagicMock()
    app.click_engine.is_running = False
    app.coordinate_picker = MagicMock()
    app.coordinate_picker.is_picking.return_value = False
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


class TestRunFinishedUi(unittest.TestCase):
    """#41/#42: the UI paints the run's real outcome and surfaces errors."""

    def test_emergency_outcome_keeps_emergency_status(self):
        app = _bare_app()
        app._stop_status_timer = MagicMock()
        app._on_run_finished(RunOutcome(STOP_EMERGENCY, "Emergency stop", 3))
        app.controller.finish_run.assert_called_once()
        app.status_var.set.assert_called_with("Emergency stop")

    def test_error_outcome_shows_dialog(self):
        app = _bare_app()
        app._stop_status_timer = MagicMock()
        outcome = RunOutcome(STOP_ERROR, "Please select valid coordinates: off screen", 0)
        with patch("autoclicker.gui.dialogs.messagebox") as mb:
            app._on_run_finished(outcome)
        mb.showerror.assert_called_once()
        app.status_var.set.assert_called_with(outcome.message)

    def test_busy_start_reports_status(self):
        app = _bare_app()
        app._collect_ui_settings = MagicMock(return_value={})
        app.failsafe_var = MagicMock()
        app.pause_unfocused_var = MagicMock()
        app.controller.validate_and_start_clicking.return_value = StartClickResult(
            success=False, busy=True
        )
        app.start_clicking()
        app.status_var.set.assert_called_with("Still stopping the previous run. Try again.")


class TestStatusBar(unittest.TestCase):
    """#53: explicit status colors and exact final counters."""

    def test_safety_outcome_paints_error_color(self):
        app = _bare_app()
        app._stop_status_timer = MagicMock()
        app.status_dot = MagicMock()
        app._on_run_finished(RunOutcome(STOP_SAFETY, "Runaway guard: over 50 clicks per second", 9))
        app.status_dot.configure.assert_called_with(foreground=STATUS_COLORS["error"])

    def test_completed_outcome_paints_stopped_color(self):
        app = _bare_app()
        app._stop_status_timer = MagicMock()
        app.status_dot = MagicMock()
        app._on_run_finished(RunOutcome(STOP_COMPLETED, "Done: reached 3 clicks", 3))
        app.status_dot.configure.assert_called_with(foreground=STATUS_COLORS["stopped"])

    def test_paint_stopped_refreshes_counters(self):
        app = _bare_app()
        app._stop_status_timer = MagicMock()
        app.click_count_var = MagicMock()
        app.runtime_var = MagicMock()
        app.performance_var = MagicMock()
        app.click_engine.get_status.return_value = {"click_count": 1234, "runtime": "00:01:02"}
        app._paint_stopped("Stopped")
        app.click_count_var.set.assert_called_with("Clicks: 1234")
        app.runtime_var.set.assert_called_with("Runtime: 00:01:02")


class TestHotkeyWiring(unittest.TestCase):
    """#47: hotkey keys follow the run state and the saved bindings."""

    def test_stopping_releases_stop_keys(self):
        app = _bare_app()
        app._stop_status_timer = MagicMock()
        app._paint_stopped("Stopped")
        app._hotkeys.set_running.assert_called_with(False)

    def test_toggle_starts_or_stops(self):
        app = _bare_app()
        app.start_clicking = MagicMock()
        app.stop_clicking = MagicMock()
        app.click_engine.is_running = False
        app.toggle_clicking()
        app.start_clicking.assert_called_once()
        app.click_engine.is_running = True
        app.toggle_clicking()
        app.stop_clicking.assert_called_once()

    def test_invalid_saved_hotkeys_fall_back_to_defaults(self):
        app = _bare_app()
        app.settings.get.return_value = {"start": "Ctrl+", "emergency": "Esc"}
        self.assertEqual(app._saved_hotkeys(), DEFAULT_HOTKEYS)

    def test_label_suffix_uses_toggle_when_start_unbound(self):
        app = _bare_app()
        app._hotkeys.bindings = {"start": "", "stop": "", "emergency": "Esc", "toggle": "F8"}
        self.assertEqual(app._hotkey_suffix("start"), " (F8)")
        self.assertEqual(app._hotkey_suffix("emergency"), " (Esc)")


class TestMinimizeToTray(unittest.TestCase):
    """#49: minimizing hides to the tray, with a one-time hint."""

    def _app(self, enabled=True, state="iconic"):
        app = _bare_app()
        app.tray_icon = MagicMock()
        app.minimize_to_tray_var = MagicMock()
        app.minimize_to_tray_var.get.return_value = enabled
        app.root.state.return_value = state
        app._tray_hint_shown = False
        return app

    def test_minimize_withdraws_and_hints_once(self):
        app = self._app()
        event = MagicMock(widget=app.root)
        app._on_unmap(event)
        app._on_unmap(event)
        self.assertEqual(app.root.withdraw.call_count, 2)
        app.tray_icon.notify.assert_called_once()

    def test_disabled_or_not_minimized_does_nothing(self):
        for enabled, state in ((False, "iconic"), (True, "withdrawn"), (True, "normal")):
            with self.subTest(enabled=enabled, state=state):
                app = self._app(enabled, state)
                app._on_unmap(MagicMock(widget=app.root))
                app.root.withdraw.assert_not_called()

    def test_child_widget_unmap_ignored(self):
        app = self._app()
        app._on_unmap(MagicMock(widget=MagicMock()))
        app.root.withdraw.assert_not_called()

    def test_status_mirrored_in_tray_tooltip(self):
        app = _bare_app()
        app.tray_icon = MagicMock()
        app._set_status_message("Running...", "running")
        self.assertEqual(app.tray_icon.title, "Windows Autoclicker: Running...")


class TestPauseStatus(unittest.TestCase):
    """#63: pause when unfocused shows a distinct Paused state."""

    def test_paused_then_resumed(self):
        app = _bare_app()
        app._shown_paused = False
        app._show_pause_state(True)
        self.assertIn("Paused", app.status_var.set.call_args.args[0])
        app.status_var.set.reset_mock()
        app._show_pause_state(True)  # unchanged: no repaint
        app.status_var.set.assert_not_called()
        app._show_pause_state(False)
        app.status_var.set.assert_called_with("Running...")


class TestThemeToggle(unittest.TestCase):
    def test_text_styles_follow_the_theme(self):
        """#104: muted and error text colors are reapplied for the new theme."""
        app = _bare_app()
        app.theme_var = MagicMock()
        app.theme_var.get.return_value = "light"
        with (
            patch("autoclicker.gui.main_window.sv_ttk"),
            patch("autoclicker.gui.main_window.apply_text_styles") as apply,
        ):
            app.toggle_theme()
        apply.assert_called_once_with("dark", app.root)
        app.settings.set.assert_called_with("theme", "dark")


class TestMouseWheel(unittest.TestCase):
    """#103: the settings canvas scrolls only for its own widgets, touchpads add up."""

    def _app(self):
        app = _bare_app()
        app.canvas = MagicMock()
        app.canvas.bbox.return_value = (0, 0, 400, 2000)
        app.canvas.winfo_height.return_value = 500
        return app

    def _event(self, app, delta, toplevel=None, cls="TLabel"):
        widget = MagicMock()
        widget.winfo_toplevel.return_value = toplevel if toplevel is not None else app.root
        widget.winfo_class.return_value = cls
        return MagicMock(widget=widget, delta=delta)

    def test_notch_scrolls(self):
        app = self._app()
        app._on_mousewheel(self._event(app, -120))
        app.canvas.yview_scroll.assert_called_once_with(1, "units")

    def test_touchpad_deltas_accumulate(self):
        app = self._app()
        for _ in range(3):
            app._on_mousewheel(self._event(app, 40))
        app.canvas.yview_scroll.assert_called_once_with(-1, "units")

    def test_dialogs_and_lists_keep_their_wheel(self):
        app = self._app()
        app._on_mousewheel(self._event(app, -120, toplevel=MagicMock()))
        app._on_mousewheel(self._event(app, -120, cls="Listbox"))
        app._on_mousewheel(self._event(app, -120, cls="Text"))
        app.canvas.yview_scroll.assert_not_called()


class _Widget:
    """Minimal stand-in for a Tk widget in the settings frame."""

    def __init__(self, cls, *children, disabled=False, style=""):
        self.cls, self.children, self.disabled, self.style = cls, list(children), disabled, style

    def winfo_class(self):
        return self.cls

    def winfo_children(self):
        return self.children

    def cget(self, key):
        return self.style if key == "style" else ("disabled" if self.disabled else "normal")

    def instate(self, spec):
        return self.disabled

    def state(self, spec):
        self.disabled = spec == ["disabled"]


class TestSettingsLock(unittest.TestCase):
    """#102: the form is locked while a run or countdown uses it."""

    def test_locks_enabled_controls_and_restores_exactly(self):
        entry = _Widget("TEntry")
        off_entry = _Widget("TEntry", disabled=True)
        radio = _Widget("TRadiobutton")
        header = _Widget("TButton", style="Toolbutton")
        label = _Widget("TLabel")
        app = _bare_app()
        app.main_frame = _Widget(
            "TFrame", _Widget("TFrame", entry, off_entry, label), radio, header
        )
        app._set_settings_locked(True)
        self.assertTrue(entry.disabled and radio.disabled)
        self.assertFalse(header.disabled)  # section headers stay usable
        self.assertFalse(label.disabled)
        app._set_settings_locked(True)  # idempotent
        self.assertEqual(len(app._locked_widgets), 2)
        app._set_settings_locked(False)
        self.assertFalse(entry.disabled or radio.disabled)
        self.assertTrue(off_entry.disabled)  # was off before the lock; stays off

    def test_stop_unlocks(self):
        app = _bare_app()
        entry = _Widget("TEntry")
        app.main_frame = _Widget("TFrame", entry)
        app._set_settings_locked(True)
        app._paint_stopped("Stopped")
        self.assertFalse(entry.disabled)
