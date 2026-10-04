# SPDX-License-Identifier: CC-BY-NC-4.0
"""Allow one running instance per user session.

Two instances would each register the hotkeys and click the same target,
doubling the click rate while each runaway guard only sees half of it.

The first instance owns a named mutex and waits on a named "show" event. A
second launch finds the mutex, sets the event so the running window comes to
the front (even when it is hidden in the tray), and exits.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable
from typing import Any

_log = logging.getLogger(__name__)

_NAME = "TMHSDigital.WindowsAutoclicker"
MUTEX_NAME = f"Local\\{_NAME}.Instance"
SHOW_EVENT_NAME = f"Local\\{_NAME}.Show"

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0


def _load_kernel32() -> Any:
    if not hasattr(ctypes, "WinDLL"):
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined, unused-ignore]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.OpenEventW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.SetEvent.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    return kernel32


def _last_error() -> int:
    get = getattr(ctypes, "get_last_error", None)
    return int(get()) if get else 0


class SingleInstance:
    """Named-mutex guard plus a 'show yourself' signal for the running instance."""

    def __init__(self, *, kernel32: Any = None, last_error: Callable[[], int] = _last_error):
        self._kernel32 = kernel32 if kernel32 is not None else _load_kernel32()
        self._last_error = last_error
        self._mutex: Any = None
        self._show_event: Any = None

    def acquire(self) -> bool:
        """True if this is the only instance (or the check is unavailable)."""
        if self._kernel32 is None:
            return True
        try:
            self._mutex = self._kernel32.CreateMutexW(None, False, MUTEX_NAME)
            if not self._mutex:
                return True  # cannot tell; do not block startup
            if self._last_error() == ERROR_ALREADY_EXISTS:
                return False
            # Auto-reset event the running instance waits on.
            self._show_event = self._kernel32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
            return True
        except Exception:
            _log.exception("Single-instance check failed")
            return True

    def signal_existing(self) -> bool:
        """Ask the running instance to show its window. Returns True if signalled."""
        if self._kernel32 is None:
            return False
        handle = self._kernel32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT_NAME)
        if not handle:
            return False
        try:
            return bool(self._kernel32.SetEvent(handle))
        finally:
            self._kernel32.CloseHandle(handle)

    def watch(self, on_show: Callable[[], None]) -> None:
        """Call ``on_show`` (from a daemon thread) whenever another launch signals."""
        if self._kernel32 is None or not self._show_event:
            return

        def loop() -> None:
            while True:
                result = self._kernel32.WaitForSingleObject(self._show_event, INFINITE)
                if result != WAIT_OBJECT_0:
                    return
                try:
                    on_show()
                except Exception:
                    _log.exception("Show-window request failed")

        threading.Thread(target=loop, daemon=True, name="SingleInstanceWatch").start()
