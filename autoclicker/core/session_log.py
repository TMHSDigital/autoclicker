# SPDX-License-Identifier: CC-BY-NC-4.0
"""Session log (start/stop/safety events) under %APPDATA%/WindowsAutoclicker/.

The file is rotated at MAX_BYTES, keeping BACKUP_COUNT older copies
(sessions.log.1 is the newest backup), so a long-lived install never grows
it without bound.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .app_data import app_data_dir

MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_log = logging.getLogger(__name__)
# Events come from the Tk thread and the click thread.
_lock = threading.Lock()


def _escape_field(value: Any) -> str:
    """Keep session-log records on a single TSV line."""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def session_log_path() -> Path:
    return app_data_dir() / "sessions.log"


def _rotate(path: Path) -> None:
    """Shift sessions.log -> .1 -> .2 ... dropping the oldest backup."""
    oldest = path.with_name(f"{path.name}.{BACKUP_COUNT}")
    if oldest.exists():
        oldest.unlink()
    for index in range(BACKUP_COUNT - 1, 0, -1):
        src = path.with_name(f"{path.name}.{index}")
        if src.exists():
            os.replace(src, path.with_name(f"{path.name}.{index + 1}"))
    os.replace(path, path.with_name(f"{path.name}.1"))


def append_session_event(event: str, **fields: Any) -> None:
    """Append one tab-separated log line; never raises to callers."""
    try:
        path = session_log_path()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        extras = " ".join(f"{k}={_escape_field(fields[k])}" for k in sorted(fields))
        line = f"{ts}\tevent={event}"
        if extras:
            line += f"\t{extras}"
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size >= MAX_BYTES:
                _rotate(path)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError as exc:
        _log.debug("Could not write session log: %s", exc)
