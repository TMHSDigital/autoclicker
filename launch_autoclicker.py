#!/usr/bin/env python3
"""
Launcher script for the modular autoclicker application
"""

import sys
import os

# Add current directory to path so we can import autoclicker package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from autoclicker.main import main

if __name__ == "__main__":
    main()
