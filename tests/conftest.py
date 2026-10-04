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
