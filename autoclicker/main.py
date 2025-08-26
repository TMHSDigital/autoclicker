#!/usr/bin/env python3
"""
Windows Autoclicker Application - Modular Entry Point
A professional autoclicker with advanced automation capabilities and safety features.
"""

import sys
import tkinter as tk
from tkinter import messagebox

from .gui.main_window import AutoclickerApp


def main():
    """Main function"""
    try:
        app = AutoclickerApp()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")
        # Try to show error dialog if tkinter is available
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", f"Application failed to start: {e}")
            root.destroy()
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
