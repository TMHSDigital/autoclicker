# SPDX-License-Identifier: CC-BY-NC-4.0
"""PyAutoGUI, imported on first real use instead of at startup (#163).

Importing pyautogui pulls in pyscreeze, pygetwindow and (from source) mouseinfo,
which costs a few hundred milliseconds of every launch before the window can
appear. Modules use ``from .lazy_pyautogui import pyautogui`` and call it as
usual; the real import happens the first time an attribute is read.

Settings assigned before that (``pyautogui.FAILSAFE = ...`` while the safety
options are applied at startup) are kept and handed to the module when it
loads, so configuring it never forces the import.
"""

from __future__ import annotations

import importlib
import threading
from types import ModuleType
from typing import Any


class _LazyPyAutoGUI:
    def __init__(self) -> None:
        object.__setattr__(self, "_module", None)
        object.__setattr__(self, "_pending", {})
        object.__setattr__(self, "_lock", threading.Lock())

    def load(self) -> ModuleType:
        """Import pyautogui now (safe from any thread) and return it."""
        module: ModuleType | None = self._module
        if module is not None:
            return module
        with self._lock:
            if self._module is None:
                real = importlib.import_module("pyautogui")
                for name, value in self._pending.items():
                    setattr(real, name, value)
                self._pending.clear()
                object.__setattr__(self, "_module", real)
                return real
            loaded: ModuleType = self._module
            return loaded

    @property
    def loaded(self) -> bool:
        return self._module is not None

    def __getattr__(self, name: str) -> Any:
        pending = object.__getattribute__(self, "_pending")
        if name in pending and self._module is None:
            return pending[name]
        return getattr(self.load(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        with self._lock:
            if self._module is None:
                self._pending[name] = value
                return
        setattr(self._module, name, value)


pyautogui: Any = _LazyPyAutoGUI()
