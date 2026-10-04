#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Windows Autoclicker Application - Modular Entry Point
"""

import logging
import sys
import tkinter as tk
from tkinter import messagebox

from .core.logging_setup import configure_logging
from .core.single_instance import SingleInstance
from .gui.main_window import AutoclickerApp


def main():
    """Main function"""
    configure_logging()
    instance = SingleInstance()
    if not instance.acquire():
        # Already running: bring that window to the front instead of starting
        # a second clicker with its own hotkeys.
        instance.signal_existing()
        return
    try:
        app = AutoclickerApp()
        instance.watch(lambda: app._ui(app.show_window))
        app.run()
    except Exception as e:
        logging.getLogger("autoclicker").exception("Application error")
        # Try to show error dialog if tkinter is available
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", f"Application failed to start: {e}")
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
