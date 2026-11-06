"""tools/ui_snapshots.py: scenario registry and argument handling (no window is built)."""

import importlib.util
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "tools" / "ui_snapshots.py"
_spec = importlib.util.spec_from_file_location("ui_snapshots", _PATH)
assert _spec is not None and _spec.loader is not None
ui_snapshots = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui_snapshots)


class TestUiSnapshots(unittest.TestCase):
    def test_scenarios_cover_the_main_views(self):
        for name in ("default", "panels", "image", "sequence", "running", "high-contrast"):
            self.assertIn(name, ui_snapshots.SCENARIOS)

    def test_list_prints_every_scenario(self):
        from contextlib import redirect_stdout
        from io import StringIO

        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(ui_snapshots.main(["--list"]), 0)
        for name in ui_snapshots.SCENARIOS:
            self.assertIn(name, out.getvalue())

    def test_unknown_scenario_is_a_usage_error(self):
        from contextlib import redirect_stderr
        from io import StringIO

        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            ui_snapshots.main(["nope"])
        self.assertEqual(raised.exception.code, 2)

    def test_high_contrast_palette_goes_through_the_real_mapping(self):
        palette = ui_snapshots._hc_palette()
        self.assertEqual(palette["bg"], "#000000")
        self.assertEqual(palette["text"], "#ffffff")
        self.assertEqual(palette["accent"], "#1aebff")


if __name__ == "__main__":
    unittest.main()
