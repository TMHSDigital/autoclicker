"""Scoop and winget manifests for a release (#76)."""

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "package_manifests", Path(__file__).resolve().parent.parent / "tools" / "package_manifests.py"
)
manifests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifests)

SHA = "ab" * 32


class TestManifests(unittest.TestCase):
    def test_scoop(self):
        scoop = manifests.scoop_manifest("1.5.0", SHA)
        self.assertEqual(scoop["version"], "1.5.0")
        self.assertTrue(scoop["url"].endswith("/v1.5.0/WindowsAutoclicker.exe"))
        self.assertEqual(scoop["hash"], SHA)
        self.assertEqual(scoop["autoupdate"]["hash"], {"url": "$url.sha256"})

    def test_winget(self):
        files = manifests.winget_manifests("1.5.0", SHA)
        self.assertEqual(len(files), 3)
        installer = files["TMHSDigital.WindowsAutoclicker.installer.yaml"]
        self.assertIn("InstallerType: portable", installer)
        self.assertIn(f"InstallerSha256: {SHA.upper()}", installer)
        for text in files.values():
            self.assertIn("PackageVersion: 1.5.0", text)
            self.assertIn("ManifestVersion: 1.12.0", text)


class TestVerifyWritten(unittest.TestCase):
    """#109: the release job checks the manifests before committing them to main."""

    def setUp(self):
        import json

        scoop_path, _ = manifests.written_paths("0.0.0")
        bucket = json.loads(scoop_path.read_text("utf-8"))
        self.version, self.sha = bucket["version"], bucket["hash"]

    def test_committed_manifests_are_consistent(self):
        self.assertEqual(manifests.verify_written(self.version, self.sha), [])

    def test_wrong_hash_or_version_is_reported(self):
        problems = manifests.verify_written(self.version, "cd" * 32)
        self.assertTrue(any("hash" in p for p in problems), problems)
        self.assertTrue(any("InstallerSha256" in p for p in problems), problems)
        missing = manifests.verify_written("99.0.0", self.sha)
        self.assertTrue(any("version" in p for p in missing), missing)
