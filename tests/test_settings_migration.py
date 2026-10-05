"""Tests for AppData settings path and legacy migration."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

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
            patch("autoclicker.core.settings_paths.legacy_app_dir", return_value=Path(cwd)),
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
                patch("autoclicker.core.settings_paths.legacy_app_dir", return_value=Path(cwd)),
            ):
                primary = appdata_settings_path()
                primary.parent.mkdir(parents=True, exist_ok=True)
                primary.write_text(json.dumps({"x_coord": 1}), encoding="utf-8")
                mgr = SettingsManager()
                self.assertEqual(mgr.get("x_coord"), 1)

    def test_no_legacy_uses_defaults(self):
        with (
            tempfile.TemporaryDirectory() as appdata,
            tempfile.TemporaryDirectory() as cwd,
            patch.dict(os.environ, {"APPDATA": appdata}),
            patch("autoclicker.core.settings_paths.legacy_app_dir", return_value=Path(cwd)),
        ):
            mgr = SettingsManager()
            self.assertEqual(mgr.get("x_coord"), 100)


class TestNoMigrationOverUnreadablePrimary(unittest.TestCase):
    """#65: a legacy file must not be copied over an unreadable AppData file."""

    def test_unreadable_primary_is_left_for_quarantine(self):
        from autoclicker.core import settings_paths

        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp, "appdata", "autoclicker_settings.json")
            primary.parent.mkdir()
            primary.write_text("{broken", encoding="utf-8")
            legacy = Path(tmp, "autoclicker_settings.json")
            legacy.write_text('{"x_coord": 5}', encoding="utf-8")
            with (
                patch.object(settings_paths, "appdata_settings_path", return_value=primary),
                patch.object(settings_paths, "legacy_settings_path", return_value=legacy),
                patch.object(
                    settings_paths,
                    "legacy_migrated_marker_path",
                    return_value=Path(tmp, ".migrated"),
                ),
            ):
                self.assertEqual(settings_paths.resolve_settings_file(), str(primary))
            self.assertEqual(primary.read_text(encoding="utf-8"), "{broken")


class TestLegacyLocation(unittest.TestCase):
    """#105: only a file next to the app is migrated, never one in the working folder."""

    def test_file_in_the_working_folder_is_ignored(self):
        with (
            tempfile.TemporaryDirectory() as appdata,
            tempfile.TemporaryDirectory() as cwd,
            tempfile.TemporaryDirectory() as app_dir,
            patch.dict(os.environ, {"APPDATA": appdata}),
            patch("autoclicker.core.settings_paths.legacy_app_dir", return_value=Path(app_dir)),
        ):
            Path(cwd, "autoclicker_settings.json").write_text(
                json.dumps({"enable_failsafe": False}), encoding="utf-8"
            )
            saved = os.getcwd()
            os.chdir(cwd)
            try:
                resolved = resolve_settings_file()
            finally:
                os.chdir(saved)
            self.assertEqual(resolved, str(appdata_settings_path()))
            self.assertFalse(appdata_settings_path().exists())

    def test_failed_migration_still_saves_to_appdata(self):
        from autoclicker.core import settings_paths

        with (
            tempfile.TemporaryDirectory() as appdata,
            tempfile.TemporaryDirectory() as app_dir,
            patch.dict(os.environ, {"APPDATA": appdata}),
            patch.object(settings_paths, "legacy_app_dir", return_value=Path(app_dir)),
            patch.object(settings_paths, "atomic_write_json", side_effect=OSError("disk full")),
        ):
            Path(app_dir, "autoclicker_settings.json").write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_settings_file(), str(appdata_settings_path()))

    def test_unwritable_marker_does_not_redirect(self):
        from autoclicker.core import settings_paths

        with (
            tempfile.TemporaryDirectory() as appdata,
            tempfile.TemporaryDirectory() as app_dir,
            patch.dict(os.environ, {"APPDATA": appdata}),
            patch.object(settings_paths, "legacy_app_dir", return_value=Path(app_dir)),
        ):
            Path(app_dir, "autoclicker_settings.json").write_text('{"y_coord": 7}', "utf-8")
            with patch.object(Path, "write_text", side_effect=OSError("read-only")):
                resolved = resolve_settings_file()
            self.assertEqual(resolved, str(appdata_settings_path()))
            self.assertEqual(json.loads(appdata_settings_path().read_text("utf-8"))["y_coord"], 7)

    @pytest.mark.real_legacy_dir
    def test_app_dir_is_the_exe_folder_when_frozen(self):
        from autoclicker.core import settings_paths

        self.assertEqual(
            settings_paths.legacy_app_dir(), Path(settings_paths.__file__).resolve().parents[2]
        )
        real = settings_paths.legacy_app_dir
        with (
            patch.object(settings_paths.sys, "frozen", True, create=True),
            patch.object(settings_paths.sys, "executable", r"C:\Tools\Autoclicker\app.exe"),
        ):
            self.assertEqual(real(), Path(r"C:\Tools\Autoclicker").resolve())
