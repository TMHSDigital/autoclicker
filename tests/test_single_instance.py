"""Single running instance (#50)."""

import threading
import unittest
from unittest.mock import MagicMock

from autoclicker.core.single_instance import (
    ERROR_ALREADY_EXISTS,
    MUTEX_NAME,
    SHOW_EVENT_NAME,
    SingleInstance,
)


class TestSingleInstance(unittest.TestCase):
    def test_first_instance_acquires_and_creates_show_event(self):
        k32 = MagicMock()
        guard = SingleInstance(kernel32=k32, last_error=lambda: 0)
        self.assertTrue(guard.acquire())
        k32.CreateMutexW.assert_called_once_with(None, False, MUTEX_NAME)
        k32.CreateEventW.assert_called_once_with(None, False, False, SHOW_EVENT_NAME)

    def test_second_instance_is_refused(self):
        k32 = MagicMock()
        guard = SingleInstance(kernel32=k32, last_error=lambda: ERROR_ALREADY_EXISTS)
        self.assertFalse(guard.acquire())
        k32.CreateEventW.assert_not_called()

    def test_signal_existing_sets_event(self):
        k32 = MagicMock()
        k32.OpenEventW.return_value = 99
        k32.SetEvent.return_value = 1
        self.assertTrue(SingleInstance(kernel32=k32).signal_existing())
        k32.SetEvent.assert_called_once_with(99)
        k32.CloseHandle.assert_called_once_with(99)

    def test_unavailable_never_blocks_startup(self):
        guard = SingleInstance(kernel32=None)
        guard._kernel32 = None
        self.assertTrue(guard.acquire())
        self.assertFalse(guard.signal_existing())

    def test_watch_calls_on_show_per_signal(self):
        k32 = MagicMock()
        k32.WaitForSingleObject.side_effect = [0, 0, 1]  # two signals, then stop
        guard = SingleInstance(kernel32=k32, last_error=lambda: 0)
        guard.acquire()
        shown = threading.Event()
        calls = []

        def on_show():
            calls.append(1)
            if len(calls) == 2:
                shown.set()

        guard.watch(on_show)
        self.assertTrue(shown.wait(timeout=2.0))
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
