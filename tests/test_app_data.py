"""App data folder and session-log rotation (#54)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoclicker.core import session_log
from autoclicker.core.app_data import app_data_dir


class TestAppDataDir(unittest.TestCase):
    def test_uses_appdata(self):
        with patch.dict(os.environ, {"APPDATA": r"C:\Users\x\AppData\Roaming"}):
            self.assertEqual(
                app_data_dir(), Path(r"C:\Users\x\AppData\Roaming") / "WindowsAutoclicker"
            )

    def test_missing_appdata_never_relative_to_cwd(self):
        with patch.dict(os.environ, {"APPDATA": ""}):
            path = app_data_dir()
        self.assertTrue(path.is_absolute())
        self.assertEqual(path, Path.home() / "AppData" / "Roaming" / "WindowsAutoclicker")


class TestSessionLogRotation(unittest.TestCase):
    def test_rotates_and_keeps_bounded_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "sessions.log"
            with (
                patch.object(session_log, "session_log_path", return_value=log_path),
                patch.object(session_log, "MAX_BYTES", 200),
            ):
                for i in range(60):
                    session_log.append_session_event("stop", reason="user_stop", n=i)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(
                names, ["sessions.log", "sessions.log.1", "sessions.log.2", "sessions.log.3"]
            )
            for p in Path(tmp).iterdir():
                self.assertLess(p.stat().st_size, 200 + 100)
            self.assertIn("n=59", log_path.read_text(encoding="utf-8"))

    def test_write_failure_never_raises(self):
        with patch.object(session_log, "session_log_path", side_effect=OSError("denied")):
            session_log.append_session_event("start")


if __name__ == "__main__":
    unittest.main()
