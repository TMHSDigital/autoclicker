"""Command line and headless runs (#75)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyautogui

from autoclicker import cli
from autoclicker.cli import (
    EXIT_ALREADY_RUNNING,
    EXIT_EMERGENCY,
    EXIT_OK,
    EXIT_SAFETY,
    EXIT_USAGE,
    UsageError,
    build_overrides,
    has_overrides,
    parse_args,
)


def overrides(*argv, profiles=None):
    profiles = profiles or {}
    return build_overrides(parse_args(list(argv)), profiles.get)


class TestOverrides(unittest.TestCase):
    def test_target_and_timing_flags(self):
        values = overrides(
            "--at", "800, 600", "--interval", "2s", "--button", "right", "--double",
            "--burst", "3:50", "--clicks", "200", "--minutes", "5", "--delay", "0",
        )  # fmt: skip
        self.assertEqual(
            values,
            {
                "target_mode": "fixed",
                "x": "800",
                "y": "600",
                "interval": "2",
                "interval_unit": "seconds",
                "mouse_button": "right",
                "click_type": "double",
                "burst_clicks": "3",
                "burst_pause": "50",
                "max_clicks": "200",
                "auto_stop_minutes": "5",
                "start_delay_seconds": "0",
            },
        )

    def test_interval_defaults_to_ms(self):
        self.assertEqual(overrides("--interval", "150")["interval_unit"], "ms")
        self.assertEqual(overrides("--interval", "150ms")["interval"], "150")

    def test_modes(self):
        self.assertEqual(overrides("--cursor")["target_mode"], "cursor")
        self.assertEqual(overrides("--sequence", "--repeat", "4")["sequence_repeat"], "4")

    def test_profile_then_flags_on_top(self):
        profiles = {"Work": {"x": 1, "y": 2, "interval": 100, "mouse_button": "left"}}
        values = overrides("--profile", "Work", "--button", "middle", profiles=profiles)
        self.assertEqual(values["x"], 1)
        self.assertEqual(values["mouse_button"], "middle")

    def test_unusable_values(self):
        for argv in (
            ("--at", "800"),
            ("--interval", "fast"),
            ("--burst", "3"),
            ("--profile", "Missing"),
        ):
            with self.subTest(argv=argv), self.assertRaises(UsageError):
                overrides(*argv)

    def test_conflicting_flags_rejected_by_parser(self):
        with self.assertRaises(SystemExit):
            parse_args(["--at", "1,1", "--cursor"])

    def test_has_overrides(self):
        self.assertFalse(has_overrides(parse_args([])))
        self.assertFalse(has_overrides(parse_args(["--start", "--minimized"])))
        self.assertTrue(has_overrides(parse_args(["--clicks", "5"])))


class HeadlessCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        env = patch.dict(os.environ, {"APPDATA": self._dir.name})
        env.start()
        self.addCleanup(env.stop)
        cwd = os.getcwd()
        os.chdir(self._dir.name)
        self.addCleanup(os.chdir, cwd)

        for target, kwargs in (
            ("autoclicker.core.single_instance.SingleInstance.acquire", {"return_value": True}),
            ("autoclicker.app.hotkeys.HotkeyManager", {}),
        ):
            p = patch(target, **kwargs)
            setattr(self, target.rsplit(".", 1)[-1], p.start())
            self.addCleanup(p.stop)
        p = patch("autoclicker.core.click_engine.pyautogui")
        self.pyautogui = p.start()
        self.addCleanup(p.stop)
        self.pyautogui.size.return_value = (1920, 1080)
        self.pyautogui.FailSafeException = pyautogui.FailSafeException
        self.pyautogui.PyAutoGUIException = pyautogui.PyAutoGUIException
        p = patch("autoclicker.core.click_engine.monitor_rects", return_value=[])
        p.start()
        self.addCleanup(p.stop)

    def settings_path(self):
        return Path(self._dir.name, "WindowsAutoclicker", "autoclicker_settings.json")

    def run_cli(self, *argv):
        return cli.run_headless(parse_args(["--headless", *argv]))


class TestHeadless(HeadlessCase):
    def test_runs_to_completion_without_touching_saved_settings(self):
        code = self.run_cli("--at", "10,20", "--interval", "0ms", "--clicks", "3", "--delay", "0")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.pyautogui.click.call_count, 3)
        self.pyautogui.click.assert_called_with(x=10, y=20, button="left", clicks=1)
        saved = self.settings_path()
        if saved.exists():
            self.assertNotEqual(json.loads(saved.read_text("utf-8")).get("x_coord"), 10)
        hotkeys = self.HotkeyManager.return_value
        hotkeys.set_running.assert_called_with(True)
        hotkeys.unregister.assert_called_once()

    def test_bad_settings_exit_2(self):
        self.assertEqual(self.run_cli("--at", "99999,1", "--delay", "0"), EXIT_USAGE)
        self.assertEqual(self.run_cli("--interval", "nope"), EXIT_USAGE)
        self.pyautogui.click.assert_not_called()

    def test_already_running(self):
        self.acquire.return_value = False
        self.assertEqual(self.run_cli("--clicks", "1"), EXIT_ALREADY_RUNNING)

    def test_emergency_hotkey_exit_code(self):
        def emergency_on_first_click(**_kwargs):
            callbacks = self.HotkeyManager.call_args.args[0]
            callbacks["emergency"]()

        self.pyautogui.click.side_effect = emergency_on_first_click
        code = self.run_cli("--at", "10,10", "--interval", "0ms", "--delay", "0")
        self.assertEqual(code, EXIT_EMERGENCY)

    def test_terminal_is_excluded_from_focus_adoption(self):
        """#94: the window a headless run was typed into is never its target."""
        from autoclicker.core.click_engine import ClickEngine

        seen = []
        real_start = ClickEngine.start_clicking

        def spy(engine, *args, **kwargs):
            seen.append(engine.launcher_windows)
            return real_start(engine, *args, **kwargs)

        with (
            patch.object(cli, "_launcher_window", return_value=4242),
            patch.object(ClickEngine, "start_clicking", spy),
        ):
            code = self.run_cli(
                "--at", "10,10", "--interval", "0ms", "--clicks", "1", "--delay", "0"
            )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(seen, [frozenset({4242})])

    def test_launcher_window_needs_a_console(self):
        import ctypes

        with patch.object(ctypes.windll.kernel32, "GetConsoleWindow", return_value=0):
            self.assertIsNone(cli._launcher_window())
        with (
            patch.object(ctypes.windll.kernel32, "GetConsoleWindow", return_value=7),
            patch("autoclicker.core.safety.get_foreground_window_handle", return_value=99),
        ):
            self.assertEqual(cli._launcher_window(), 99)

    def test_failsafe_exit_code(self):
        self.pyautogui.click.side_effect = pyautogui.FailSafeException()
        code = self.run_cli("--at", "10,10", "--interval", "0ms", "--delay", "0")
        self.assertEqual(code, EXIT_SAFETY)


class TestMain(unittest.TestCase):
    def test_headless_dispatch(self):
        from autoclicker import main as main_mod

        with (
            patch.object(main_mod, "run_headless", return_value=4) as run,
            patch.object(main_mod, "configure_logging"),
        ):
            self.assertEqual(main_mod.main(["--headless", "--clicks", "1"]), 4)
        run.assert_called_once()

    def test_gui_launch_options(self):
        from autoclicker import main as main_mod

        app = MagicMock()
        app.preset_manager.load_profile.return_value = None
        args = parse_args(["--cursor", "--start", "--minimized"])
        main_mod._apply_launch_options(app, args)
        app.apply_form_values.assert_called_once_with({"target_mode": "cursor"})
        scheduled = [c.args[1] for c in app.root.after.call_args_list]
        self.assertEqual(scheduled, [app.hide_to_tray, app.start_from_button])

    def test_bad_gui_option_goes_to_the_status_bar(self):
        from autoclicker import main as main_mod

        app = MagicMock()
        main_mod._apply_launch_options(app, parse_args(["--interval", "soon", "--start"]))
        app.apply_form_values.assert_not_called()
        self.assertIn("Command line", app._set_status_message.call_args.args[0])
        app.root.after.assert_not_called()

    def test_windowed_exe_shows_help_in_a_dialog(self):
        from autoclicker import main as main_mod

        with (
            patch.object(main_mod.sys, "stdout", None),
            patch.object(main_mod, "_show_dialog") as dialog,
            self.assertRaises(SystemExit),
        ):
            main_mod._parse_args(["--help"])
        _title, text = dialog.call_args.args
        self.assertIn("--headless", text)
        self.assertFalse(dialog.call_args.kwargs["error"])
