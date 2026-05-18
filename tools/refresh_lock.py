#!/usr/bin/env python3
"""
Regenerate requirements-lock.txt from requirements.txt.

Run from a clean environment on Python 3.11 (CI default):
  python tools/refresh_lock.py
Or: make lock / tasks.bat lock (after make install)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
LOCK_FILE = ROOT / "requirements-lock.txt"


def main() -> int:
    if not REQUIREMENTS.is_file():
        print(f"Missing {REQUIREMENTS}", file=sys.stderr)
        return 1

    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        check=True,
    )
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
    LOCK_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} packages to {LOCK_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
