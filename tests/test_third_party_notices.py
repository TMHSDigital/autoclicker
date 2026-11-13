"""Third-party notices and the modules the exe leaves out (#153)."""

import ast
import importlib.metadata
import re
import runpy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
notices = runpy.run_path(str(ROOT / "tools" / "third_party_notices.py"))
SPEC_TEXT = (ROOT / "packaging" / "WindowsAutoclicker.spec").read_text("utf-8")
LOCK_TEXT = (ROOT / "requirements/runtime-lock.txt").read_text("utf-8")


class TestNotBundled(unittest.TestCase):
    def test_spec_excludes_match_the_notices_tool(self):
        match = re.search(r"excludes=(\[[^\]]*\])", SPEC_TEXT)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(set(ast.literal_eval(match.group(1))), set(notices["NOT_BUNDLED"]))

    def test_gpl_modules_are_never_bundled(self):
        self.assertLessEqual({"mouseinfo", "pymsgbox"}, set(notices["NOT_BUNDLED"]))

    def test_spec_bundles_the_notices_and_license(self):
        self.assertIn('_tools["write_notices"]()', SPEC_TEXT)
        self.assertIn('(str(_notices), ".")', SPEC_TEXT)
        self.assertIn('(str(ROOT / "LICENSE"), ".")', SPEC_TEXT)


class TestLockedPackages(unittest.TestCase):
    def test_parses_pins_skips_excluded_and_sorts(self):
        lock = (
            "Pillow==13.0.0\nmouseinfo==0.1.3\n# comment\npywin32==312 ; sys_platform == 'win32'\n"
        )
        self.assertEqual(
            notices["locked_packages"](lock), [("Pillow", "13.0.0"), ("pywin32", "312")]
        )


class TestRender(unittest.TestCase):
    def setUp(self):
        for name, version in notices["locked_packages"](LOCK_TEXT):
            try:
                installed = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                self.skipTest(f"{name} is not installed")
            if installed != version:
                self.skipTest(f"{name} {installed} installed, lock pins {version}")

    def test_lists_every_bundled_package_with_its_license(self):
        with TemporaryDirectory() as tmp:
            path = notices["write_notices"](Path(tmp) / "sub" / "NOTICES.txt")
            text = path.read_text("utf-8")
        normalized = text.lower().replace("-", "_")
        for name, version in notices["locked_packages"](LOCK_TEXT):
            with self.subTest(name=name):
                self.assertIn(f"\n{name.lower().replace('-', '_')} {version}\n", normalized)
        for name in notices["NOT_BUNDLED"]:
            with self.subTest(excluded=name):
                self.assertNotIn(f"\n{name} ", normalized)
        self.assertIn("Source code: https://github.com/moses-palmer/pystray", text)
        self.assertFalse([line for line in text.splitlines() if line != line.rstrip()])

    def test_version_mismatch_is_an_error(self):
        name, version = notices["locked_packages"](LOCK_TEXT)[0]
        with self.assertRaises(SystemExit):
            notices["package_section"](name, version + ".post999")


if __name__ == "__main__":
    unittest.main()
