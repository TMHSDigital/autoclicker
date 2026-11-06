"""--list-profiles, profile names in the not-found error, and --json results (#176)."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from autoclicker import cli
from autoclicker.cli import EXIT_OK, EXIT_USAGE, parse_args
from tests.test_cli import HeadlessCase


class TestJsonResult(HeadlessCase):
    def run_json(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.run_cli(*argv, "--json")
        return code, out.getvalue(), err.getvalue()

    def test_completed_run_prints_one_json_object_on_stdout(self):
        code, out, err = self.run_json(
            "--at", "10,20", "--interval", "0ms", "--clicks", "3", "--delay", "0"
        )
        self.assertEqual(code, EXIT_OK)
        result = json.loads(out)
        self.assertEqual(set(result), {"reason", "message", "clicks", "seconds", "exit_code"})
        self.assertEqual(result["reason"], "completed")
        self.assertEqual(result["clicks"], 3)
        self.assertEqual(result["exit_code"], EXIT_OK)
        self.assertGreaterEqual(result["seconds"], 0)
        self.assertIn("Clicking.", err)  # progress goes to stderr

    def test_bad_options_are_reported_as_json_too(self):
        code, out, _err = self.run_json("--at", "99999,1", "--delay", "0")
        self.assertEqual(code, EXIT_USAGE)
        result = json.loads(out)
        self.assertEqual(result["reason"], "usage")
        self.assertEqual(result["exit_code"], EXIT_USAGE)
        self.assertEqual(result["clicks"], 0)

    def test_without_json_stdout_has_no_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.run_cli("--at", "10,20", "--interval", "0ms", "--clicks", "1", "--delay", "0")
        self.assertNotIn("{", out.getvalue())


class TestProfiles(HeadlessCase):
    def save(self, *names):
        from autoclicker.core.settings_manager import SettingsManager
        from autoclicker.utils.profiles import PresetManager

        manager = PresetManager(SettingsManager())
        for name in names:
            manager.save_profile(name, {"x": 5, "y": 6, "interval": "100"})

    def test_unknown_profile_names_the_saved_ones(self):
        self.save("Work", "alpha")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.run_cli("--profile", "Nope"), EXIT_USAGE)
        self.assertIn("No profile named 'Nope'. Saved profiles: alpha, Work", err.getvalue())

    def test_unknown_profile_with_none_saved(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.run_cli("--profile", "Nope")
        self.assertIn("there are no saved profiles", err.getvalue())

    def test_listing(self):
        self.assertEqual(cli.profile_listing(), "No saved profiles.")
        self.save("Work", "alpha")
        lines = cli.profile_listing().splitlines()
        self.assertEqual([line.split(":")[0] for line in lines], ["alpha", "Work"])
        self.assertIn("(5, 6)", lines[0])

    def test_main_prints_the_listing_and_exits_0(self):
        from autoclicker import main as main_module

        self.save("Work")
        out = io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            patch.object(main_module, "configure_logging"),
            patch.object(main_module, "AutoclickerApp") as app,
        ):
            self.assertEqual(main_module.main(["--list-profiles"]), 0)
        self.assertTrue(out.getvalue().startswith("Work: "))
        app.assert_not_called()

    def test_flags_parse(self):
        args = parse_args(["--list-profiles"])
        self.assertTrue(args.list_profiles)
        self.assertTrue(parse_args(["--headless", "--json"]).json)


if __name__ == "__main__":
    unittest.main()
