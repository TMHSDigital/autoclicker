"""Test helpers. Stub optional GUI deps so AutoclickerApp can be imported."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("sv_ttk", MagicMock())

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _primary_screen_only(monkeypatch):
    """Keep tests independent of the host's monitor layout.

    With the Win32 query disabled, desktop bounds fall back to the (usually
    mocked) ``pyautogui.size``. Tests that exercise multi-monitor bounds patch
    ``_query_virtual_screen`` themselves.
    """
    monkeypatch.setattr("autoclicker.core.screen._query_virtual_screen", lambda: None)


@pytest.fixture(autouse=True)
def _cursor_away_from_corners(monkeypatch):
    """The real cursor may rest in a corner of the host; tests that need it patch this."""
    monkeypatch.setattr("autoclicker.core.click_engine.cursor_position", lambda: None)


@pytest.fixture(autouse=True)
def _no_legacy_settings(request, monkeypatch, tmp_path_factory):
    """Legacy migration reads next to the app, i.e. the checkout; keep a developer's
    own autoclicker_settings.json there out of every test (#105)."""
    if request.node.get_closest_marker("real_legacy_dir"):
        return
    empty = tmp_path_factory.mktemp("legacy-app-dir")
    monkeypatch.setattr("autoclicker.core.settings_paths.legacy_app_dir", lambda: empty)
