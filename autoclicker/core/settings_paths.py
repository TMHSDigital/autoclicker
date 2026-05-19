# SPDX-License-Identifier: CC-BY-NC-4.0
"""Resolve settings file locations and legacy migration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .session_log import append_session_event

LEGACY_FILENAME = "autoclicker_settings.json"
MIGRATED_MARKER = ".migrated"


def appdata_settings_path() -> Path:
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "WindowsAutoclicker" / LEGACY_FILENAME


def legacy_cwd_settings_path() -> Path:
    return Path.cwd() / LEGACY_FILENAME


def legacy_migrated_marker_path() -> Path:
    return Path.cwd() / MIGRATED_MARKER


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_file():
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def resolve_settings_file(explicit: str | None = None) -> str:
    """
    Primary settings path is %APPDATA%/WindowsAutoclicker/autoclicker_settings.json.
    Migrate from CWD legacy file once; AppData wins on conflict.
    """
    if explicit is not None and explicit != LEGACY_FILENAME:
        return explicit

    primary = appdata_settings_path()
    legacy = legacy_cwd_settings_path()
    marker = legacy_migrated_marker_path()

    primary.parent.mkdir(parents=True, exist_ok=True)

    primary_data = _read_json(primary)
    legacy_data = _read_json(legacy)

    if primary_data is not None:
        if legacy_data is not None and legacy_data != primary_data:
            append_session_event(
                "settings_conflict",
                message="AppData settings used; legacy CWD file unchanged",
            )
        return str(primary)

    if legacy_data is not None and not marker.exists():
        try:
            with primary.open("w", encoding="utf-8") as fh:
                json.dump(legacy_data, fh, indent=2, ensure_ascii=False)
            marker.write_text("migrated\n", encoding="utf-8")
            append_session_event("settings_migrated", from_path=str(legacy), to_path=str(primary))
        except OSError:
            return str(legacy)

    return str(primary)
