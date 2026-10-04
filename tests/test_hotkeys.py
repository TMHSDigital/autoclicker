"""RegisterHotKey-based hotkeys (#57) and configurable bindings (#47)."""

import unittest
from unittest.mock import MagicMock

from autoclicker.app.hotkeys import (
    DEFAULT_HOTKEYS,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
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


if __name__ == "__main__":
    unittest.main()
