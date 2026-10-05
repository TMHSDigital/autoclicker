# SPDX-License-Identifier: CC-BY-NC-4.0
"""Text styles whose colors follow the light/dark theme (#104).

ttk style settings belong to the current theme, so they are applied again
after every sv_ttk.set_theme. Each color meets WCAG AA (4.5:1) against the
sv_ttk background: #fafafa (light) and #1c1c1c (dark).
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

_log = logging.getLogger(__name__)

# Secondary text: hints, summaries, the footer.
MUTED = "Muted.TLabel"
# Inline error messages.
ERROR = "Error.TLabel"

TEXT_COLORS = {
    "light": {MUTED: "#57606a", ERROR: "#cf222e"},  # 6.1:1 and 5.1:1
    "dark": {MUTED: "#9198a1", ERROR: "#ff7b72"},  # 5.9:1 and 6.8:1
}


def apply_text_styles(theme: str, master: Any = None, *, style: Any = None) -> None:
    """Color the Muted and Error label styles for ``theme`` ("light" or "dark")."""
    colors = TEXT_COLORS.get(theme, TEXT_COLORS["light"])
    try:
        style = style if style is not None else ttk.Style(master)
        for name, color in colors.items():
            style.configure(name, foreground=color)
    except Exception:  # cosmetic; never block startup or a theme switch
        _log.debug("Could not apply text styles", exc_info=True)
