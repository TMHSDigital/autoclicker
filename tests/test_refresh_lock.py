"""The runtime lock is resolved from requirements.txt, never frozen from the dev venv (#108)."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

_SPEC = importlib.util.spec_from_file_location(
    "refresh_lock", Path(__file__).resolve().parent.parent / "tools" / "refresh_lock.py"
)
assert _SPEC and _SPEC.loader
refresh_lock = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(refresh_lock)


class TestCommands(unittest.TestCase):
    def test_runtime_lock_compiles_for_windows_and_the_release_python(self):
        command = refresh_lock.runtime_lock_command("uv")
        self.assertEqual(command[:3], ["uv", "pip", "compile"])
        self.assertIn(str(refresh_lock.REQUIREMENTS), command)
        self.assertEqual(command[command.index("--python-platform") + 1], "windows")
        self.assertEqual(command[command.index("--python-version") + 1], "3.11")
        self.assertEqual(command[command.index("-o") + 1], str(refresh_lock.LOCK_FILE))
        self.assertNotIn("freeze", command)
        self.assertNotIn("--upgrade", command)
        self.assertIn("--upgrade", refresh_lock.runtime_lock_command("uv", upgrade=True))

    def test_main_runs_both_or_only_dev(self):
        with (
            patch.object(refresh_lock.shutil, "which", return_value="uv"),
            patch.object(refresh_lock.subprocess, "run") as run,
        ):
            self.assertEqual(refresh_lock.main([]), 0)
            outputs = [c.args[0][c.args[0].index("-o") + 1] for c in run.call_args_list]
            self.assertEqual(
                outputs, [str(refresh_lock.LOCK_FILE), str(refresh_lock.DEV_LOCK_FILE)]
            )
            run.reset_mock()
            refresh_lock.main(["--dev"])
            self.assertEqual(run.call_count, 1)

    def test_needs_uv(self):
        with patch.object(refresh_lock.shutil, "which", return_value=None):
            self.assertEqual(refresh_lock.main([]), 1)

    def test_runtime_lock_has_only_runtime_packages(self):
        lock = Path(refresh_lock.LOCK_FILE).read_text("utf-8").lower()
        for tool in ("pytest", "ruff", "mypy", "pyinstaller", "-e ", "git+"):
            self.assertNotIn(tool, lock)


if __name__ == "__main__":
    unittest.main()
