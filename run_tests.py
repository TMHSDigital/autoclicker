#!/usr/bin/env python3
"""
Test runner for the autoclicker application.
Thin wrapper around pytest for backward compatibility.
"""

import subprocess
import sys


def main() -> int:
    args = [sys.executable, "-m", "pytest"]
    if len(sys.argv) > 1 and sys.argv[1] == "--coverage":
        args.extend(
            [
                "--cov=autoclicker",
                "--cov-report=term",
                "--cov-report=html",
            ]
        )
    result = subprocess.run(args)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
