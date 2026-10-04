# SPDX-License-Identifier: CC-BY-NC-4.0
"""Global hotkeys via Win32 RegisterHotKey.

RegisterHotKey needs no system-wide keyboard hook. A registered key is
delivered only to this app, so keys are claimed by state: the Start key while
idle, the Stop and Emergency keys only while clicking. That way Esc still
works in other programs whenever the autoclicker is not running.

Registration and the message loop live on one daemon thread (Win32 requires
both on the same thread); other threads talk to it by posting messages.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable, Iterable
from ctypes import wintypes
from typing import Any

_log = logging.getLogger(__name__)

ACTIONS = ("start", "stop", "emergency", "toggle")
DEFAULT_HOTKEYS = {"start": "F6", "stop": "F7", "emergency": "Esc", "toggle": ""}
# Actions whose keys are claimed in each state.
_IDLE_ACTIONS = ("start", "toggle")
_RUNNING_ACTIONS = ("stop", "emergency", "toggle")

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP_APPLY = 0x8000 + 1

_MODIFIERS = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}
_MODIFIER_ORDER = (("Ctrl", MOD_CONTROL), ("Alt", MOD_ALT), ("Shift", MOD_SHIFT), ("Win", MOD_WIN))

_NAMED_KEYS = {
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "insert": 0x2D,
    "delete": 0x2E,
    "pause": 0x13,
    "scrolllock": 0x91,
}
_CANONICAL_NAMES = {
    0x1B: "Esc",
    0x20: "Space",
    0x21: "PageUp",
    0x22: "PageDown",
    0x23: "End",
    0x24: "Home",
    0x2D: "Insert",
    0x2E: "Delete",
    0x13: "Pause",
    0x91: "ScrollLock",
}


class HotkeyError(ValueError):
    """A hotkey string could not be parsed."""


def parse_hotkey(text: str) -> tuple[int, int]:
    """Parse e.g. ``"Ctrl+Shift+F6"`` into ``(modifiers, virtual_key)``."""
    parts = [p.strip() for p in str(text).split("+") if p.strip()]
    if not parts:
        raise HotkeyError("Empty hotkey")
    modifiers = 0
    for part in parts[:-1]:
        flag = _MODIFIERS.get(part.lower())
        if flag is None:
            raise HotkeyError(f"Unknown modifier: {part}")
        modifiers |= flag
    key = parts[-1].lower()
    if key in _MODIFIERS:
        raise HotkeyError("A hotkey needs a key besides modifiers")
    if key in _NAMED_KEYS:
        return modifiers, _NAMED_KEYS[key]
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return modifiers, 0x70 + int(key[1:]) - 1
    if len(key) == 1 and key.isascii() and key.isalnum():
        if modifiers == 0:
            raise HotkeyError("Letter and digit keys need Ctrl, Alt, Shift or Win")
        return modifiers, ord(key.upper())
    raise HotkeyError(f"Unsupported key: {parts[-1]}")


def format_hotkey(modifiers: int, vk: int) -> str:
    """Canonical display form, e.g. ``"Ctrl+Shift+F6"``."""
    names = [name for name, flag in _MODIFIER_ORDER if modifiers & flag]
    if 0x70 <= vk <= 0x87:
        key = f"F{vk - 0x70 + 1}"
    else:
        key = _CANONICAL_NAMES.get(vk, chr(vk))
    return "+".join([*names, key])


def normalize_hotkey(text: str) -> str:
    """Return the canonical form of a hotkey string (raises HotkeyError)."""
    return format_hotkey(*parse_hotkey(text))


def validate_bindings(bindings: dict[str, str]) -> dict[str, str]:
    """Normalize bindings; empty means unbound. Raises HotkeyError on bad or duplicate keys."""
    result: dict[str, str] = {}
    seen: dict[str, str] = {}
    for action in ACTIONS:
        text = str(bindings.get(action, "") or "").strip()
        if not text:
            result[action] = ""
            continue
        key = normalize_hotkey(text)
        if key in seen:
            raise HotkeyError(f"{key} is assigned to both {seen[key]} and {action}")
        seen[key] = action
        result[action] = key
    if not result["start"] and not result["toggle"]:
        raise HotkeyError("Set a Start key or a Toggle key")
    if not result["emergency"]:
        raise HotkeyError("The Emergency stop key cannot be empty")
    return result


class HotkeyManager:
    """Owns the hotkey thread and claims keys according to the running state."""

    def __init__(
        self,
        callbacks: dict[str, Callable[[], None]],
        on_error: Callable[[str], None],
        *,
        user32: Any = None,
    ) -> None:
        self._callbacks = callbacks
        self._on_error = on_error
        self._user32 = user32 if user32 is not None else _load_user32()
        self._bindings = dict(DEFAULT_HOTKEYS)
        self._running = False
        self._suspended = False
        self._registered: dict[int, str] = {}  # hotkey id -> action
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    # -- public API (any thread) -------------------------------------------

    @property
    def bindings(self) -> dict[str, str]:
        return dict(self._bindings)

    def start(self, bindings: dict[str, str] | None = None) -> None:
        if bindings is not None:
            self._bindings = dict(bindings)
        if self._user32 is None:
            self._on_error("Global hotkeys are unavailable on this system")
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="Hotkeys")
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def set_bindings(self, bindings: dict[str, str]) -> None:
        """Change the keys (already validated) and re-register."""
        self._bindings = dict(bindings)
        self._post(WM_APP_APPLY)

    def set_running(self, running: bool) -> None:
        """Claim Stop/Emergency keys while clicking, Start key while idle."""
        if running != self._running:
            self._running = running
            self._post(WM_APP_APPLY)

    def set_suspended(self, suspended: bool) -> None:
        """Release every key (e.g. while the user is typing a new binding)."""
        if suspended != self._suspended:
            self._suspended = suspended
            self._post(WM_APP_APPLY)

    def unregister(self) -> None:
        """Release all keys and end the hotkey thread."""
        self._post(WM_QUIT)
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)

    def desired_actions(self) -> tuple[str, ...]:
        if self._suspended:
            return ()
        names = _RUNNING_ACTIONS if self._running else _IDLE_ACTIONS
        return tuple(a for a in names if self._bindings.get(a))

    # -- hotkey thread -----------------------------------------------------

    def _post(self, message: int) -> None:
        if self._thread_id is not None and self._user32 is not None:
            self._user32.PostThreadMessageW(self._thread_id, message, 0, 0)

    def _apply(self) -> None:
        """(Hotkey thread) unregister everything, then register the desired set."""
        with self._lock:
            for hotkey_id in list(self._registered):
                self._user32.UnregisterHotKey(None, hotkey_id)
            self._registered.clear()
            failed: list[str] = []
            for index, action in enumerate(self.desired_actions(), start=1):
                key = self._bindings[action]
                try:
                    modifiers, vk = parse_hotkey(key)
                except HotkeyError:
                    failed.append(key)
                    continue
                if self._user32.RegisterHotKey(None, index, modifiers | MOD_NOREPEAT, vk):
                    self._registered[index] = action
                else:
                    failed.append(key)
        if failed:
            self._on_error(f"Hotkey unavailable (used by another program?): {', '.join(failed)}")

    def _dispatch(self, hotkey_id: int) -> None:
        action = self._registered.get(hotkey_id)
        callback = self._callbacks.get(action) if action else None
        if callback is not None:
            try:
                callback()
            except Exception:
                _log.exception("Hotkey callback failed")

    def _loop(self) -> None:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined, unused-ignore]
        self._thread_id = int(kernel32.GetCurrentThreadId())
        msg = wintypes.MSG()
        # Create this thread's message queue before anyone posts to it.
        self._user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self._apply()
        self._ready.set()
        try:
            while self._user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self._dispatch(int(msg.wParam))
                elif msg.message == WM_APP_APPLY:
                    self._apply()
        finally:
            with self._lock:
                for hotkey_id in list(self._registered):
                    self._user32.UnregisterHotKey(None, hotkey_id)
                self._registered.clear()
            self._thread_id = None


def _load_user32() -> Any:
    windll = getattr(ctypes, "windll", None)
    return windll.user32 if windll is not None else None


def callbacks_for(
    start: Callable[[], None],
    stop: Callable[[], None],
    emergency: Callable[[], None],
    toggle: Callable[[], None],
) -> dict[str, Callable[[], None]]:
    return {"start": start, "stop": stop, "emergency": emergency, "toggle": toggle}


def describe(bindings: dict[str, str], actions: Iterable[str]) -> str:
    """Comma-separated bound keys for the given actions (for labels/logs)."""
    return ", ".join(bindings[a] for a in actions if bindings.get(a))
