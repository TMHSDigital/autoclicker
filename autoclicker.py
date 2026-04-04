#!/usr/bin/env python3
"""
Windows Autoclicker Application - Entry Point
"""

import sys

try:
    from autoclicker.main import main
    main()
except ImportError as e:
    print(f"Failed to import autoclicker package: {e}")
    print("Please ensure all dependencies are installed: pip install -r requirements.txt")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Import Error", f"Could not load autoclicker: {e}\n\nRun: pip install -r requirements.txt")
        root.destroy()
    except Exception:
        pass
    sys.exit(1)
except Exception as e:
    print(f"Application error: {e}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Application failed to start: {e}")
        root.destroy()
    except Exception:
        pass
    sys.exit(1)
