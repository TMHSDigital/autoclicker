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
from unittest.mock import MagicMock, patch

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
        self.messagebox = p(patch("autoclicker.gui.main_window.messagebox"))
        self.simpledialog = p(patch("autoclicker.gui.main_window.simpledialog"))
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
        self.pyautogui.moveTo.assert_not_called()
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
