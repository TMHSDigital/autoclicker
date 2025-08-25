#!/usr/bin/env python3
"""
Test script for the autoclicker functionality
"""

import sys
import os

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")

    try:
        import tkinter
        print("✓ tkinter available")
    except ImportError as e:
        print(f"✗ tkinter import failed: {e}")
        return False

    try:
        import pyautogui
        print("✓ pyautogui available")
    except ImportError as e:
        print(f"✗ pyautogui import failed: {e}")
        return False

    try:
        import mouse
        print("✓ mouse available")
        print(f"  Available methods: {[m for m in dir(mouse) if not m.startswith('_')]}")
    except ImportError as e:
        print(f"✗ mouse import failed: {e}")
        return False

    try:
        import keyboard
        print("✓ keyboard available")
    except ImportError as e:
        print(f"✗ keyboard import failed: {e}")
        return False

    try:
        import pystray
        print("✓ pystray available")
    except ImportError as e:
        print(f"✗ pystray import failed: {e}")
        return False

    try:
        from PIL import Image
        print("✓ PIL available")
    except ImportError as e:
        print(f"✗ PIL import failed: {e}")
        return False

    return True

def test_mouse_functionality():
    """Test basic mouse functionality"""
    print("\nTesting mouse functionality...")

    try:
        import mouse
        import pyautogui

        # Test getting mouse position
        x, y = mouse.get_position()
        print(f"✓ Current mouse position: ({x}, {y})")

        # Test pyautogui size
        screen_width, screen_height = pyautogui.size()
        print(f"✓ Screen size: {screen_width}x{screen_height}")

        return True
    except Exception as e:
        print(f"✗ Mouse functionality test failed: {e}")
        return False

def test_file_structure():
    """Test that all required files exist"""
    print("\nTesting file structure...")

    required_files = [
        'autoclicker.py',
        'requirements.txt',
        'README.md',
        'autoclicker.ico',
        'run_autoclicker.bat'
    ]

    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} exists")
        else:
            print(f"✗ {file} missing")
            return False

    return True

def main():
    """Run all tests"""
    print("🧪 Autoclicker Test Suite")
    print("=" * 40)

    all_passed = True

    # Test imports
    if not test_imports():
        all_passed = False

    # Test mouse functionality
    if not test_mouse_functionality():
        all_passed = False

    # Test file structure
    if not test_file_structure():
        all_passed = False

    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 All tests passed! The autoclicker should work correctly.")
        print("\nTo run the application:")
        print("1. Double-click run_autoclicker.bat")
        print("2. Or manually: autoclicker_env\\Scripts\\activate && python autoclicker.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
