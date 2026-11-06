"""Open data folder in the menu (#180)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoclicker.gui.main_window import AutoclickerApp


def _app():
    app = AutoclickerApp.__new__(AutoclickerApp)
    app._set_status_message = MagicMock()
    return app


class TestOpenDataFolder(unittest.TestCase):
    def test_opens_the_app_data_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp, "WindowsAutoclicker")
            with (
                patch("autoclicker.gui.features.info.app_data_dir", return_value=folder),
                patch("autoclicker.gui.features.info.os.startfile", create=True) as start,
            ):
                _app().open_data_folder()
            start.assert_called_once_with(folder)
            self.assertTrue(folder.is_dir())  # created first, so Explorer has something to open

    def test_failure_shows_in_the_status_line(self):
        app = _app()
        with (
            patch("autoclicker.gui.features.info.app_data_dir", return_value=Path(os.devnull)),
            patch(
                "autoclicker.gui.features.info.os.startfile",
                create=True,
                side_effect=OSError("no"),
            ),
            patch.object(Path, "mkdir"),
            self.assertLogs("autoclicker.gui.features.info", "WARNING"),
        ):
            app.open_data_folder()
        self.assertEqual(app._set_status_message.call_args.args[1], "error")

    def test_menu_has_the_item(self):
        source = Path(__file__).resolve().parent.parent / "autoclicker/gui/sections/header.py"
        self.assertIn(
            'label="Open data folder", command=app.open_data_folder', source.read_text("utf-8")
        )


if __name__ == "__main__":
    unittest.main()
