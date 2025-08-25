#!/usr/bin/env python3
"""
Launcher script for Windows Autoclicker
Activates virtual environment and runs the application
"""

import subprocess
import sys
import os

def main():
    """Launch the autoclicker with virtual environment"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_path = os.path.join(script_dir, 'autoclicker_env', 'Scripts', 'activate')
    main_script = os.path.join(script_dir, 'autoclicker.py')

    # Check if virtual environment exists
    if not os.path.exists(venv_path):
        print("Virtual environment not found. Please run setup first.")
        print("Run: python -m venv autoclicker_env && autoclicker_env\\Scripts\\activate && pip install -r requirements.txt")
        input("Press Enter to exit...")
        return

    # Check if main script exists
    if not os.path.exists(main_script):
        print("Main application file not found:", main_script)
        input("Press Enter to exit...")
        return

    try:
        # Run the autoclicker in the virtual environment
        cmd = f'cmd /c "{venv_path} && python {main_script}"'
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print(f"Error launching application: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
