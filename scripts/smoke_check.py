#!/usr/bin/env python3
"""
Smoke check for autoclicker runtime dependencies and project layout.
Not collected by pytest; run manually: python scripts/smoke_check.py
"""

import os
import sys

# Repo root (parent of scripts/)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")


def check_imports() -> bool:
    """Verify required modules can be imported."""
    print("Testing imports...")
    passed = True

    try:
        import tkinter  # noqa: F401

        _ok("tkinter available")
    except ImportError as exc:
        _fail(f"tkinter import failed: {exc}")
        passed = False

    try:
        import pyautogui  # noqa: F401

        _ok("pyautogui available")
    except ImportError as exc:
        _fail(f"pyautogui import failed: {exc}")
        passed = False

    try:
        import mouse

        _ok("mouse available")
        methods = [m for m in dir(mouse) if not m.startswith("_")]
        print(f"  Available methods: {methods}")
    except ImportError as exc:
        _fail(f"mouse import failed: {exc}")
        passed = False

    try:
        import keyboard  # noqa: F401

        _ok("keyboard available")
    except ImportError as exc:
        _fail(f"keyboard import failed: {exc}")
        passed = False

    try:
        import pystray  # noqa: F401

        _ok("pystray available")
    except ImportError as exc:
        _fail(f"pystray import failed: {exc}")
        passed = False

    try:
        from PIL import Image  # noqa: F401

        _ok("PIL available")
    except ImportError as exc:
        _fail(f"PIL import failed: {exc}")
        passed = False

    return passed


def check_mouse_functionality() -> bool:
    """Verify basic mouse and screen queries."""
    print("\nTesting mouse functionality...")
    try:
        import mouse
        import pyautogui

        x, y = mouse.get_position()
        _ok(f"Current mouse position: ({x}, {y})")

        screen_width, screen_height = pyautogui.size()
        _ok(f"Screen size: {screen_width}x{screen_height}")
        return True
    except Exception as exc:
        _fail(f"Mouse functionality check failed: {exc}")
        return False


def check_file_structure() -> bool:
    """Verify required project files exist at repo root."""
    print("\nTesting file structure...")
    os.chdir(_REPO_ROOT)
    required_files = [
        "autoclicker.py",
        "requirements.txt",
        "README.md",
        "autoclicker.ico",
        "run_autoclicker.bat",
    ]
    passed = True
    for name in required_files:
        if os.path.exists(name):
            _ok(f"{name} exists")
        else:
            _fail(f"{name} missing")
            passed = False
    return passed


def main() -> bool:
    """Run all smoke checks."""
    print("Autoclicker smoke check")
    print("=" * 40)

    all_passed = check_imports() and check_mouse_functionality() and check_file_structure()

    print("\n" + "=" * 40)
    if all_passed:
        print("All checks passed. The autoclicker should work correctly.")
        print("\nTo run the application:")
        print("1. Double-click run_autoclicker.bat")
        print("2. Or: autoclicker_env\\Scripts\\activate && python autoclicker.py")
    else:
        print("Some checks failed. See messages above.")

    return all_passed


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
