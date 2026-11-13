"""pyproject, requirements/runtime.txt and requirements/dev.in stay in step (#155)."""

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _specs(lines):
    """``{name: spec}`` for requirement lines, ignoring comments and blanks."""
    found = {}
    for line in lines:
        line = line.split("#", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", line)
        if match:
            found[match.group(1).lower()] = match.group(2).replace(" ", "")
    return found


class TestDependencySpecs(unittest.TestCase):
    def setUp(self):
        self.project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]

    def test_runtime_dependencies_match_requirements_txt(self):
        txt = _specs((ROOT / "requirements/runtime.txt").read_text("utf-8").splitlines())
        self.assertEqual(_specs(self.project["dependencies"]), txt)

    def test_dev_and_build_extras_match_requirements_dev_in(self):
        dev_in = _specs((ROOT / "requirements/dev.in").read_text("utf-8").splitlines())
        extras = self.project["optional-dependencies"]
        self.assertEqual(_specs(extras["dev"] + extras["build"]), dev_in)


if __name__ == "__main__":
    unittest.main()
