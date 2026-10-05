#!/usr/bin/env python3
"""
Regenerate the lock files.

- requirements-lock.txt: runtime dependencies from requirements.txt, compiled
  with uv for Windows and Python 3.11 (CI and release default). It is resolved
  from requirements.txt alone, never frozen from the dev venv, so dev tools and
  the editable install can't leak in (#108).
- requirements-dev-lock.txt: dev and build tooling from requirements-dev.in,
  compiled with uv as one lock valid for every supported Python (3.10+), so
  CI and pre-commit always run the same tool versions.

Existing pins are kept unless the inputs need a change; pass --upgrade to move
every pin to the newest allowed version.

Usage (uv on PATH; any Python):
  python tools/refresh_lock.py            # both
  python tools/refresh_lock.py --dev      # dev lock only
  python tools/refresh_lock.py --upgrade  # both, newest allowed versions
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
# The exe and CI run the runtime dependencies on Windows with this Python.
RUNTIME_PYTHON = "3.11"


def runtime_lock_command(uv: str, *, upgrade: bool = False) -> list[str]:
    command = [
        uv,
        "pip",
        "compile",
        str(REQUIREMENTS),
        "--python-version",
        RUNTIME_PYTHON,
        "--python-platform",
        "windows",
        "--no-header",
        "--no-annotate",
        "--quiet",
        "-o",
        str(LOCK_FILE),
    ]
    return [*command, "--upgrade"] if upgrade else command


def dev_lock_command(uv: str, *, upgrade: bool = False) -> list[str]:
    command = [
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
    ]
    return [*command, "--upgrade"] if upgrade else command


def main(argv: list[str]) -> int:
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required to refresh the locks: https://docs.astral.sh/uv/", file=sys.stderr)
        return 1
    upgrade = "--upgrade" in argv
    commands = [dev_lock_command(uv, upgrade=upgrade)]
    if "--dev" not in argv:
        commands.insert(0, runtime_lock_command(uv, upgrade=upgrade))
    for command in commands:
        subprocess.run(command, check=True, cwd=ROOT)
        print(f"Wrote {command[command.index('-o') + 1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
