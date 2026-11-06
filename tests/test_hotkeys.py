"""RegisterHotKey-based hotkeys (#57) and configurable bindings (#47)."""

import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.app import hotkeys as hotkeys_module
from autoclicker.app.hotkeys import (
    DEFAULT_HOTKEYS,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    WM_APP_APPLY,
    WM_HOTKEY,
    WM_QUIT,
    HotkeyError,
    HotkeyManager,
    format_hotkey,
    normalize_hotkey,
    parse_hotkey,
    validate_bindings,
)
from autoclicker.gui.hotkeys_dialog import hotkey_from_event


class TestParsing(unittest.TestCase):
    def test_function_and_named_keys(self):
        self.assertEqual(parse_hotkey("F6"), (0, 0x75))
        self.assertEqual(parse_hotkey("f24"), (0, 0x87))
        self.assertEqual(parse_hotkey("Esc"), (0, 0x1B))
        self.assertEqual(parse_hotkey("escape"), (0, 0x1B))
        self.assertEqual(parse_hotkey("Pause"), (0, 0x13))

    def test_modifiers(self):
        self.assertEqual(parse_hotkey("Ctrl+Shift+F6"), (MOD_CONTROL | MOD_SHIFT, 0x75))
        self.assertEqual(parse_hotkey("alt + x"), (MOD_ALT, ord("X")))

    def test_rejections(self):
        for bad in ("", "Ctrl+", "Ctrl+Shift", "Hyper+F6", "F25", "x", "5", "Tab"):
            with self.subTest(bad=bad), self.assertRaises(HotkeyError):
                parse_hotkey(bad)

    def test_canonical_form_round_trips(self):
        self.assertEqual(normalize_hotkey("shift+ctrl+f6"), "Ctrl+Shift+F6")
        self.assertEqual(normalize_hotkey("escape"), "Esc")
        self.assertEqual(format_hotkey(MOD_ALT, ord("Q")), "Alt+Q")

    def test_validate_bindings(self):
        self.assertEqual(validate_bindings(DEFAULT_HOTKEYS), DEFAULT_HOTKEYS)
        with self.assertRaises(HotkeyError):
            validate_bindings({"start": "F6", "stop": "f6", "emergency": "Esc"})
        with self.assertRaises(HotkeyError):
            validate_bindings({"start": "F6", "stop": "F7", "emergency": ""})
        with self.assertRaises(HotkeyError):
            validate_bindings({"start": "", "toggle": "", "emergency": "Esc"})
        only_toggle = validate_bindings({"toggle": "F8", "emergency": "Esc"})
        self.assertEqual(only_toggle["toggle"], "F8")


class TestTkKeyCapture(unittest.TestCase):
    def test_event_translation(self):
        self.assertEqual(hotkey_from_event("F6", 0), "F6")
        self.assertEqual(hotkey_from_event("Escape", 0), "Esc")
        self.assertEqual(hotkey_from_event("a", 0x0004), "Ctrl+A")
        self.assertEqual(hotkey_from_event("F9", 0x0004 | 0x0001), "Ctrl+Shift+F9")
        self.assertEqual(hotkey_from_event("x", 0x20000), "Alt+X")
        self.assertIsNone(hotkey_from_event("Control_L", 0x0004))
        with self.assertRaises(HotkeyError):
            hotkey_from_event("a", 0)


class TestManagerClaimsByState(unittest.TestCase):
    """Keys are claimed by run state so Esc stays usable in other apps when idle."""

    def setUp(self):
        self.user32 = MagicMock()
        self.user32.RegisterHotKey.return_value = 1
        self.callbacks = {"start": MagicMock(), "stop": MagicMock(), "emergency": MagicMock()}
        self.errors: list[str] = []
        self.manager = HotkeyManager(self.callbacks, self.errors.append, user32=self.user32)

    def _registered_vks(self):
        return [c.args[3] for c in self.user32.RegisterHotKey.call_args_list]

    def test_idle_claims_only_start(self):
        self.manager._apply()
        self.assertEqual(self._registered_vks(), [0x75])
        flags = self.user32.RegisterHotKey.call_args.args[2]
        self.assertTrue(flags & MOD_NOREPEAT)

    def test_running_claims_stop_and_emergency(self):
        self.manager._running = True
        self.manager._apply()
        self.assertEqual(self._registered_vks(), [0x76, 0x1B])

    def test_reapply_unregisters_previous(self):
        self.manager._apply()
        self.manager._running = True
        self.manager._apply()
        self.user32.UnregisterHotKey.assert_called_once_with(None, 1)

    def test_suspended_claims_nothing(self):
        self.manager._suspended = True
        self.manager._apply()
        self.user32.RegisterHotKey.assert_not_called()

    def test_failed_registration_is_reported(self):
        self.user32.RegisterHotKey.return_value = 0
        self.manager._apply()
        self.assertEqual(len(self.errors), 1)
        self.assertIn("F6", self.errors[0])

    def test_dispatch_routes_to_action(self):
        self.manager._running = True
        self.manager._apply()
        self.manager._dispatch(2)  # second registered id = emergency
        self.callbacks["emergency"].assert_called_once()
        self.callbacks["stop"].assert_not_called()

    def test_set_running_posts_only_on_change(self):
        self.manager._thread_id = 42
        self.manager.set_running(False)
        self.user32.PostThreadMessageW.assert_not_called()
        self.manager.set_running(True)
        self.user32.PostThreadMessageW.assert_called_once()

    def test_no_user32_reports_unavailable(self):
        errors: list[str] = []
        manager = HotkeyManager({}, errors.append, user32=None)
        manager._user32 = None
        manager.start()
        self.assertTrue(errors)


class FakeUser32:
    """Scripted Win32 message queue for driving ``HotkeyManager._loop``.

    Messages are ``(message, wParam)`` pairs. With ``block=False`` an empty
    queue ends the loop like WM_QUIT; with ``block=True`` GetMessageW waits,
    as the real call does.
    """

    def __init__(self, *, fail_vks=(), block=False):
        self.messages: queue.Queue = queue.Queue()
        self.registered: dict[int, int] = {}
        self.register_calls: list[int] = []
        self.unregister_calls: list[int] = []
        self.fail_vks = set(fail_vks)
        self.block = block

    def PeekMessageW(self, *args):
        return 0

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, vk):
        self.register_calls.append(vk)
        if vk in self.fail_vks:
            return 0
        self.registered[hotkey_id] = vk
        return 1

    def UnregisterHotKey(self, hwnd, hotkey_id):
        self.unregister_calls.append(hotkey_id)
        self.registered.pop(hotkey_id, None)
        return 1

    def PostThreadMessageW(self, thread_id, message, wparam, lparam):
        self.messages.put((message, wparam))
        return 1

    def GetMessageW(self, pmsg, hwnd, low, high):
        try:
            message, wparam = (
                self.messages.get(timeout=5) if self.block else self.messages.get_nowait()
            )
        except queue.Empty:
            return 0
        if message == WM_QUIT:
            return 0
        msg = pmsg._obj
        msg.message = message
        msg.wParam = wparam
        return 1


class TestMessageLoop(unittest.TestCase):
    """The hotkey thread's message loop (#164) and startup failures (#144)."""

    def setUp(self):
        windll = MagicMock()
        windll.kernel32.GetCurrentThreadId.return_value = 4242
        patcher = patch.object(hotkeys_module.ctypes, "windll", windll, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.callbacks = {name: MagicMock() for name in ("start", "stop", "emergency", "toggle")}
        self.errors: list[str] = []

    def manager(self, user32, on_error=None, bindings=None):
        manager = HotkeyManager(self.callbacks, on_error or self.errors.append, user32=user32)
        if bindings is not None:
            manager._bindings = dict(bindings)
        return manager

    def test_start_sets_ready_and_registers_idle_actions(self):
        user32 = FakeUser32(block=True)
        manager = self.manager(user32)
        manager.start()
        self.assertTrue(manager._ready.is_set())
        self.assertEqual(sorted(user32.registered.values()), [0x75])
        manager.unregister()
        self.assertFalse(manager._thread.is_alive())
        self.assertEqual(user32.registered, {})
        self.assertIsNone(manager._thread_id)

    def test_emergency_hotkey_while_running_calls_emergency_once(self):
        user32 = FakeUser32()
        manager = self.manager(user32)
        manager._running = True
        user32.messages.put((WM_HOTKEY, 2))  # running ids: 1 stop, 2 emergency
        manager._loop()
        self.callbacks["emergency"].assert_called_once()
        self.callbacks["stop"].assert_not_called()

    def test_raising_callback_is_logged_and_next_hotkey_still_dispatches(self):
        user32 = FakeUser32()
        manager = self.manager(user32)
        manager._running = True
        self.callbacks["stop"].side_effect = RuntimeError("boom")
        user32.messages.put((WM_HOTKEY, 1))
        user32.messages.put((WM_HOTKEY, 2))
        with self.assertLogs("autoclicker.app.hotkeys", "ERROR"):
            manager._loop()
        self.callbacks["emergency"].assert_called_once()

    def test_suspend_then_apply_unregisters_everything(self):
        user32 = FakeUser32()
        manager = self.manager(user32)
        self.callbacks["start"].side_effect = lambda: manager.set_suspended(True)
        user32.messages.put((WM_HOTKEY, 1))
        registered_before_quit: list[dict] = []
        original_apply = manager._apply

        def apply_and_record():
            original_apply()
            registered_before_quit.append(dict(user32.registered))

        manager._apply = apply_and_record
        manager._loop()
        self.assertEqual(registered_before_quit[-1], {})
        self.assertEqual(user32.register_calls, [0x75])

    def test_loop_exit_unregisters_every_id_and_clears_thread_id(self):
        user32 = FakeUser32()
        manager = self.manager(user32)
        manager._running = True
        manager._loop()
        self.assertEqual(sorted(user32.unregister_calls), [1, 2])
        self.assertEqual(user32.registered, {})
        self.assertIsNone(manager._thread_id)

    def test_unparsable_binding_is_reported_and_other_keys_register(self):
        user32 = FakeUser32()
        manager = self.manager(user32, bindings={**DEFAULT_HOTKEYS, "toggle": "F8"})
        manager._bindings["start"] = "ctrl+nonsense"
        manager._apply()
        self.assertEqual(list(user32.registered.values()), [0x77])
        self.assertEqual(len(self.errors), 1)
        self.assertIn("ctrl+nonsense", self.errors[0])

    def test_on_error_raising_at_startup_keeps_the_loop_running(self):
        user32 = FakeUser32(fail_vks={0x75})
        on_error = MagicMock(side_effect=RuntimeError("main thread is not in main loop"))
        manager = self.manager(user32, on_error, bindings={**DEFAULT_HOTKEYS, "toggle": "F8"})
        user32.messages.put((WM_HOTKEY, 2))  # idle ids: 1 start (failed), 2 toggle
        with self.assertLogs("autoclicker.app.hotkeys", "ERROR"):
            manager._loop()
        on_error.assert_called_once()
        self.assertTrue(manager._ready.is_set())
        self.callbacks["toggle"].assert_called_once()

    def test_reapply_after_set_running_claims_running_keys(self):
        user32 = FakeUser32()
        manager = self.manager(user32)
        self.callbacks["start"].side_effect = lambda: manager.set_running(True)
        user32.messages.put((WM_HOTKEY, 1))
        manager._loop()
        self.assertEqual(user32.register_calls, [0x75, 0x76, 0x1B])

    def test_unregister_from_the_hotkey_thread_does_not_join_itself(self):
        user32 = FakeUser32(block=True)
        manager = self.manager(user32)
        manager._thread = threading.current_thread()
        self.callbacks["start"].side_effect = manager.unregister
        user32.messages.put((WM_HOTKEY, 1))
        manager._loop()  # would raise "cannot join current thread"
        self.callbacks["start"].assert_called_once()
        self.assertIsNone(manager._thread_id)

    def test_apply_message_constant_reaches_apply(self):
        user32 = FakeUser32()
        manager = self.manager(user32)
        user32.messages.put((WM_APP_APPLY, 0))
        manager._loop()
        self.assertEqual(user32.register_calls, [0x75, 0x75])


if __name__ == "__main__":
    unittest.main()
