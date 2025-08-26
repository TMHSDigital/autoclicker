#!/usr/bin/env python3
"""
Windows Autoclicker Application - Entry Point
A professional autoclicker with advanced automation capabilities and safety features.

This is a wrapper script that launches the modular autoclicker application.
"""

import sys
import os

# Add current directory to path so we can import autoclicker package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from autoclicker.main import main
    main()
except ImportError as e:
    print(f"Failed to import modular autoclicker: {e}")
    print("Please ensure the autoclicker package is properly installed.")
    import tkinter as tk
    from tkinter import messagebox
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Import Error", f"Could not load modular autoclicker: {e}\n\nPlease ensure all files are properly installed.")
        root.destroy()
    except:
        pass
    sys.exit(1)
except Exception as e:
    print(f"Application error: {e}")
    import tkinter as tk
    from tkinter import messagebox
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Application failed to start: {e}")
        root.destroy()
    except:
        pass
    sys.exit(1)
