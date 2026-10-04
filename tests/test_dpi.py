"""DPI awareness is explicit and set before PyAutoGUI loads (#67)."""

import subprocess
import sys
import unittest
from unittest.mock import MagicMock

from autoclicker.core.dpi import enable_per_monitor_dpi_awareness


class TestFallbacks(unittest.TestCase):
    def test_prefers_per_monitor_v2(self):
        windll = MagicMock()
        windll.user32.SetProcessDpiAwarenessContext.return_value = 1
        self.assertEqual(enable_per_monitor_dpi_awareness(windll), "per-monitor-v2")
        windll.shcore.SetProcessDpiAwareness.assert_not_called()

    def test_falls_back_to_per_monitor(self):
        windll = MagicMock()
        windll.user32.SetProcessDpiAwarenessContext.side_effect = AttributeError
        windll.shcore.SetProcessDpiAwareness.return_value = 0
        self.assertEqual(enable_per_monitor_dpi_awareness(windll), "per-monitor")

    def test_falls_back_to_system(self):
        windll = MagicMock()
        windll.user32.SetProcessDpiAwarenessContext.return_value = 0
        windll.shcore.SetProcessDpiAwareness.side_effect = OSError
        windll.user32.SetProcessDPIAware.return_value = 1
        self.assertEqual(enable_per_monitor_dpi_awareness(windll), "system")

    def test_already_set_is_unchanged(self):
        windll = MagicMock()
        windll.user32.SetProcessDpiAwarenessContext.return_value = 0
        windll.shcore.SetProcessDpiAwareness.return_value = -2147024891  # E_ACCESSDENIED
        windll.user32.SetProcessDPIAware.return_value = 0
        self.assertEqual(enable_per_monitor_dpi_awareness(windll), "unchanged")


@unittest.skipUnless(sys.platform == "win32", "Windows DPI APIs")
class TestEntryPoint(unittest.TestCase):
    def test_importing_main_leaves_the_process_per_monitor_aware(self):
        """PyAutoGUI is imported by the GUI; it must not downgrade the awareness."""
        code = (
            "import sys, ctypes\n"
            "sys.modules['sv_ttk'] = type(sys)('sv_ttk')\n"
            "import autoclicker.main\n"
            "u = ctypes.windll.user32\n"
            "u.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p\n"
            "u.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]\n"
            "print(u.GetAwarenessFromDpiAwarenessContext(u.GetThreadDpiAwarenessContext()))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "2")  # DPI_AWARENESS_PER_MONITOR_AWARE
