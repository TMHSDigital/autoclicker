#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Windows Autoclicker Application - Modular Entry Point
"""

import argparse
import contextlib
import io
import logging
import sys
import tkinter as tk
from tkinter import messagebox

from .core.dpi import enable_per_monitor_dpi_awareness

# Before anything imports PyAutoGUI, which locks in weaker system-aware DPI
# handling on import (see core/dpi.py).
enable_per_monitor_dpi_awareness()

from .cli import (  # noqa: E402
    UsageError,
    build_overrides,
    build_parser,
    has_overrides,
    run_headless,
)
from .core.logging_setup import configure_logging  # noqa: E402
from .core.single_instance import SingleInstance  # noqa: E402
from .gui.main_window import AutoclickerApp  # noqa: E402


def _show_dialog(title: str, text: str, *, error: bool) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, text)
        root.destroy()
    except Exception:
        pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse flags. The windowed exe has no console, so --help and errors go to a dialog."""
    parser = build_parser()
    if sys.stdout is not None:
        return parser.parse_args(argv)
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            return parser.parse_args(argv)
    except SystemExit as exit_:
        _show_dialog("Windows Autoclicker", captured.getvalue(), error=bool(exit_.code))
        raise


def main(argv: list[str] | None = None) -> int:
    """Run the app (or a headless run). Returns the process exit code."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    configure_logging()
    if args.headless:
        return run_headless(args)

    instance = SingleInstance()
    if not instance.acquire():
        # Already running: bring that window to the front instead of starting
        # a second clicker with its own hotkeys.
        instance.signal_existing()
        if has_overrides(args) or args.start or args.minimized:
            print(
                "Already running: brought it to the front; options were ignored.", file=sys.stderr
            )
        return 0
    try:
        app = AutoclickerApp()
        instance.watch(lambda: app._ui(app.show_window))
        _apply_launch_options(app, args)
        app.run()
    except Exception as e:
        logging.getLogger("autoclicker").exception("Application error")
        _show_dialog("Error", f"Application failed to start: {e}", error=True)
        return 1
    return 0


def _apply_launch_options(app: AutoclickerApp, args: argparse.Namespace) -> None:
    """Fill the form from flags, then hide to the tray and/or press Start."""
    if has_overrides(args):
        try:
            overrides = build_overrides(args, app.preset_manager.load_profile)
        except UsageError as e:
            app._set_status_message(f"Command line: {e}", "error")
            return
        app.apply_form_values(overrides)
    if args.minimized:
        app.root.after(0, app.hide_to_tray)
    if args.start:
        app.root.after(0, app.start_from_button)


if __name__ == "__main__":
    sys.exit(main())
