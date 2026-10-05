# SPDX-License-Identifier: CC-BY-NC-4.0
"""Tk standard dialogs, reached through one module so tests can patch them in one place."""

from tkinter import filedialog, messagebox, simpledialog

__all__ = ["filedialog", "messagebox", "simpledialog"]
