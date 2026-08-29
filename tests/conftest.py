"""Test helpers. Stub optional GUI deps so AutoclickerApp can be imported."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("sv_ttk", MagicMock())
