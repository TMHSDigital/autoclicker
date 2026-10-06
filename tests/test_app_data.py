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


class TestPortableMode(unittest.TestCase):
    """#122: portable.txt next to the exe keeps everything in a data folder beside it."""

    def _frozen(self, exe_dir):
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch("autoclicker.core.app_data.sys.frozen", True, create=True))
        stack.enter_context(
            patch("autoclicker.core.app_data.sys.executable", str(Path(exe_dir, "app.exe")))
        )
        return stack

    def test_marker_next_to_the_exe(self):
        with tempfile.TemporaryDirectory() as exe_dir:
            Path(exe_dir, "portable.txt").write_text("", encoding="utf-8")
            with self._frozen(exe_dir), patch.dict(os.environ, {"APPDATA": r"C:\elsewhere"}):
                self.assertEqual(app_data_dir(), Path(exe_dir).resolve() / "data")

    def test_without_marker_uses_appdata(self):
        with (
            tempfile.TemporaryDirectory() as exe_dir,
            self._frozen(exe_dir),
            patch.dict(os.environ, {"APPDATA": r"C:\Roaming"}),
        ):
            self.assertEqual(app_data_dir(), Path(r"C:\Roaming") / "WindowsAutoclicker")

    def test_source_runs_are_never_portable(self):
        from autoclicker.core import app_data

        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "portable.txt").write_text("", encoding="utf-8")
            with patch.object(app_data, "app_dir", return_value=Path(folder)):
                self.assertIsNone(app_data.portable_data_dir())
