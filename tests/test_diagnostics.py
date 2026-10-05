"""Copy diagnostics (#88) and the Info dialog."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoclicker import __version__
from autoclicker.core.diagnostics import build_report, redact_settings
from autoclicker.core.screen import ScreenBounds

SETTINGS = {
    "interval": 100,
    "x_coord": 5,
    "presets": {"Bank login": {"x": 1, "y": 2}, "Home": {"x": 3, "y": 4}},
    "sequence": [{"x": 10, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 30}],
    "condition_x": 640,
    "condition_y": 360,
    "condition_color": "#123456",
}


class TestRedaction(unittest.TestCase):
    def test_personal_details_are_summarized(self):
        redacted = redact_settings(SETTINGS)
        self.assertEqual(redacted["presets"], "<2 profiles>")
        self.assertEqual(redacted["sequence"], "<3 steps>")
        self.assertEqual(redacted["condition_pixel"], "<redacted>")
        for key in ("condition_x", "condition_y", "condition_color"):
            self.assertNotIn(key, redacted)
        self.assertEqual(redacted["interval"], 100)


class TestReport(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.folder = Path(self._dir.name)

    def report(self):
        return build_report(
            SETTINGS,
            monitors=lambda: [ScreenBounds(-1920, 0, 1920, 1080), ScreenBounds(0, 0, 2560, 1440)],
            data_dir=self.folder,
        )

    def test_contents(self):
        log = "\n".join(f"line {i}" for i in range(80))
        (self.folder / "autoclicker.log").write_text(log, encoding="utf-8")
        (self.folder / "sessions.log").write_text("start\nstop\n", encoding="utf-8")
        text = self.report()
        self.assertIn(f"App version: {__version__}", text)
        self.assertIn("Monitors (2): 1920x1080 at (-1920, 0); 2560x1440 at (0, 0)", text)
        self.assertIn("line 79", text)
        self.assertNotIn("line 29\n", text)  # only the last 50 lines
        self.assertIn("stop", text)

    def test_nothing_personal_leaks(self):
        text = self.report()
        for secret in ("Bank login", "#123456", '"x": 20', "640"):
            self.assertNotIn(secret, text)

    def test_missing_logs(self):
        self.assertIn("(not found)", self.report())


class TestInfoDialog(unittest.TestCase):
    @patch("autoclicker.gui.info_dialog.ttk")
    @patch("autoclicker.gui.info_dialog.tk")
    def test_copy_previews_then_copies(self, tk_mod, _ttk):
        from autoclicker.gui.info_dialog import InfoDialog

        root = MagicMock()
        dialog = InfoDialog(root, "9.9.9", diagnostics=lambda: "REPORT")
        dialog.show_diagnostics()
        text_widget = tk_mod.Text.return_value
        text_widget.insert.assert_called_once_with("1.0", "REPORT")
        dialog.copy_to_clipboard("REPORT")
        root.clipboard_clear.assert_called_once()
        root.clipboard_append.assert_called_once_with("REPORT")

    def test_app_opens_the_dialog_with_current_values(self):
        from autoclicker.gui.main_window import AutoclickerApp

        app = AutoclickerApp.__new__(AutoclickerApp)
        app.root = MagicMock()
        app.settings = MagicMock()
        app.settings.get_all.return_value = {"interval": 1}
        with (
            patch.object(AutoclickerApp, "_collect_ui_settings", return_value={"interval": "250"}),
            patch("autoclicker.gui.features.info.InfoDialog") as dialog,
        ):
            app.show_info()
            report = dialog.call_args.kwargs["diagnostics"]()
        self.assertIn('"interval": "250"', report)
