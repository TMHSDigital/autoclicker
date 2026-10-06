"""Release notes come from the tagged version's CHANGELOG section only (#45)."""

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "release_notes", Path(__file__).resolve().parent.parent / "scripts" / "release_notes.py"
)
assert _SPEC and _SPEC.loader
release_notes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release_notes)

SAMPLE = """# Changelog

## [Unreleased]

### Added

- Upcoming thing.

## [1.5.0] - 2026-10-05

### Fixed

- Stop really stops.

## [1.4.1] - 2026-10-04

### Security

- Pillow bump.

[Unreleased]: https://example.invalid/compare/v1.5.0...HEAD
[1.5.0]: https://example.invalid/releases/tag/v1.5.0
"""


class TestReleaseNotes(unittest.TestCase):
    def test_extracts_only_that_version(self):
        body = release_notes.extract_section(SAMPLE, "v1.5.0")
        self.assertEqual(body, "### Fixed\n\n- Stop really stops.")

    def test_last_section_stops_at_link_block(self):
        body = release_notes.extract_section(SAMPLE, "1.4.1")
        self.assertEqual(body, "### Security\n\n- Pillow bump.")

    def test_missing_version(self):
        self.assertIsNone(release_notes.extract_section(SAMPLE, "9.9.9"))
        self.assertIsNone(release_notes.release_notes(SAMPLE, "9.9.9"))

    def test_notes_include_verification_footer(self):
        notes = release_notes.release_notes(SAMPLE, "v1.5.0")
        self.assertTrue(notes.startswith("**Install:**"))  # #117: how to get it, first
        self.assertIn("scoop install tmhs/windows-autoclicker", notes)
        self.assertIn("\n\n### Fixed\n\n- Stop really stops.", notes)
        self.assertIn("gh attestation verify", notes)
        self.assertIn("/blob/v1.5.0/CHANGELOG.md", notes)

    def test_package_version_parsing(self):
        self.assertEqual(release_notes.package_version('x\n__version__ = "1.5.0"\n'), "1.5.0")
        self.assertIsNone(release_notes.package_version("nothing here"))

    def test_mismatched_tag_fails(self):
        self.assertEqual(release_notes.main(["v0.0.1"]), 1)

    def test_real_changelog_has_current_release(self):
        changelog = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text("utf-8")
        self.assertIsNotNone(release_notes.extract_section(changelog, "1.4.1"))


if __name__ == "__main__":
    unittest.main()
