# SPDX-License-Identifier: CC-BY-NC-4.0
"""Resolve settings file locations and legacy migration."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .app_data import app_data_dir
from .session_log import append_session_event

LEGACY_FILENAME = "autoclicker_settings.json"
MIGRATED_MARKER = ".migrated"

_log = logging.getLogger(__name__)


def appdata_settings_path() -> Path:
    return app_data_dir() / LEGACY_FILENAME


def legacy_app_dir() -> Path:
    """Folder older versions kept their settings in: next to the app.

    The exe's folder, or the source checkout when run with Python. Never the
    working directory, which may be any folder the app was started from (#105).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def legacy_settings_path() -> Path:
    return legacy_app_dir() / LEGACY_FILENAME


def legacy_migrated_marker_path() -> Path:
    return legacy_app_dir() / MIGRATED_MARKER


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


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON via a same-directory temp file, then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def resolve_settings_file(explicit: str | None = None) -> str:
    """
    Primary settings path is %APPDATA%/WindowsAutoclicker/autoclicker_settings.json.
    A legacy file next to the app is migrated once, while there is no AppData
    file yet; AppData wins on conflict. Settings are always saved to AppData.
    """
    if explicit is not None and explicit != LEGACY_FILENAME:
        return explicit

    primary = appdata_settings_path()
    legacy = legacy_settings_path()
    marker = legacy_migrated_marker_path()

    primary.parent.mkdir(parents=True, exist_ok=True)

    primary_data = _read_json(primary)
    legacy_data = _read_json(legacy)

    if primary_data is not None:
        if legacy_data is not None and legacy_data != primary_data:
            append_session_event(
                "settings_conflict",
                message="AppData settings used; legacy file next to the app unchanged",
            )
        return str(primary)

    # Never migrate over an existing (even unreadable) AppData file: SettingsManager
    # moves an unreadable one aside instead of losing it.
    if legacy_data is not None and not marker.exists() and not primary.exists():
        try:
            atomic_write_json(primary, legacy_data)
        except OSError as e:
            _log.warning("Could not migrate %s: %s", legacy, e)
            return str(primary)  # never save to the legacy file (#105)
        append_session_event("settings_migrated", from_path=str(legacy), to_path=str(primary))
        try:
            # Only a hint for anyone looking in the old folder: once the AppData
            # file exists, migration never runs again anyway.
            marker.write_text("migrated\n", encoding="utf-8")
        except OSError:
            pass

    return str(primary)
