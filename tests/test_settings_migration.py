"""Tests for AppData settings path and legacy migration."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoclicker.core.settings_manager import SettingsManager
from autoclicker.core.settings_paths import appdata_settings_path, resolve_settings_file


class TestSettingsMigration(unittest.TestCase):
    def test_explicit_path_unchanged(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            path = tmp.name
        try:
            mgr = SettingsManager(path)
            self.assertEqual(mgr.settings_file, path)
        finally:
            os.unlink(path)

    def test_happy_path_appdata_primary(self):
        with tempfile.TemporaryDirectory() as appdata, patch.dict(os.environ, {"APPDATA": appdata}):
            primary = appdata_settings_path()
            primary.parent.mkdir(parents=True, exist_ok=True)
            primary.write_text(json.dumps({"x_coord": 42}), encoding="utf-8")
            resolved = resolve_settings_file()
            self.assertEqual(resolved, str(primary))
            mgr = SettingsManager()
            self.assertEqual(mgr.get("x_coord"), 42)

    def test_migrate_from_legacy_cwd(self):
        with (
            tempfile.TemporaryDirectory() as appdata,
            tempfile.TemporaryDirectory() as cwd,
            patch.dict(os.environ, {"APPDATA": appdata}),
            patch("autoclicker.core.settings_paths.Path.cwd", return_value=Path(cwd)),
        ):
            legacy = Path(cwd) / "autoclicker_settings.json"
            legacy.write_text(json.dumps({"y_coord": 99}), encoding="utf-8")
            resolved = resolve_settings_file()
            primary = appdata_settings_path()
            self.assertEqual(resolved, str(primary))
            self.assertTrue(primary.is_file())
            self.assertTrue((Path(cwd) / ".migrated").is_file())
            self.assertTrue(legacy.is_file())
            data = json.loads(primary.read_text(encoding="utf-8"))
            self.assertEqual(data["y_coord"], 99)

    def test_conflict_appdata_wins(self):
        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as cwd:
            legacy = Path(cwd) / "autoclicker_settings.json"
            legacy.write_text(json.dumps({"x_coord": 2}), encoding="utf-8")
            with (
                patch.dict(os.environ, {"APPDATA": appdata}),
                patch("autoclicker.core.settings_paths.Path.cwd", return_value=Path(cwd)),
            ):
                primary = appdata_settings_path()
                primary.parent.mkdir(parents=True, exist_ok=True)
                primary.write_text(json.dumps({"x_coord": 1}), encoding="utf-8")
                mgr = SettingsManager()
                self.assertEqual(mgr.get("x_coord"), 1)

    def test_no_legacy_uses_defaults(self):
        with tempfile.TemporaryDirectory() as appdata, patch.dict(os.environ, {"APPDATA": appdata}):
            mgr = SettingsManager()
            self.assertEqual(mgr.get("x_coord"), 100)
