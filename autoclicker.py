#!/usr/bin/env python3
"""
Windows Autoclicker Application - Entry Point
"""

import contextlib
import sys


def _show_error(title: str, text: str) -> None:
    """Best effort: the windowed exe has no console, so also try a dialog."""
    with contextlib.suppress(Exception):
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, text)
        root.destroy()


def run() -> int:
    try:
        from autoclicker.main import main
    except ImportError as e:
        print(f"Failed to import autoclicker package: {e}")
        print("Please ensure all dependencies are installed: pip install -r requirements.txt")
        _show_error(
            "Import Error",
            f"Could not load autoclicker: {e}\n\nRun: pip install -r requirements.txt",
        )
        return 1
    try:
        return main()
    except Exception as e:
        print(f"Application error: {e}")
        _show_error("Error", f"Application failed to start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run())
