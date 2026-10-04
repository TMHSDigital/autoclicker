# SPDX-License-Identifier: CC-BY-NC-4.0
"""Dialog for rebinding the global hotkeys."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from ..app.hotkeys import ACTIONS, HotkeyError, normalize_hotkey, validate_bindings

ACTION_LABELS = {
    "start": "Start",
    "stop": "Stop",
    "emergency": "Emergency stop",
    "toggle": "Start/stop toggle",
}

# Tk modifier bits in event.state on Windows.
_TK_SHIFT = 0x0001
_TK_CONTROL = 0x0004
_TK_ALT = 0x20000

_MODIFIER_KEYSYMS = {
    "Shift_L",
    "Shift_R",
    "Control_L",
    "Control_R",
    "Alt_L",
    "Alt_R",
    "Win_L",
    "Win_R",
    "Caps_Lock",
    "Num_Lock",
}
_KEYSYM_NAMES = {
    "Escape": "Esc",
    "Prior": "PageUp",
    "Next": "PageDown",
    "space": "Space",
    "Scroll_Lock": "ScrollLock",
}


def hotkey_from_event(keysym: str, state: int) -> str | None:
    """Turn a Tk key event into a canonical hotkey string.

    Returns None for a bare modifier press (keep waiting for the real key) and
    raises HotkeyError for keys the hotkey system cannot register.
    """
    if keysym in _MODIFIER_KEYSYMS:
        return None
    key = _KEYSYM_NAMES.get(keysym, keysym)
    if len(key) == 1:
        key = key.upper()
    parts = []
    if state & _TK_CONTROL:
        parts.append("Ctrl")
    if state & _TK_ALT:
        parts.append("Alt")
    if state & _TK_SHIFT:
        parts.append("Shift")
    return normalize_hotkey("+".join([*parts, key]))


class HotkeysDialog:
    """Modal dialog: press a key combination in a field to bind it."""

    def __init__(
        self,
        parent: Any,
        bindings: dict[str, str],
        on_save: Callable[[dict[str, str]], None],
        on_close: Callable[[], None],
    ) -> None:
        self._on_save = on_save
        self._on_close = on_close
        self._values = dict(bindings)
        self.window = tk.Toplevel(parent)
        self.window.title("Hotkeys")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        body = ttk.Frame(self.window, padding=16)
        body.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            body,
            text="Click a field and press the key combination. Backspace clears.",
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        self._vars: dict[str, tk.StringVar] = {}
        for row, action in enumerate(ACTIONS, start=1):
            ttk.Label(body, text=ACTION_LABELS[action] + ":").grid(
                row=row, column=0, sticky=tk.W, pady=4, padx=(0, 12)
            )
            var = tk.StringVar(value=self._values.get(action, "") or "")
            self._vars[action] = var
            entry = ttk.Entry(body, textvariable=var, width=22)
            entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=4)
            entry.bind("<KeyPress>", self._capture_handler(action))

        self._error = tk.StringVar()
        ttk.Label(body, textvariable=self._error, foreground="#cf222e").grid(
            row=len(ACTIONS) + 1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0)
        )
        ttk.Label(
            body,
            text="Stop and Emergency keys are only claimed while clicking.",
            foreground="#8b949e",
        ).grid(row=len(ACTIONS) + 2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))

        buttons = ttk.Frame(body)
        buttons.grid(row=len(ACTIONS) + 3, column=0, columnspan=2, sticky=tk.E, pady=(14, 0))
        ttk.Button(buttons, text="Defaults", command=self._defaults).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=self.close).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        self.window.grab_set()

    def _capture_handler(self, action: str) -> Callable[[Any], str]:
        def handler(event: Any) -> str:
            return self._capture(action, event)

        return handler

    def _capture(self, action: str, event: Any) -> str:
        if event.keysym in ("BackSpace", "Delete") and not event.state & (_TK_CONTROL | _TK_ALT):
            self._vars[action].set("")
            self._error.set("")
            return "break"
        if event.keysym == "Tab":
            return ""  # let focus move between fields
        try:
            key = hotkey_from_event(event.keysym, int(event.state))
        except HotkeyError as exc:
            self._error.set(str(exc))
            return "break"
        if key is not None:
            self._vars[action].set(key)
            self._error.set("")
        return "break"

    def _defaults(self) -> None:
        from ..app.hotkeys import DEFAULT_HOTKEYS

        for action, var in self._vars.items():
            var.set(DEFAULT_HOTKEYS[action])
        self._error.set("")

    def _save(self) -> None:
        try:
            bindings = validate_bindings({a: v.get() for a, v in self._vars.items()})
        except HotkeyError as exc:
            self._error.set(str(exc))
            return
        self._on_save(bindings)
        self.close()

    def close(self) -> None:
        try:
            self.window.grab_release()
            self.window.destroy()
        finally:
            self._on_close()
