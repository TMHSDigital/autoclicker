"""Tests for bundled resource path resolution."""

import unittest
from pathlib import Path
from unittest.mock import patch

from autoclicker.core.resources import ASSETS_DIR, resource_path


class TestResourcePath(unittest.TestCase):
    def test_repo_root_candidate_when_file_missing(self):
        path = resource_path("definitely-missing-icon.ico")
        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, "definitely-missing-icon.ico")

    def test_prefers_meipass_when_file_exists(self):
        with patch("autoclicker.core.resources.sys") as mock_sys:
            mock_sys._MEIPASS = "C:\\frozen"
            with patch.object(Path, "is_file", return_value=True):
                path = resource_path("autoclicker.ico")
        self.assertEqual(path, Path("C:\\frozen") / "autoclicker" / "assets" / "autoclicker.ico")

    def test_bundled_icons_ship_in_the_package(self):
        """#58: icons live inside the package so wheels and pipx installs get them."""
        for name in ("autoclicker.ico", "autoclicker.png"):
            path = resource_path(name)
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.parent, ASSETS_DIR)
