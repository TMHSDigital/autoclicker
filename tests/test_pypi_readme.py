"""README links are made absolute for the PyPI page (#118)."""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("pypi_readme", ROOT / "tools" / "pypi_readme.py")
assert _SPEC and _SPEC.loader
pypi_readme = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pypi_readme)


class TestAbsolutize(unittest.TestCase):
    def test_images_links_and_files(self):
        text = (
            '<img src="docs/images/a.png" /> [verify](docs/RELEASING.md#x) '
            '<a href="CONTRIBUTING.md">c</a> [license](LICENSE) '
            "[web](https://example.com) [top](#quick-start)"
        )
        out = pypi_readme.absolutize(text)
        raw = "https://raw.githubusercontent.com/TMHSDigital/autoclicker/main"
        blob = "https://github.com/TMHSDigital/autoclicker/blob/main"
        self.assertIn(f'src="{raw}/docs/images/a.png"', out)
        self.assertIn(f"]({blob}/docs/RELEASING.md#x)", out)
        self.assertIn(f'href="{blob}/CONTRIBUTING.md"', out)
        self.assertIn(f"]({blob}/LICENSE)", out)
        self.assertIn("](https://example.com)", out)
        self.assertIn("](#quick-start)", out)

    def test_real_readme_has_no_relative_links_left(self):
        out = pypi_readme.absolutize((ROOT / "README.md").read_text("utf-8"))
        relative = re.findall(r'(?:src|href)="(?!https?:|#|mailto:)([^"]+)"', out)
        relative += re.findall(r"\]\((?!https?:|#|mailto:)([^)]+)\)", out)
        self.assertEqual(relative, [])


if __name__ == "__main__":
    unittest.main()
