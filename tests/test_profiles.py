"""Profiles: presets that also restore click settings, with import/export (#73)."""

import json
import os
import tempfile
import unittest

from autoclicker.core.settings_manager import SettingsManager
from autoclicker.utils.profiles import (
    EXPORT_FORMAT,
    PresetManager,
    describe_profile,
)

FULL = {
    "x": 800,
    "y": 600,
    "target_mode": "fixed",
    "interval": 100,
    "interval_unit": "ms",
    "variation": 10,
    "mouse_button": "right",
    "click_type": "double",
    "burst_clicks": 3,
    "burst_pause": 50,
    "max_clicks": 1000,
    "auto_stop_minutes": 5,
}


class ProfileTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = SettingsManager(os.path.join(self._dir.name, "settings.json"))
        self.manager = PresetManager(self.settings)

    def path(self, name):
        return os.path.join(self._dir.name, name)


class TestProfileStorage(ProfileTestCase):
    def test_round_trip_keeps_click_settings(self):
        self.assertTrue(self.manager.save_profile("Game", {**FULL, "theme": "dark"}))
        loaded = self.manager.load_profile("Game")
        self.assertEqual(loaded, FULL)  # unrelated keys are not stored
        self.assertEqual(self.manager.load_preset("Game"), (800, 600))

    def test_old_coordinate_only_presets_still_load(self):
        self.settings.set("presets", {"Old": {"x": 5, "y": 6}})
        self.assertEqual(self.manager.load_profile("Old"), {"x": 5, "y": 6})

    def test_missing_point_is_not_a_profile(self):
        self.settings.set("presets", {"Bad": {"interval": 5}})
        self.assertIsNone(self.manager.load_profile("Bad"))

    def test_has_profile(self):
        self.manager.save_preset("A", 1, 2)
        self.assertTrue(self.manager.has_profile("A"))
        self.assertFalse(self.manager.has_profile("B"))


class TestDescribe(unittest.TestCase):
    def test_full_profile(self):
        self.assertEqual(
            describe_profile(FULL),
            "(800, 600) · every 100 ms ±10 ms · right double · burst 3 x 50 ms"
            " · stop after 1,000 clicks · stop after 5 min",
        )

    def test_cursor_and_seconds(self):
        text = describe_profile(
            {"x": 0, "y": 0, "target_mode": "cursor", "interval": 2, "interval_unit": "seconds"}
        )
        self.assertEqual(text, "at the cursor · every 2 s")

    def test_coordinates_only(self):
        self.assertEqual(describe_profile({"x": 1, "y": 2}), "(1, 2)")


class TestImportExport(ProfileTestCase):
    def test_export_then_import_into_a_fresh_install(self):
        self.manager.save_profile("Game", FULL)
        self.manager.save_preset("Spot", 10, 20)
        out = self.path("profiles.json")
        self.assertEqual(self.manager.export_profiles(out), 2)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["format"], EXPORT_FORMAT)

        other = PresetManager(SettingsManager(self.path("other.json")))
        result = other.import_profiles(other.read_profiles_file(out), replace_existing=False)
        self.assertEqual(sorted(result.added), ["Game", "Spot"])
        self.assertEqual(other.load_profile("Game"), FULL)

    def test_existing_names_kept_unless_replacing(self):
        self.manager.save_preset("Spot", 1, 1)
        incoming = {"Spot": {"x": 9, "y": 9}}
        result = self.manager.import_profiles(incoming, replace_existing=False)
        self.assertEqual(result.skipped, ["Spot"])
        self.assertEqual(self.manager.load_preset("Spot"), (1, 1))
        result = self.manager.import_profiles(incoming, replace_existing=True)
        self.assertEqual(result.replaced, ["Spot"])
        self.assertEqual(self.manager.load_preset("Spot"), (9, 9))

    def test_invalid_entries_are_skipped(self):
        incoming = {
            "ok": {"x": "5", "y": 6, "interval": "250"},
            "no point": {"interval": 5},
            "bad button": {"x": 1, "y": 1, "mouse_button": "thumb"},
            "not a dict": [1, 2],
            "": {"x": 1, "y": 1},
        }
        result = self.manager.import_profiles(incoming, replace_existing=False)
        self.assertEqual(result.added, ["ok"])
        self.assertEqual(
            sorted(result.invalid), sorted(["no point", "bad button", "not a dict", ""])
        )
        self.assertEqual(self.manager.load_profile("ok"), {"x": 5, "y": 6, "interval": 250})

    def test_reading_a_foreign_file_fails_clearly(self):
        bad = self.path("bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump({"x_coord": 5}, fh)
        with self.assertRaisesRegex(ValueError, "not a Windows Autoclicker profiles file"):
            self.manager.read_profiles_file(bad)
        with self.assertRaisesRegex(ValueError, "Could not read"):
            self.manager.read_profiles_file(self.path("missing.json"))


class TestImageProfiles(ProfileTestCase):
    """#98: image profiles carry their own image, safely, through export/import."""

    def setUp(self):
        super().setUp()
        from unittest.mock import patch

        from PIL import Image

        self.appdata = os.path.join(self._dir.name, "appdata")
        env = patch.dict(os.environ, {"APPDATA": self.appdata})
        env.start()
        self.addCleanup(env.stop)
        self.image_file = self.path("capture.png")
        Image.new("RGB", (30, 12), (200, 10, 10)).save(self.image_file)
        self.profile = {
            "x": 1,
            "y": 2,
            "target_mode": "image",
            "image_path": self.image_file,
            "image_region": [100, 100, 330, 312],
            "image_margin": 150,
        }

    def test_saved_with_its_image_and_described(self):
        self.manager.save_profile("Ok button", self.profile)
        loaded = self.manager.load_profile("Ok button")
        self.assertEqual(loaded["image_path"], self.image_file)
        self.assertEqual(loaded["image_region"], [100, 100, 330, 312])
        self.assertIn("wherever its image appears", describe_profile(loaded))

    def test_export_embeds_the_png_and_import_stores_it_locally(self):
        self.manager.save_profile("Ok button", self.profile)
        out = self.path("export.json")
        self.manager.export_profiles(out)
        exported = json.loads(open(out, encoding="utf-8").read())["profiles"]["Ok button"]
        self.assertNotIn("image_path", exported)
        self.assertIn("image_png", exported)

        fresh = PresetManager(SettingsManager(self.path("other.json")))
        profiles = fresh.read_profiles_file(out)
        result = fresh.import_profiles(profiles, replace_existing=False)
        self.assertEqual(result.added, ["Ok button"])
        stored = fresh.load_profile("Ok button")["image_path"]
        self.assertTrue(
            stored.startswith(os.path.join(self.appdata, "WindowsAutoclicker", "images"))
        )
        from PIL import Image

        with Image.open(stored) as image:
            self.assertEqual(image.size, (30, 12))
        # Importing the same profile again reuses the same file.
        fresh.import_profiles(profiles, replace_existing=True)
        self.assertEqual(fresh.load_profile("Ok button")["image_path"], stored)

    def test_import_never_trusts_a_path_from_the_file(self):
        raw = {**self.profile, "image_path": "\\\\attacker\\share\\x.png"}
        result = self.manager.import_profiles({"Evil": raw}, replace_existing=False)
        self.assertEqual(result.added, ["Evil"])
        self.assertNotIn("image_path", self.manager.load_profile("Evil"))

    def test_bad_embedded_images_are_rejected(self):
        import base64
        import io

        from PIL import Image

        gif = io.BytesIO()
        Image.new("RGB", (4, 4)).save(gif, format="GIF")
        for bad in ("not base64!", base64.b64encode(b"hello").decode(), 42,
                    base64.b64encode(gif.getvalue()).decode()):  # fmt: skip
            with self.subTest(bad=str(bad)[:20]):
                raw = {"x": 1, "y": 1, "target_mode": "image", "image_png": bad}
                result = self.manager.import_profiles({"Bad": raw}, replace_existing=True)
                self.assertEqual(result.invalid, ["Bad"])
