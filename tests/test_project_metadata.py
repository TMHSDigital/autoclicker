"""Facts kept in more than one file stay in step (#111).

Parsed with regular expressions: tomllib is Python 3.11+ and CI covers 3.10.
"""

import re
import unittest
from pathlib import Path

import autoclicker

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = (ROOT / "pyproject.toml").read_text("utf-8")


def _requirement_names(lines: list[str]) -> list[str]:
    names = []
    for line in lines:
        line = line.split("#", 1)[0].strip().strip('",')
        if line:
            names.append(re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].lower())
    return sorted(names)


class TestVersion(unittest.TestCase):
    def test_pyproject_matches_package(self):
        match = re.search(r'^version = "([^"]+)"', PYPROJECT, re.MULTILINE)
        assert match is not None
        self.assertEqual(match.group(1), autoclicker.__version__)


class TestDependencies(unittest.TestCase):
    def test_requirements_txt_matches_pyproject(self):
        block = re.search(r"^dependencies = \[(.*?)^\]", PYPROJECT, re.MULTILINE | re.DOTALL)
        assert block is not None
        from_pyproject = _requirement_names(block.group(1).splitlines())
        requirements = (ROOT / "requirements.txt").read_text("utf-8").splitlines()
        self.assertEqual(_requirement_names(requirements), from_pyproject)

    def test_runtime_lock_pins_every_dependency(self):
        lock = (ROOT / "requirements-lock.txt").read_text("utf-8").splitlines()
        pinned = {line.split("==")[0].strip().lower() for line in lock if "==" in line}
        requirements = (ROOT / "requirements.txt").read_text("utf-8").splitlines()
        for name in _requirement_names(requirements):
            self.assertIn(name.replace("_", "-"), pinned)


class TestDeprecatedAlias(unittest.TestCase):
    def test_coordinate_picker_still_exports_profiles(self):
        """utils.coordinate_picker was renamed to utils.profiles in 1.6.0; remove in 2.0."""
        from autoclicker.utils import coordinate_picker, profiles

        self.assertIs(coordinate_picker.PresetManager, profiles.PresetManager)


if __name__ == "__main__":
    unittest.main()
