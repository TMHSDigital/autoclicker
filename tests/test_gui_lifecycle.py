"""End-to-end GUI lifecycle tests without a live Tk (#59).

The real AutoclickerApp is built with every Tk widget and variable replaced by
small fakes, so __init__, all section builders, the controller and the real
ClickEngine thread run for real while pyautogui is patched out. root.after(0)
queues callbacks and pump() runs them on the test thread, which is what the Tk
event loop does: worker callbacks run after the current handler returns.
"""

from __future__ import annotations

import os
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, call, patch

from autoclicker.app.hotkeys import DEFAULT_HOTKEYS


class FakeVar:
    def __init__(self, master=None, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *_args):
        return "trace"


class FakeEntry:
    def __init__(self, *_args, **_kwargs):
        self.text = ""
        self.state = "normal"

    def insert(self, _index, text):
        self.text += str(text)

    def delete(self, *_args):
        self.text = ""

    def get(self):
        return self.text

    def configure(self, **kwargs):
        self.state = str(kwargs.get("state", self.state))

    config = configure

    def cget(self, _key):
        return self.state

    def pack(self, *_a, **_k):
        pass

    grid = pack
    bind = pack


class FakeCollapsible:
    def __init__(self, *_args, **_kwargs):
        self.body = MagicMock()

    def grid(self, *_a, **_k):
        pass


_PENDING: list = []
_PENDING_LOCK = threading.Lock()


class FakeRoot(MagicMock):
    """Tk root whose after(0, fn) queues fn for pump(), like the Tk event loop."""

    def after(self, delay, fn=None, *args):
        if delay == 0 and fn is not None:
            with _PENDING_LOCK:
                _PENDING.append((fn, args))
        return f"after#{delay}"


def pump():
    """Run queued Tk callbacks on the calling (UI) thread."""
    while True:
        with _PENDING_LOCK:
            if not _PENDING:
                return
            fn, args = _PENDING.pop(0)
        fn(*args)


def _settle(app, timeout=3.0):
    """Wait for the click thread to finish, then let the 'UI thread' paint the outcome."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        thread = app.click_engine.click_thread
        if not app.click_engine.is_running and (thread is None or not thread.is_alive()):
            time.sleep(0.02)
            pump()
            return
        time.sleep(0.01)
    raise AssertionError("click run did not finish")


class GuiHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)  # keep legacy-settings migration away from the repo
        self.addCleanup(os.chdir, self._cwd)

        with _PENDING_LOCK:
            _PENDING.clear()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        p = self.stack.enter_context
        p(patch.dict(os.environ, {"APPDATA": self._tmp.name}))
        p(patch("tkinter.Tk", FakeRoot))
        p(patch("tkinter.StringVar", FakeVar))
        p(patch("tkinter.BooleanVar", FakeVar))
        p(patch("tkinter.Canvas", MagicMock()))
        p(patch("tkinter.Listbox", MagicMock()))
        p(patch("tkinter.Label", MagicMock()))
        for name in (
            "Frame",
            "LabelFrame",
            "Label",
            "Button",
            "Radiobutton",
            "Checkbutton",
            "Combobox",
            "Scrollbar",
        ):
            p(patch(f"tkinter.ttk.{name}", MagicMock()))
        p(patch("tkinter.ttk.Entry", FakeEntry))
        p(patch("autoclicker.gui.sections.advanced.CollapsibleFrame", FakeCollapsible))
        self.messagebox = p(patch("autoclicker.gui.dialogs.messagebox"))
        self.simpledialog = p(patch("autoclicker.gui.dialogs.simpledialog"))
        hotkeys_cls = p(patch("autoclicker.gui.main_window.HotkeyManager"))
        self.hotkeys = hotkeys_cls.return_value
        self.hotkeys.bindings = dict(DEFAULT_HOTKEYS)
        p(patch("autoclicker.gui.main_window.create_tray_icon", return_value=None))
        self.picker_cls = p(patch("autoclicker.gui.main_window.CoordinatePicker"))
        self.picker_cls.return_value.is_picking.return_value = False
        self.pyautogui = p(patch("autoclicker.core.click_engine.pyautogui"))
        self.pyautogui.size.return_value = (1920, 1080)
        self.pyautogui.FailSafeException = type("FailSafeException", (Exception,), {})
        self.pyautogui.PyAutoGUIException = type("PyAutoGUIException", (Exception,), {})
        p(patch("autoclicker.core.screen._query_virtual_screen", return_value=None))
        p(patch("autoclicker.app.controller.pyautogui", self.pyautogui))

        from autoclicker.gui.main_window import AutoclickerApp

        self.app = AutoclickerApp()
        self.app.root.state.return_value = "normal"

    def set_fields(self, **values):
        for name, value in values.items():
            entry = getattr(self.app, f"{name}_entry")
            entry.delete(0, "end")
            entry.insert(0, value)


class TestBuild(GuiHarness):
    def test_build_wires_everything(self):
        app = self.app
        self.hotkeys.start.assert_called_once()
        app.start_btn.config.assert_any_call(text="Start (F6)")
        app.emergency_btn.config.assert_any_call(text="Emergency stop (Esc)")
        self.assertEqual(app.target_mode_var.get(), "fixed")
        self.assertEqual(app.x_entry.get(), "100")
        self.assertEqual(app.x_entry.cget("state"), "normal")


class TestRunLifecycle(GuiHarness):
    def test_max_clicks_run_reports_completion_once(self):
        app = self.app
        self.set_fields(interval="5")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="4")
        app.start_clicking()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 4 clicks")
        self.assertEqual(app.click_count_var.get(), "Clicks: 4")
        self.hotkeys.set_running.assert_any_call(True)
        self.hotkeys.set_running.assert_called_with(False)
        log = Path(self._tmp.name, "WindowsAutoclicker", "sessions.log").read_text("utf-8")
        self.assertEqual(log.count("event=stop"), 1)
        self.assertIn("reason=completed", log)

    def test_user_stop(self):
        app = self.app
        self.set_fields(interval="20")
        app.start_clicking()
        time.sleep(0.05)
        app.stop_clicking()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Stopped")
        log = Path(self._tmp.name, "WindowsAutoclicker", "sessions.log").read_text("utf-8")
        self.assertEqual(log.count("event=stop"), 1)
        self.assertIn("reason=user_stop", log)

    def test_emergency_stop(self):
        app = self.app
        self.set_fields(interval="20")
        app.start_clicking()
        time.sleep(0.05)
        app.emergency_stop()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Emergency stop")

    def test_emergency_stop_when_idle_paints_no_error(self):
        """#103: nothing was running, so there is nothing to report in red."""
        app = self.app
        app._set_status_message("Hotkeys saved")
        app.emergency_stop()
        self.assertEqual(app.status_var.get(), "Hotkeys saved")

    def test_emergency_stop_with_picker_open_still_stops_the_run(self):
        """#95: cancelling the picker must not swallow the emergency stop."""
        app = self.app
        self.set_fields(interval="20")
        app.start_clicking()
        time.sleep(0.05)
        self.picker_cls.return_value.is_picking.return_value = True
        app.emergency_stop()
        _settle(app)
        self.picker_cls.return_value.stop_picking.assert_called_once_with(cancelled=True)
        self.assertFalse(app.click_engine.is_running)
        self.assertEqual(app.status_var.get(), "Emergency stop")

    def test_no_start_while_picking(self):
        """#95: a run's clicks would land on the picker overlay."""
        app = self.app
        self.picker_cls.return_value.is_picking.return_value = True
        for start in (app.start_from_button, app.start_clicking):
            with self.subTest(start=start.__name__):
                start()
                self.assertFalse(app.click_engine.is_running)
                self.assertIsNone(app._countdown_job)
                self.assertEqual(app.status_var.get(), "Finish picking before starting")

    def test_failsafe_safety_stop(self):
        app = self.app
        self.pyautogui.click.side_effect = self.pyautogui.FailSafeException()
        self.set_fields(interval="5")
        app.start_clicking()
        _settle(app)
        self.assertIn("Failsafe", app.status_var.get())

    def test_click_error_shows_dialog(self):
        app = self.app
        self.pyautogui.click.side_effect = RuntimeError("driver gone")
        self.set_fields(interval="5")
        app.start_clicking()
        _settle(app)
        self.messagebox.showerror.assert_called()
        self.assertIn("driver gone", app.status_var.get())

    def test_validation_error_names_field(self):
        app = self.app
        self.set_fields(interval="-500")
        app.start_clicking()
        self.assertFalse(app.click_engine.is_running)
        title, message = self.messagebox.showerror.call_args.args
        self.assertEqual(title, "Validation Error")
        self.assertIn("Interval:", message)

    def test_cursor_mode_run(self):
        app = self.app
        app.target_mode_var.set("cursor")
        app._on_target_mode_change()
        self.assertEqual(app.x_entry.cget("state"), "disabled")
        self.set_fields(interval="5")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        app.start_clicking()
        _settle(app)
        # Cursor mode passes no position, so each click lands where the cursor is
        for click in self.pyautogui.click.call_args_list:
            self.assertNotIn("x", click.kwargs)
        self.assertTrue(self.pyautogui.click.called)
        self.assertEqual(app.coord_var.get(), "Target: current cursor position")

    def test_toggle_starts_then_stops(self):
        app = self.app
        self.set_fields(interval="20")
        app.toggle_clicking()
        self.assertTrue(app.click_engine.is_running)
        app.toggle_clicking()
        _settle(app)
        self.assertFalse(app.click_engine.is_running)


class TestOtherActions(GuiHarness):
    def test_presets_save_load_delete(self):
        app = self.app
        self.set_fields(x="321", y="654")
        self.simpledialog.askstring.return_value = "Spot"
        app.save_preset()
        self.set_fields(x="0", y="0")
        app.preset_var.set("Spot")
        app.load_preset()
        self.assertEqual((app.x_entry.get(), app.y_entry.get()), ("321", "654"))
        self.messagebox.askokcancel.return_value = True
        app.delete_preset()
        self.assertEqual(app.preset_manager.get_preset_names(), [])

    def test_theme_toggle_persists(self):
        app = self.app
        app.toggle_theme()
        self.assertEqual(app.settings.get("theme"), "dark")

    def test_hotkeys_dialog_save(self):
        app = self.app
        with patch("autoclicker.gui.main_window.HotkeysDialog") as dialog:
            app.open_hotkeys_dialog()
        self.hotkeys.set_suspended.assert_called_with(True)
        on_save = dialog.call_args.kwargs["on_save"]
        new = {**DEFAULT_HOTKEYS, "toggle": "F8"}
        on_save(new)
        self.assertEqual(app.settings.get("hotkeys"), new)
        self.hotkeys.set_bindings.assert_called_with(new)

    def test_picker_selection_fills_fields(self):
        app = self.app
        app._on_coordinates_selected(-1200, 300)
        self.assertEqual((app.x_entry.get(), app.y_entry.get()), ("-1200", "300"))
        self.assertEqual(app.status_var.get(), "Coordinate selected")

    def test_quit_persists_and_releases(self):
        app = self.app
        self.set_fields(x="42")
        app.quit_application()
        self.hotkeys.unregister.assert_called_once()
        self.assertEqual(app.settings.get("x_coord"), 42)

    def test_close_asks_first(self):
        app = self.app
        app.quit_application = MagicMock()
        self.messagebox.askokcancel.return_value = False
        app.on_closing()
        app.quit_application.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class TestHotkeysDialog(unittest.TestCase):
    """The rebinding dialog captures keys, rejects bad ones, and saves valid sets."""

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        p = self.stack.enter_context
        p(patch("tkinter.Toplevel", MagicMock()))
        p(patch("tkinter.StringVar", FakeVar))
        for name in ("Frame", "Label", "Button", "Entry"):
            p(patch(f"tkinter.ttk.{name}", MagicMock()))
        from autoclicker.gui.hotkeys_dialog import HotkeysDialog

        self.saved: list = []
        self.closed: list = []
        self.dialog = HotkeysDialog(
            MagicMock(),
            dict(DEFAULT_HOTKEYS),
            on_save=self.saved.append,
            on_close=lambda: self.closed.append(True),
        )

    @staticmethod
    def _key(keysym, state=0):
        return MagicMock(keysym=keysym, state=state)

    def test_capture_save_and_close(self):
        d = self.dialog
        self.assertEqual(d._capture("toggle", self._key("F8")), "break")
        self.assertEqual(d._vars["toggle"].get(), "F8")
        d._capture("start", self._key("F9", 0x0004))  # Ctrl+F9
        d._save()
        self.assertEqual(self.saved[-1]["start"], "Ctrl+F9")
        self.assertEqual(self.saved[-1]["toggle"], "F8")
        self.assertEqual(self.closed, [True])

    def test_bad_key_and_duplicates_are_reported(self):
        d = self.dialog
        d._capture("start", self._key("a"))  # bare letter not allowed
        self.assertTrue(d._error.get())
        d._capture("stop", self._key("F6"))  # same as start
        d._save()
        self.assertEqual(self.saved, [])
        self.assertIn("F6", d._error.get())

    def test_backspace_clears_and_defaults_restore(self):
        d = self.dialog
        d._capture("stop", self._key("BackSpace"))
        self.assertEqual(d._vars["stop"].get(), "")
        d._defaults()
        self.assertEqual(d._vars["stop"].get(), "F7")
        self.assertEqual(d._capture("stop", self._key("Tab")), "")


class TestSpeedLimitField(GuiHarness):
    """#64: the runaway guard ceiling is editable in Advanced."""

    def test_ceiling_is_saved_from_the_ui(self):
        app = self.app
        self.assertEqual(app.max_cps_entry.get(), "50")
        self.set_fields(interval="5", max_cps="120")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        app.start_clicking()
        _settle(app)
        self.assertEqual(app.settings.get("max_cps_ceiling"), 120)
        self.assertEqual(app.click_engine.max_cps_ceiling, 120)

    def test_turning_the_guard_off_asks_first(self):
        app = self.app
        self.set_fields(interval="5", max_cps="0")
        self.messagebox.askokcancel.return_value = False
        app.start_clicking()
        self.assertFalse(app.click_engine.is_running)
        self.assertEqual(app.settings.get("max_cps_ceiling"), 50)

        self.messagebox.askokcancel.return_value = True
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        app.start_clicking()
        _settle(app)
        self.assertEqual(app.settings.get("max_cps_ceiling"), 0)

    def test_invalid_ceiling_is_reported(self):
        app = self.app
        self.set_fields(max_cps="fast")
        app.start_clicking()
        _title, message = self.messagebox.showerror.call_args.args
        self.assertIn("Max clicks per second", message)


class TestStartCountdown(GuiHarness):
    """#74: Start button and tray starts count down; every stop path cancels it."""

    def begin(self, delay="3"):
        app = self.app
        self.set_fields(interval="5", start_delay=delay)
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        app.start_from_button()
        return app

    def test_counts_down_then_starts(self):
        app = self.begin("2")
        self.assertEqual(app.status_var.get(), "Starting in 2...")
        self.assertFalse(app.click_engine.is_running)
        self.hotkeys.set_running.assert_called_with(True)
        app._countdown_tick(1)
        self.assertEqual(app.status_var.get(), "Starting in 1...")
        app._countdown_tick(0)
        self.assertIsNone(app._countdown_job)
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")
        self.assertEqual(app.settings.get("start_delay_seconds"), 2)

    def test_zero_delay_starts_at_once(self):
        app = self.begin("0")
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")

    def test_stop_cancels(self):
        app = self.begin()
        seen = len(app.start_btn.config.call_args_list)
        app.stop_clicking()
        self.assertIsNone(app._countdown_job)
        self.assertEqual(app.status_var.get(), "Start cancelled")
        self.assertIn(call(state="normal"), app.start_btn.config.call_args_list[seen:])
        self.hotkeys.set_running.assert_called_with(False)
        log = Path(self._tmp.name, "WindowsAutoclicker", "sessions.log")
        self.assertFalse(log.exists() and "event=start" in log.read_text("utf-8"))

    def test_emergency_and_toggle_cancel(self):
        for cancel in ("emergency_stop", "toggle_clicking"):
            with self.subTest(cancel=cancel):
                app = self.begin()
                getattr(app, cancel)()
                self.assertIsNone(app._countdown_job)
                self.assertFalse(app.click_engine.is_running)
                self.assertEqual(app.status_var.get(), "Start cancelled")

    def test_start_hotkey_during_countdown_starts_now(self):
        app = self.begin()
        app.start_clicking()
        self.assertIsNone(app._countdown_job)
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")

    def test_hotkeys_dialog_refused_during_countdown(self):
        """#93: the run would start with every global stop key released."""
        app = self.begin()
        with patch("autoclicker.gui.main_window.HotkeysDialog") as dialog:
            app.open_hotkeys_dialog()
        dialog.assert_not_called()
        self.assertNotIn(call(True), self.hotkeys.set_suspended.call_args_list)
        self.messagebox.showwarning.assert_called_once()
        self.assertIsNotNone(app._countdown_job)

    def test_no_start_while_hotkeys_dialog_open(self):
        """#93: Start (button, tray, countdown end) waits until the dialog closes."""
        app = self.app
        self.set_fields(interval="5", start_delay="0")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        with patch("autoclicker.gui.main_window.HotkeysDialog") as dialog:
            app.open_hotkeys_dialog()
        for start in (app.start_from_button, app.start_clicking):
            with self.subTest(start=start.__name__):
                start()
                self.assertFalse(app.click_engine.is_running)
                self.assertEqual(app.status_var.get(), "Close the Hotkeys dialog before starting")
        dialog.call_args.kwargs["on_close"]()
        self.hotkeys.set_suspended.assert_called_with(False)
        app.start_from_button()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")

    def test_invalid_input_is_reported_before_counting(self):
        app = self.app
        self.set_fields(interval="abc")
        app.start_from_button()
        self.assertIsNone(app._countdown_job)
        self.messagebox.showerror.assert_called_once()

    def test_invalid_delay_is_reported(self):
        app = self.app
        self.set_fields(start_delay="90")
        app.start_from_button()
        _title, message = self.messagebox.showerror.call_args.args
        self.assertIn("Start delay", message)

    def test_input_broken_during_countdown_does_not_start(self):
        app = self.begin()
        self.set_fields(interval="abc")
        seen = len(app.start_btn.config.call_args_list)
        app._countdown_tick(0)
        self.assertFalse(app.click_engine.is_running)
        self.assertEqual(app.status_var.get(), "Not started")
        self.assertIn(call(state="normal"), app.start_btn.config.call_args_list[seen:])


class TestProfilesUi(GuiHarness):
    """#73: profiles restore the click settings, ask before overwriting, import and export."""

    def setUp(self):
        super().setUp()
        self.filedialog = self.stack.enter_context(patch("autoclicker.gui.dialogs.filedialog"))

    def test_save_and_load_restores_settings(self):
        app = self.app
        self.set_fields(x="640", y="480", interval="250", variation="20")
        app.button_var.set("right")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="300")
        self.simpledialog.askstring.return_value = "Work"
        app.save_preset()
        self.assertIn("(640, 480)", app.preset_summary_var.get())

        # Change everything, then load the profile back
        self.set_fields(x="1", y="1", interval="999", variation="0")
        app.button_var.set("left")
        app.limit_clicks_var.set(False)
        app.preset_var.set("Work")
        app.load_preset()
        self.assertEqual(app.x_entry.get(), "640")
        self.assertEqual(app.interval_entry.get(), "250")
        self.assertEqual(app.variation_entry.get(), "20")
        self.assertEqual(app.button_var.get(), "right")
        self.assertTrue(app.limit_clicks_var.get())
        self.assertEqual(app.max_clicks_entry.get(), "300")

    def test_overwrite_asks_first(self):
        app = self.app
        self.simpledialog.askstring.return_value = "Spot"
        app.save_preset()
        self.set_fields(x="900")
        self.messagebox.askyesno.return_value = False
        app.save_preset()
        self.messagebox.askyesno.assert_called_once()
        self.assertEqual(app.preset_manager.load_preset("Spot"), (100, 100))

    def test_invalid_form_is_not_saved(self):
        app = self.app
        self.set_fields(interval="soon")
        app.save_preset()
        self.simpledialog.askstring.assert_not_called()
        self.messagebox.showerror.assert_called_once()

    def test_cursor_profile_switches_mode(self):
        app = self.app
        app.target_mode_var.set("cursor")
        self.simpledialog.askstring.return_value = "Hover"
        app.save_preset()
        app.target_mode_var.set("fixed")
        app.preset_var.set("Hover")
        app.load_preset()
        self.assertEqual(app.target_mode_var.get(), "cursor")
        self.assertEqual(app.x_entry.cget("state"), "disabled")

    def test_export_and_import(self):
        app = self.app
        self.simpledialog.askstring.return_value = "Spot"
        app.save_preset()
        out = str(Path(self._tmp.name, "profiles.json"))
        self.filedialog.asksaveasfilename.return_value = out
        app.export_profiles()
        self.assertTrue(Path(out).exists())

        app.preset_manager.delete_preset("Spot")
        self.filedialog.askopenfilename.return_value = out
        app.import_profiles()
        self.assertEqual(app.preset_manager.get_preset_names(), ["Spot"])
        self.assertIn("Added 1", self.messagebox.showinfo.call_args.args[1])

    def test_import_of_a_foreign_file_is_reported(self):
        app = self.app
        bad = Path(self._tmp.name, "bad.json")
        bad.write_text("[]", encoding="utf-8")
        self.filedialog.askopenfilename.return_value = str(bad)
        app.import_profiles()
        self.messagebox.showerror.assert_called_once()


class TestSequenceUi(GuiHarness):
    """#72: build a sequence with the picker, edit it, and run it."""

    def add(self, x, y):
        app = self.app
        app.add_sequence_point()
        on_selected = self.picker_cls.return_value.start_picking.call_args.kwargs["on_selected"]
        on_selected(x, y)

    def test_build_edit_and_run(self):
        app = self.app
        app.target_mode_var.set("sequence")
        app._on_target_mode_change()
        app.sequence_frame.grid.assert_called()
        self.assertEqual(app.x_entry.cget("state"), "disabled")

        self.add(10, 10)
        app.button_var.set("right")
        self.add(20, 20)
        self.add(30, 30)
        self.assertEqual(
            [(s["x"], s["button"]) for s in app.sequence_steps],
            [(10, "left"), (20, "right"), (30, "right")],
        )
        self.assertEqual(len(app.settings.get("sequence")), 3)  # persisted

        app.sequence_list.curselection.return_value = (2,)
        app.move_sequence_step(-1)
        self.assertEqual([s["x"] for s in app.sequence_steps], [10, 30, 20])
        app.sequence_list.curselection.return_value = (0,)
        app.remove_sequence_step()
        self.assertEqual([s["x"] for s in app.sequence_steps], [30, 20])
        self.simpledialog.askfloat.return_value = 5
        app.edit_sequence_delay()
        self.assertEqual(app.sequence_steps[0]["delay_ms"], 5)

        self.set_fields(interval="0", sequence_repeat="2")
        app.start_clicking()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: ran the sequence 2 times")
        clicked = [(c.kwargs["x"], c.kwargs["y"]) for c in self.pyautogui.click.call_args_list]
        self.assertEqual(clicked, [(30, 30), (20, 20)] * 2)
        log = Path(self._tmp.name, "WindowsAutoclicker", "sessions.log").read_text("utf-8")
        self.assertIn("target=sequence:2", log)

    def test_empty_sequence_is_reported(self):
        app = self.app
        app.target_mode_var.set("sequence")
        app.start_clicking()
        _title, message = self.messagebox.showerror.call_args.args
        self.assertIn("Sequence: Add at least one point", message)

    def test_other_modes_hide_the_steps(self):
        app = self.app
        app.target_mode_var.set("cursor")
        app._on_target_mode_change()
        app.sequence_frame.grid_remove.assert_called()

    def test_profile_keeps_the_sequence(self):
        app = self.app
        app.target_mode_var.set("sequence")
        self.add(40, 50)
        self.simpledialog.askstring.return_value = "Route"
        app.save_preset()
        app.sequence_steps.clear()
        app.target_mode_var.set("fixed")
        app.preset_var.set("Route")
        app.load_preset()
        self.assertEqual(app.target_mode_var.get(), "sequence")
        self.assertEqual([(s["x"], s["y"]) for s in app.sequence_steps], [(40, 50)])
        self.assertIn("sequence of 1 point", app.preset_summary_var.get())


class TestTargetSummary(GuiHarness):
    def test_status_line_follows_the_form(self):
        app = self.app
        self.assertEqual(app.coord_var.get(), "Target: (100, 100)")
        app._on_coordinates_selected(640, 480)
        self.assertEqual(app.coord_var.get(), "Target: (640, 480)")
        app.target_mode_var.set("cursor")
        app._on_target_mode_change()
        self.assertEqual(app.coord_var.get(), "Target: current cursor position")
        app.target_mode_var.set("sequence")
        app._on_target_mode_change()
        self.assertEqual(app.coord_var.get(), "Target: sequence of 0 points")


class TestActionUi(GuiHarness):
    """#78: the Action row enables the right field and runs key presses."""

    def test_action_switches_fields(self):
        app = self.app
        self.assertEqual(app.hold_entry.cget("state"), "disabled")
        self.assertEqual(app.key_entry.cget("state"), "disabled")
        app.action_var.set("key")
        app._apply_action_state()
        self.assertEqual(app.key_entry.cget("state"), "normal")
        self.assertEqual(app.hold_entry.cget("state"), "disabled")

    def test_key_run(self):
        app = self.app
        app.action_var.set("key")
        app._apply_action_state()
        self.set_fields(key="F5", interval="0")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        app.start_clicking()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")
        self.assertEqual(self.pyautogui.press.call_count, 2)
        log = Path(self._tmp.name, "WindowsAutoclicker", "sessions.log").read_text("utf-8")
        self.assertIn("target=key:f5", log)

    def test_key_has_no_point_to_click(self):
        """#102: X/Y are off for Key even in Fixed mode."""
        app = self.app
        self.assertEqual(app.x_entry.cget("state"), "normal")
        app.action_var.set("key")
        app._apply_action_state()
        self.assertEqual(app.x_entry.cget("state"), "disabled")

    def test_switching_to_a_mode_that_cannot_run_the_action_falls_back_to_click(self):
        app = self.app
        app.action_var.set("key")
        app._apply_action_state()
        app.target_mode_var.set("sequence")
        app._on_target_mode_change()
        self.assertEqual(app.action_var.get(), "click")
        self.assertEqual(app.key_entry.cget("state"), "disabled")

    def test_a_profile_keeps_its_action_so_start_can_explain(self):
        app = self.app
        app.apply_form_values({"target_mode": "image", "action": "key", "key": "f5"})
        self.assertEqual(app.action_var.get(), "key")
        app.start_clicking()
        self.assertFalse(app.click_engine.is_running)
        _title, message = self.messagebox.showerror.call_args.args
        self.assertIn("Image targets click or hold", message)


class TestKeyTargetSummary(GuiHarness):
    def test_key_action_names_the_focused_window(self):
        app = self.app
        self.set_fields(key="f5")
        app.action_var.set("key")
        app._apply_action_state()
        self.assertEqual(app.coord_var.get(), "Target: the focused window (press f5)")


class TestConditionUi(GuiHarness):
    """#80: sample a pixel's color, then the run only clicks while it matches."""

    def test_sample_then_run(self):
        app = self.app
        self.assertEqual(app.condition_label_var.get(), "off")
        app.sample_condition_pixel()
        on_selected = self.picker_cls.return_value.start_picking.call_args.kwargs["on_selected"]
        with patch.object(app.root, "after") as after:
            on_selected(300, 400)
        delay, read, *args = after.call_args.args
        self.assertEqual(delay, 200)  # waits for the overlay to repaint away
        with patch("pyautogui.pixel", return_value=(0, 200, 0)):
            read(*args)
        self.assertEqual(app.condition_point, (300, 400, "#00c800"))
        self.assertEqual(app.condition_var.get(), "wait")
        self.assertIn("(300, 400)", app.condition_label_var.get())
        self.assertEqual(app.settings.get("condition_color"), "#00c800")

        self.pyautogui.pixel.return_value = (0, 200, 0)
        self.set_fields(interval="0")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        app.start_clicking()
        _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")
        self.pyautogui.pixel.assert_called_with(300, 400)

    def test_paused_for_pixel_shows_the_reason(self):
        app = self.app
        app.click_engine.pause_reason = "the watched pixel to match"
        app._show_pause_state(True)
        self.assertEqual(app.status_var.get(), "Paused: waiting for the watched pixel to match")
        app._show_pause_state(False)
        self.assertEqual(app.status_var.get(), "Running...")


class TestRecordingUi(GuiHarness):
    """#86: Record captures clicks into sequence steps; stop paths finish it."""

    def setUp(self):
        super().setUp()
        self.recorder_cls = self.stack.enter_context(
            patch("autoclicker.gui.features.recording.ClickRecorder")
        )
        self.recorder_cls.return_value.start.return_value = True
        self.stack.enter_context(
            patch("autoclicker.gui.features.recording.root_window_at", side_effect=lambda x, y: x)
        )
        self.stack.enter_context(
            patch(
                "autoclicker.gui.features.recording.is_own_window", side_effect=lambda h: h == 999
            )
        )

    def feed(self, *clicks):
        from autoclicker.core.recorder import RecordedClick

        on_click = self.recorder_cls.call_args.kwargs["on_click"]
        for x, y, t in clicks:
            on_click(RecordedClick(x, y, "left", t))
        pump()

    def test_record_then_finish_with_stop(self):
        app = self.app
        app.toggle_sequence_recording()
        self.hotkeys.set_running.assert_called_with(True)
        self.assertIn("Recording", app.status_var.get())
        self.feed((100, 100, 0.0), (999, 5, 0.4), (200, 200, 0.6))  # 999 = our own window
        self.assertIn("2 clicks", app.status_var.get())
        app.stop_clicking()  # the Stop hotkey/button finishes recording
        self.recorder_cls.return_value.stop.assert_called_once()
        self.hotkeys.set_running.assert_called_with(False)
        self.assertEqual([(s["x"], s["y"]) for s in app.sequence_steps], [(100, 100), (200, 200)])
        self.assertEqual(app.sequence_steps[0]["delay_ms"], 600)
        self.assertEqual(app.target_mode_var.get(), "sequence")
        self.assertEqual(app.status_var.get(), "Recorded 2 steps")

    def test_existing_steps_can_be_kept(self):
        app = self.app
        app.sequence_steps = [
            {"x": 1, "y": 1, "button": "left", "click_type": "single", "delay_ms": 0}
        ]
        app.toggle_sequence_recording()
        self.feed((100, 100, 0.0))
        self.messagebox.askyesnocancel.return_value = False  # keep, append
        app.toggle_sequence_recording()
        self.assertEqual([s["x"] for s in app.sequence_steps], [1, 100])

    def test_recording_can_be_discarded(self):
        """#103: Cancel throws the recording away instead of appending it."""
        app = self.app
        app.sequence_steps = [
            {"x": 1, "y": 1, "button": "left", "click_type": "single", "delay_ms": 0}
        ]
        app.toggle_sequence_recording()
        self.feed((100, 100, 0.0))
        self.messagebox.askyesnocancel.return_value = None
        app.toggle_sequence_recording()
        self.assertEqual([s["x"] for s in app.sequence_steps], [1])
        self.assertEqual(app.status_var.get(), "Recording discarded")

    def test_truncation_is_reported(self):
        from autoclicker.core.settings_manager import MAX_SEQUENCE_STEPS

        app = self.app
        app.toggle_sequence_recording()
        self.feed(*[(10 + i * 10, 100, i * 1.0) for i in range(MAX_SEQUENCE_STEPS + 3)])
        app.toggle_sequence_recording()
        self.assertEqual(len(app.sequence_steps), MAX_SEQUENCE_STEPS)
        self.assertIn(
            f"Kept {MAX_SEQUENCE_STEPS} of {MAX_SEQUENCE_STEPS + 3}", app.status_var.get()
        )

    def test_no_clicks_and_start_blocked_while_recording(self):
        app = self.app
        app.toggle_sequence_recording()
        app.start_clicking()
        self.assertFalse(app.click_engine.is_running)
        self.assertEqual(app.status_var.get(), "Finish recording before starting")
        app.emergency_stop()
        self.assertEqual(app.status_var.get(), "Recording ended with no clicks")

    def test_start_button_refused_while_recording(self):
        """#95: no countdown while recording, and the recorder keeps its stop keys."""
        app = self.app
        app.toggle_sequence_recording()
        self.hotkeys.set_running.reset_mock()
        app.start_from_button()
        self.assertIsNone(app._countdown_job)
        self.assertEqual(app.status_var.get(), "Finish recording before starting")
        self.hotkeys.set_running.assert_not_called()
        self.assertIsNotNone(app._recorder)

    def test_hotkeys_dialog_refused_while_recording(self):
        app = self.app
        app.toggle_sequence_recording()
        with patch("autoclicker.gui.main_window.HotkeysDialog") as dialog:
            app.open_hotkeys_dialog()
        dialog.assert_not_called()

    def test_hook_unavailable(self):
        self.recorder_cls.return_value.start.return_value = False
        self.app.toggle_sequence_recording()
        self.assertIn("Could not start recording", self.app.status_var.get())


class TestImageUi(GuiHarness):
    """#87: capture an image, then a run clicks wherever it is found."""

    def test_capture_then_run(self):
        from PIL import Image

        from autoclicker.core.screen import ScreenBounds

        app = self.app
        picker = self.picker_cls.return_value
        picker.start_selecting_area.return_value = True
        app.capture_image()
        on_selected = picker.start_selecting_area.call_args.kwargs["on_selected"]
        with patch.object(app.root, "after") as after:
            on_selected(ScreenBounds(500, 400, 40, 20))
        _delay, grab_later, area = after.call_args.args
        with patch(
            "autoclicker.gui.features.image.grab",
            return_value=Image.new("RGB", (40, 20), (9, 9, 9)),
        ):
            grab_later(area)
        self.assertEqual(app.target_mode_var.get(), "image")
        self.assertEqual(app.image_region, [500, 400, 40, 20])  # where it was captured
        self.assertTrue(Path(app.image_path).is_file())
        self.assertIn("Captured 40x20", app.image_info_var.get())
        self.assertEqual(app.coord_var.get(), "Target: wherever the captured image appears")

        self.set_fields(interval="0")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="2")
        with patch("autoclicker.core.image_match.ImageTarget.locate", return_value=(520, 410)):
            app.start_clicking()
            _settle(app)
        self.assertEqual(app.status_var.get(), "Done: reached 2 clicks")
        self.pyautogui.click.assert_called_with(x=520, y=410, button="left", clicks=1)

    def _capture(self, when):
        from PIL import Image

        from autoclicker.core.screen import ScreenBounds

        app = self.app
        picker = self.picker_cls.return_value
        picker.start_selecting_area.return_value = True
        app.capture_image()
        on_selected = picker.start_selecting_area.call_args.kwargs["on_selected"]
        with patch.object(app.root, "after") as after:
            on_selected(ScreenBounds(500, 400, 40, 20))
        _delay, grab_later, area = after.call_args.args
        with (
            patch("autoclicker.gui.features.image.grab", return_value=Image.new("RGB", (40, 20))),
            patch("autoclicker.gui.features.image.time.strftime", return_value=when),
        ):
            grab_later(area)
        return Path(app.image_path)

    def test_recapture_deletes_the_old_image_unless_a_profile_uses_it(self):
        """#100: captures no longer pile up, but profile images are kept."""
        app = self.app
        first = self._capture("1")
        second = self._capture("2")
        self.assertFalse(first.exists())
        self.assertTrue(second.is_file())
        app.preset_manager.save_profile(
            "Keep", {"x": 1, "y": 1, "target_mode": "image", "image_path": str(second)}
        )
        third = self._capture("3")
        self.assertTrue(second.is_file())
        self.assertTrue(third.is_file())

    def test_clear_forgets_the_image(self):
        """#123: Clear disarms the image and deletes an unused capture."""
        app = self.app
        path = self._capture("9")
        app.target_mode_var.set("image")
        app.clear_image()
        self.assertEqual((app.image_path, app.image_region), ("", []))
        self.assertEqual(app.image_info_var.get(), "No image captured yet")
        self.assertFalse(path.exists())
        self.assertEqual(app.settings.get("image_path"), "")
        app.start_clicking()
        self.assertFalse(app.click_engine.is_running)  # nothing to click

    def test_tolerance_reaches_the_engine(self):
        app = self.app
        self._capture("8")
        self.set_fields(image_tolerance="10", interval="0")
        app.limit_clicks_var.set(True)
        self.set_fields(max_clicks="1")
        with patch("autoclicker.core.image_match.ImageTarget.locate", return_value=(5, 5)):
            app.start_clicking()
            self.assertEqual(app.click_engine._image.tolerance, 10)
            _settle(app)
        self.assertEqual(app.settings.get("image_tolerance"), 10)

    def test_capture_cancel_explains_the_minimum_size(self):
        app = self.app
        picker = self.picker_cls.return_value
        picker.start_selecting_area.return_value = True
        app.capture_image()
        picker.start_selecting_area.call_args.kwargs["on_cancelled"]()
        self.assertIn("at least 4 px", app.status_var.get())

    def test_profile_brings_its_own_image(self):
        """#98: loading an image profile arms its image; one without an image clears it."""
        app = self.app
        app.image_path, app.image_region = "C:/old.png", [0, 0, 10, 10]
        app.preset_manager.save_profile(
            "Ok",
            {"x": 1, "y": 1, "target_mode": "image", "image_path": "C:/ok.png",
             "image_region": [10, 20, 300, 200], "image_margin": 40},
        )  # fmt: skip
        app.preset_manager.save_profile("Bare", {"x": 1, "y": 1, "target_mode": "image"})
        app.preset_var.set("Ok")
        app.load_preset()
        self.assertEqual((app.image_path, app.image_region), ("C:/ok.png", [10, 20, 300, 200]))
        self.assertEqual(app.image_margin_entry.get(), "40")
        self.assertIn("Captured 300x200", app.image_info_var.get())
        self.assertIn("wherever its image appears", app.preset_summary_var.get())
        app.preset_var.set("Bare")
        app.load_preset()
        self.assertEqual((app.image_path, app.image_region), ("", []))
        self.assertEqual(app.image_info_var.get(), "No image captured yet")

    def test_run_without_capture_is_reported(self):
        app = self.app
        app.target_mode_var.set("image")
        app.start_clicking()
        _title, message = self.messagebox.showerror.call_args.args
        self.assertIn("Capture an image first", message)
