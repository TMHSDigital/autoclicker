#!/usr/bin/env python3
"""
Regenerate the lock files.

- requirements-lock.txt: runtime dependencies from requirements.txt, frozen
  from a clean environment on Python 3.11 (CI default).
- requirements-dev-lock.txt: dev and build tooling from requirements-dev.in,
  compiled with uv as one lock valid for every supported Python (3.10+), so
  CI and pre-commit always run the same tool versions.

Usage (Python 3.11, uv on PATH):
  python tools/refresh_lock.py            # both
  python tools/refresh_lock.py --dev      # dev lock only
Or: make lock / tasks.bat lock (after make install)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
LOCK_FILE = ROOT / "requirements-lock.txt"
DEV_REQUIREMENTS = ROOT / "requirements-dev.in"
DEV_LOCK_FILE = ROOT / "requirements-dev-lock.txt"
MIN_PYTHON = "3.10"


def refresh_runtime_lock() -> int:
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


def refresh_dev_lock() -> int:
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required for the dev lock: https://docs.astral.sh/uv/", file=sys.stderr)
        return 1
    subprocess.run(
        [
            uv,
            "pip",
            "compile",
            str(DEV_REQUIREMENTS),
            "--universal",
            "--python-version",
            MIN_PYTHON,
            "--no-header",
            "--quiet",
            "-o",
            str(DEV_LOCK_FILE),
        ],
        check=True,
        cwd=ROOT,
    )
    print(f"Wrote {DEV_LOCK_FILE}")
    return 0


def main(argv: list[str]) -> int:
    if "--dev" not in argv:
        status = refresh_runtime_lock()
        if status:
            return status
    return refresh_dev_lock()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
