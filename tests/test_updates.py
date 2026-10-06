"""Opt-in update check (#79)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core import updates
from autoclicker.core.updates import RELEASES_PAGE, Release, check_due, is_newer


class TestVersions(unittest.TestCase):
    def test_is_newer(self):
        self.assertTrue(is_newer("1.10.0", "1.9.9"))
        self.assertTrue(is_newer("v2.0.0", "1.99.0"))
        self.assertFalse(is_newer("1.5.0", "1.5.0"))
        self.assertFalse(is_newer("1.4.9", "1.5.0"))
        self.assertFalse(is_newer("nightly", "1.5.0"))

    def test_check_due(self):
        now = 1_000_000.0
        self.assertTrue(check_due(0, now))
        self.assertTrue(check_due(None, now))
        self.assertTrue(check_due("garbage", now))
        self.assertFalse(check_due(now - 3600, now))
        self.assertTrue(check_due(now - 25 * 3600, now))
        self.assertTrue(check_due(now + 3600, now))  # clock moved back: check again


class TestFetch(unittest.TestCase):
    def _response(self, payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__.return_value = response
        return response

    def test_reads_tag_and_page(self):
        payload = {
            "tag_name": "v1.6.0",
            "html_url": "https://github.com/TMHSDigital/autoclicker/releases/tag/v1.6.0",
        }
        with patch.object(updates.urllib.request, "urlopen", return_value=self._response(payload)):
            release = updates.fetch_latest_release()
        self.assertEqual(release, Release("1.6.0", payload["html_url"]))

    def test_only_this_repositorys_release_pages_are_opened(self):
        for url in (
            "file:///C:/Windows/System32/calc.exe",
            "https://github.com/someone-else/autoclicker/releases/tag/v9.9.9",
            "https://example.invalid/TMHSDigital/autoclicker/releases/",
            None,
            42,
        ):
            with self.subTest(url=url):
                payload = {"tag_name": "v9.9.9", "html_url": url}
                with patch.object(
                    updates.urllib.request, "urlopen", return_value=self._response(payload)
                ):
                    release = updates.fetch_latest_release()
                self.assertEqual(release, Release("9.9.9", RELEASES_PAGE))

    def test_failures_are_quiet(self):
        with patch.object(updates.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertIsNone(updates.fetch_latest_release())
        with patch.object(
            updates.urllib.request, "urlopen", return_value=self._response({"tag_name": "x"})
        ):
            self.assertIsNone(updates.fetch_latest_release())


def _app(choice, last_check=0):
    from autoclicker.gui.main_window import AutoclickerApp

    app = AutoclickerApp.__new__(AutoclickerApp)
    app.root = MagicMock()
    app.click_engine = MagicMock(is_running=False)
    app.check_updates_var = MagicMock()
    app.update_button = MagicMock()
    app.tray_icon = None
    # The fallback dialog only asks once the first-run hint is gone (#124).
    stored = {
        "check_for_updates": choice,
        "last_update_check": last_check,
        "first_run_hint_dismissed": True,
    }
    app.settings = MagicMock()
    app.settings.get.side_effect = lambda key, default=None: stored.get(key, default)
    app.settings.set.side_effect = stored.__setitem__
    app.stored = stored
    return app


class TestGuiUpdateCheck(unittest.TestCase):
    @patch("autoclicker.gui.features.updates.threading.Thread")
    @patch("autoclicker.gui.dialogs.messagebox")
    def test_off_makes_no_request(self, messagebox, thread):
        _app(False)._maybe_check_for_updates()
        thread.assert_not_called()
        messagebox.askyesno.assert_not_called()

    @patch("autoclicker.gui.features.updates.threading.Thread")
    @patch("autoclicker.gui.dialogs.messagebox")
    def test_asks_once_and_remembers_no(self, messagebox, thread):
        messagebox.askyesno.return_value = False
        app = _app(None)
        app._maybe_check_for_updates()
        self.assertIs(app.stored["check_for_updates"], False)
        thread.assert_not_called()
        app._maybe_check_for_updates()
        messagebox.askyesno.assert_called_once()

    @patch("autoclicker.gui.features.updates.threading.Thread")
    @patch("autoclicker.gui.dialogs.messagebox")
    def test_on_checks_at_most_daily_and_never_while_clicking(self, messagebox, thread):
        app = _app(None)
        app.click_engine.is_running = True
        app._maybe_check_for_updates()
        thread.assert_not_called()
        messagebox.askyesno.assert_not_called()  # no dialog over a run (#103)
        _delay, retry = app.root.after.call_args.args
        self.assertEqual(retry, app._maybe_check_for_updates)
        app.stored["check_for_updates"] = True
        app.click_engine.is_running = False
        app._maybe_check_for_updates()
        thread.assert_called_once()
        self._finish_check(app, Release("1.0.0", RELEASES_PAGE))
        app._maybe_check_for_updates()  # just checked
        thread.assert_called_once()

    @patch("autoclicker.gui.features.updates.threading.Thread")
    @patch("autoclicker.gui.dialogs.messagebox")
    def test_first_run_asks_in_the_hint_not_a_dialog(self, messagebox, thread):
        """#124: no modal on first launch; Got it records the hint's checkbox."""
        app = _app(None)
        app.stored["first_run_hint_dismissed"] = False
        app._maybe_check_for_updates()
        messagebox.askyesno.assert_not_called()
        thread.assert_not_called()
        app.first_run_hint = MagicMock()
        app.hint_updates_var = MagicMock()
        app.hint_updates_var.get.return_value = True
        app.dismiss_first_run_hint()
        self.assertIs(app.stored["check_for_updates"], True)
        app.check_updates_var.set.assert_called_with(True)
        thread.assert_called_once()  # checked right away
        messagebox.askyesno.assert_not_called()

    @patch("autoclicker.gui.features.updates.threading.Thread")
    def test_hint_left_unchecked_means_no(self, thread):
        app = _app(None)
        app.stored["first_run_hint_dismissed"] = False
        app.first_run_hint = MagicMock()
        app.hint_updates_var = MagicMock()
        app.hint_updates_var.get.return_value = False
        app.dismiss_first_run_hint()
        self.assertIs(app.stored["check_for_updates"], False)
        thread.assert_not_called()

    @patch("autoclicker.gui.features.updates.threading.Thread")
    def test_failed_check_is_retried_next_launch(self, thread):
        """#103: starting offline must not skip a day."""
        app = _app(True)
        self._finish_check(app, None)
        self.assertEqual(app.stored["last_update_check"], 0)
        app._maybe_check_for_updates()
        thread.assert_called_once()

    @staticmethod
    def _finish_check(app, release):
        app.root.after.reset_mock()
        with patch("autoclicker.gui.features.updates.fetch_latest_release", return_value=release):
            app._check_for_updates()
        for call in app.root.after.call_args_list:
            _delay, callback, *args = call.args
            callback(*args)

    def test_newer_version_shows_the_button(self):
        app = _app(True)
        self._finish_check(app, Release("9.9.9", "https://example.invalid/r"))
        app.update_button.grid.assert_called_once()
        self.assertIn("9.9.9", app.update_button.configure.call_args.kwargs["text"])
        with patch("autoclicker.gui.features.updates.webbrowser.open") as open_:
            app.open_release_page()
        open_.assert_called_once_with("https://example.invalid/r")
