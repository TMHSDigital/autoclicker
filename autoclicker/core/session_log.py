# SPDX-License-Identifier: CC-BY-NC-4.0
"""Append-only session log under %APPDATA%/WindowsAutoclicker/."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def session_log_path() -> Path:
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "WindowsAutoclicker" / "sessions.log"


def append_session_event(event: str, **fields: Any) -> None:
    """Append one tab-separated log line; never raises to callers."""
    try:
        path = session_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        extras = " ".join(f"{k}={fields[k]}" for k in sorted(fields))
        line = f"{ts}\tevent={event}"
        if extras:
            line += f"\t{extras}"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
