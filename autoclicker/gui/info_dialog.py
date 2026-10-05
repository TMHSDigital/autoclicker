# SPDX-License-Identifier: CC-BY-NC-4.0
"""About / Info dialog: version, responsible-use note, diagnostics and support links."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from ..core.resources import resource_path

SPONSOR_URL = "https://github.com/sponsors/TMHSDigital"
ISSUES_URL = "https://github.com/TMHSDigital/autoclicker/issues/new/choose"

ABOUT_TEXT = (
    "Windows Autoclicker {version}\n\n"
    "For legitimate automation only. Make sure you comply with the terms of "
    "service of the software you automate, website policies and local laws. "
    "The author assumes no responsibility for misuse.\n\n"
    "Free for non-commercial use (CC BY-NC 4.0). If it saves you time, "
    "sponsoring helps keep it maintained and pays for signed releases."
)


def _use_app_icon(window: Any) -> None:
    try:
        icon = resource_path("autoclicker.ico")
        if icon.is_file():
            window.iconbitmap(str(icon))
    except Exception:
        pass


class InfoDialog:
    """Small modal-less window; Copy diagnostics previews the text before copying."""

    def __init__(self, root: Any, version: str, diagnostics: Callable[[], str]) -> None:
        self._root = root
        self._diagnostics = diagnostics
        self.window = tk.Toplevel(root)
        self.window.title("About Windows Autoclicker")
        _use_app_icon(self.window)
        self.window.transient(root)
        self.window.resizable(False, False)
        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame, text=ABOUT_TEXT.format(version=version), wraplength=380, justify=tk.LEFT
        ).pack(anchor=tk.W)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor=tk.E, pady=(14, 0))
        ttk.Button(buttons, text="Copy diagnostics…", command=self.show_diagnostics).pack(
            side=tk.LEFT
        )
        ttk.Button(buttons, text="Sponsor", command=lambda: webbrowser.open(SPONSOR_URL)).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(buttons, text="Close", command=self.window.destroy).pack(
            side=tk.LEFT, padx=(6, 0)
        )

    def show_diagnostics(self) -> None:
        """Show exactly what would be copied, with a Copy button."""
        report = self._diagnostics()
        preview = tk.Toplevel(self.window)
        preview.title("Diagnostics")
        _use_app_icon(preview)
        preview.transient(self.window)
        frame = ttk.Frame(preview, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="This is everything that will be copied. Paste it into your bug report.",
        ).pack(anchor=tk.W, pady=(0, 6))
        text = tk.Text(frame, width=90, height=24, wrap=tk.NONE)
        text.insert("1.0", report)
        text.configure(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor=tk.E, pady=(8, 0))

        def copy() -> None:
            self.copy_to_clipboard(report)
            preview.destroy()

        ttk.Button(buttons, text="Copy", command=copy).pack(side=tk.LEFT)
        ttk.Button(
            buttons, text="Open a bug report", command=lambda: webbrowser.open(ISSUES_URL)
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(buttons, text="Close", command=preview.destroy).pack(side=tk.LEFT, padx=(6, 0))

    def copy_to_clipboard(self, report: str) -> None:
        self._root.clipboard_clear()
        self._root.clipboard_append(report)
