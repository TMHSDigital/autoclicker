"""Failure and shutdown paths of the single-instance guard (#166)."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock

from autoclicker.core.single_instance import WAIT_OBJECT_0, SingleInstance

_LOGGER = "autoclicker.core.single_instance"


def _start_watch(guard: SingleInstance, on_show) -> threading.Thread:
    """Start ``guard.watch`` and return the watcher thread it created."""
    before = set(threading.enumerate())
    guard.watch(on_show)
    started = [
        t for t in threading.enumerate() if t not in before and t.name == "SingleInstanceWatch"
    ]
    if started:
        return started[0]
    # It already finished; hand back a finished thread so callers can join it.
    done = threading.Thread(target=lambda: None)
    done.start()
    return done


class TestAcquireFailures(unittest.TestCase):
    def test_null_mutex_does_not_block_startup(self):
        k32 = MagicMock()
        k32.CreateMutexW.return_value = None
        guard = SingleInstance(kernel32=k32, last_error=lambda: 0)
        self.assertTrue(guard.acquire())
        k32.CreateEventW.assert_not_called()

    def test_create_mutex_raising_does_not_block_startup(self):
        k32 = MagicMock()
        k32.CreateMutexW.side_effect = OSError("denied")
        guard = SingleInstance(kernel32=k32, last_error=lambda: 0)
        with self.assertLogs(_LOGGER, "ERROR"):
            self.assertTrue(guard.acquire())


class TestSignalExisting(unittest.TestCase):
    def test_no_event_returns_false(self):
        k32 = MagicMock()
        k32.OpenEventW.return_value = None
        self.assertFalse(SingleInstance(kernel32=k32).signal_existing())
        k32.SetEvent.assert_not_called()
        k32.CloseHandle.assert_not_called()

    def test_closes_handle_even_when_set_event_fails(self):
        k32 = MagicMock()
        k32.OpenEventW.return_value = 7
        k32.SetEvent.return_value = 0
        self.assertFalse(SingleInstance(kernel32=k32).signal_existing())
        k32.CloseHandle.assert_called_once_with(7)


class TestWatchLoop(unittest.TestCase):
    def _guard(self, results) -> tuple[SingleInstance, MagicMock]:
        k32 = MagicMock()
        k32.WaitForSingleObject.side_effect = list(results)
        guard = SingleInstance(kernel32=k32, last_error=lambda: 0)
        self.assertTrue(guard.acquire())
        return guard, k32

    def test_no_show_event_starts_nothing(self):
        k32 = MagicMock()
        guard = SingleInstance(kernel32=k32, last_error=lambda: 0)  # never acquired
        on_show = MagicMock()
        guard.watch(on_show)
        k32.WaitForSingleObject.assert_not_called()
        on_show.assert_not_called()

    def test_calls_on_show_per_signal_and_exits_on_other_result(self):
        guard, k32 = self._guard([WAIT_OBJECT_0, WAIT_OBJECT_0, WAIT_OBJECT_0, 0xFFFFFFFF])
        on_show = MagicMock()
        thread = _start_watch(guard, on_show)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(on_show.call_count, 3)
        self.assertEqual(k32.WaitForSingleObject.call_count, 4)

    def test_survives_on_show_raising(self):
        guard, k32 = self._guard([WAIT_OBJECT_0, WAIT_OBJECT_0, 0x102])  # 0x102: WAIT_TIMEOUT
        on_show = MagicMock(side_effect=[RuntimeError("window gone"), None])
        with self.assertLogs(_LOGGER, "ERROR"):
            thread = _start_watch(guard, on_show)
            thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(on_show.call_count, 2)
        self.assertEqual(k32.WaitForSingleObject.call_count, 3)


if __name__ == "__main__":
    unittest.main()
