# SPDX-License-Identifier: CC-BY-NC-4.0
"""Record a click sequence by watching real mouse clicks (#86).

A low-level mouse hook (WH_MOUSE_LL) is installed only while recording and is
always removed when recording stops, so the app never runs a system-wide hook
otherwise. Only button presses are recorded: position, button and time. No
keystrokes, nothing leaves the machine.
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)

WH_MOUSE_LL = 14
WM_QUIT = 0x0012
_BUTTONS = {0x0201: "left", 0x0204: "right", 0x0207: "middle"}  # WM_*BUTTONDOWN

# Gaps are rounded to this many milliseconds and capped at the longest step wait.
ROUND_MS = 50
MAX_WAIT_MS = 60_000
# Two presses of the same button within this distance merge into a double click.
DOUBLE_CLICK_PIXELS = 4


@dataclass(frozen=True)
class RecordedClick:
    x: int
    y: int
    button: str
    time: float  # time.monotonic() seconds


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


def double_click_seconds() -> float:
    try:
        millis = int(ctypes.windll.user32.GetDoubleClickTime())  # type: ignore[attr-defined, unused-ignore]
        return millis / 1000
    except Exception:
        return 0.5


def clicks_to_steps(
    clicks: list[RecordedClick], *, double_click_window: float | None = None
) -> list[dict[str, Any]]:
    """Turn recorded presses into sequence steps.

    Each step's wait is the gap to the next click (rounded to ROUND_MS, capped
    at MAX_WAIT_MS); the last step waits 0 because the Interval follows it.
    """
    window = double_click_seconds() if double_click_window is None else double_click_window
    merged: list[tuple[RecordedClick, str]] = []
    for click in clicks:
        if merged:
            last, kind = merged[-1]
            if (
                kind == "single"
                and click.button == last.button
                and click.time - last.time <= window
                and abs(click.x - last.x) <= DOUBLE_CLICK_PIXELS
                and abs(click.y - last.y) <= DOUBLE_CLICK_PIXELS
            ):
                merged[-1] = (last, "double")
                continue
        merged.append((click, "single"))

    steps = []
    for index, (click, kind) in enumerate(merged):
        if index + 1 < len(merged):
            gap_ms = (merged[index + 1][0].time - click.time) * 1000
            delay = min(MAX_WAIT_MS, round(gap_ms / ROUND_MS) * ROUND_MS)
        else:
            delay = 0
        steps.append(
            {
                "x": click.x,
                "y": click.y,
                "button": click.button,
                "click_type": kind,
                "delay_ms": delay,
            }
        )
    return steps


class ClickRecorder:
    """Owns the hook thread while recording."""

    def __init__(self, on_click: Callable[[RecordedClick], None], *, user32: Any = None) -> None:
        self._on_click = on_click
        self._user32 = user32
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._hooked = False
        self._proc: Any = None  # keep the ctypes callback alive while hooked

    @property
    def recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Install the hook on its own thread. False if it couldn't be installed."""
        if self.recording:
            return True
        if self._user32 is None:
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return False
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined, unused-ignore]
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ClickRecorder")
        self._thread.start()
        self._ready.wait(timeout=2.0)
        return self._hooked

    def stop(self) -> None:
        """Remove the hook and end the thread (safe to call more than once)."""
        thread = self._thread
        if thread is None:
            return
        if self._thread_id is not None:
            self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        user32 = self._user32
        hook_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
        ]  # fmt: skip
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, hook_proc_type, ctypes.c_void_p, wintypes.DWORD,
        ]  # fmt: skip
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]

        def proc(code: int, wparam: int, lparam: int) -> int:
            if code == 0 and wparam in _BUTTONS:
                info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                try:
                    self._on_click(
                        RecordedClick(
                            int(info.pt.x), int(info.pt.y), _BUTTONS[wparam], time.monotonic()
                        )
                    )
                except Exception:
                    _log.exception("Recording callback failed")
            return int(user32.CallNextHookEx(None, code, wparam, lparam))

        self._proc = hook_proc_type(proc)
        self._thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())  # type: ignore[attr-defined, unused-ignore]
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        self._hooked = bool(hook)
        self._ready.set()
        if not hook:
            _log.warning("Could not install the recording hook")
            return
        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user32.UnhookWindowsHookEx(hook)
            self._hooked = False
            self._thread_id = None
            self._proc = None
