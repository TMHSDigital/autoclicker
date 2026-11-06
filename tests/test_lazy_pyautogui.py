"""PyAutoGUI loads on first use, not at startup (#163)."""

import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from autoclicker.core.lazy_pyautogui import _LazyPyAutoGUI


class TestLazyPyAutoGUI(unittest.TestCase):
    def setUp(self):
        self.fake = types.ModuleType("pyautogui")
        self.fake.FAILSAFE = True
        self.fake.size = lambda: (800, 600)
        patcher = patch.dict(sys.modules, {"pyautogui": self.fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.lazy = _LazyPyAutoGUI()

    def test_settings_before_load_are_kept_and_applied(self):
        self.lazy.FAILSAFE = False
        self.assertFalse(self.lazy.loaded)
        self.assertIs(self.lazy.FAILSAFE, False)  # read back without importing
        self.assertFalse(self.lazy.loaded)
        self.assertEqual(self.lazy.size(), (800, 600))
        self.assertTrue(self.lazy.loaded)
        self.assertIs(self.fake.FAILSAFE, False)

    def test_settings_after_load_go_to_the_module(self):
        self.lazy.load()
        self.lazy.PAUSE = 0
        self.assertEqual(self.fake.PAUSE, 0)

    def test_load_returns_the_module_once(self):
        self.assertIs(self.lazy.load(), self.fake)
        self.assertIs(self.lazy.load(), self.fake)


class TestStartupImports(unittest.TestCase):
    def test_importing_the_app_does_not_import_pyautogui_or_urllib(self):
        code = (
            "import sys, autoclicker.main, autoclicker.gui.main_window; "
            "print(sorted(m for m in ('pyautogui', 'urllib.request') if m in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True
        )
        self.assertEqual(result.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
