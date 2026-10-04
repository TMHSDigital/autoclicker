"""Opt-in update check (#79)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core import updates
from autoclicker.core.updates import Release, check_due, is_newer, newer_release


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

    def test_newer_release(self):
        found = Release("9.0.0", "https://example.invalid/r")
        self.assertEqual(newer_release("1.0.0", lambda: found), found)
        self.assertIsNone(newer_release("9.0.0", lambda: found))
        self.assertIsNone(newer_release("1.0.0", lambda: None))


class TestFetch(unittest.TestCase):
    def _response(self, payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__.return_value = response
        return response

    def test_reads_tag_and_page(self):
        payload = {"tag_name": "v1.6.0", "html_url": "https://github.com/x/releases/tag/v1.6.0"}
        with patch.object(updates.urllib.request, "urlopen", return_value=self._response(payload)):
            release = updates.fetch_latest_release()
        self.assertEqual(release, Release("1.6.0", payload["html_url"]))

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
    stored = {"check_for_updates": choice, "last_update_check": last_check}
    app.settings = MagicMock()
    app.settings.get.side_effect = lambda key, default=None: stored.get(key, default)
    app.settings.set.side_effect = stored.__setitem__
    app.stored = stored
    return app


class TestGuiUpdateCheck(unittest.TestCase):
    @patch("autoclicker.gui.main_window.threading.Thread")
    @patch("autoclicker.gui.main_window.messagebox")
    def test_off_makes_no_request(self, messagebox, thread):
        _app(False)._maybe_check_for_updates()
        thread.assert_not_called()
        messagebox.askyesno.assert_not_called()

    @patch("autoclicker.gui.main_window.threading.Thread")
    @patch("autoclicker.gui.main_window.messagebox")
    def test_asks_once_and_remembers_no(self, messagebox, thread):
        messagebox.askyesno.return_value = False
        app = _app(None)
        app._maybe_check_for_updates()
        self.assertIs(app.stored["check_for_updates"], False)
        thread.assert_not_called()
        app._maybe_check_for_updates()
        messagebox.askyesno.assert_called_once()

    @patch("autoclicker.gui.main_window.threading.Thread")
    @patch("autoclicker.gui.main_window.messagebox")
    def test_on_checks_at_most_daily_and_never_while_clicking(self, _messagebox, thread):
        app = _app(True)
        app.click_engine.is_running = True
        app._maybe_check_for_updates()
        thread.assert_not_called()
        app.click_engine.is_running = False
        app._maybe_check_for_updates()
        thread.assert_called_once()
        app._maybe_check_for_updates()  # just checked
        thread.assert_called_once()

    def test_newer_version_shows_the_button(self):
        app = _app(True)
        with patch(
            "autoclicker.gui.main_window.newer_release",
            return_value=Release("9.9.9", "https://example.invalid/r"),
        ):
            app._check_for_updates()
        _delay, callback = app.root.after.call_args.args
        callback()
        app.update_button.grid.assert_called_once()
        self.assertIn("9.9.9", app.update_button.configure.call_args.kwargs["text"])
        with patch("autoclicker.gui.main_window.webbrowser.open") as open_:
            app.open_release_page()
        open_.assert_called_once_with("https://example.invalid/r")
