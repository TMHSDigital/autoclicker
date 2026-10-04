# SPDX-License-Identifier: CC-BY-NC-4.0
"""Process DPI awareness.

Picking and clicking only line up if Tk, PyAutoGUI and the Win32 calls all
speak physical pixels. Per-monitor-v2 awareness makes that true on every
monitor, including mixed-DPI desktops where a system-aware process gets
scaled ("virtualized") coordinates on monitors whose scaling differs from the
primary one.

Awareness can be set only once per process, and PyAutoGUI sets the weaker
system-aware mode as a side effect of being imported, so this must run first.
"""

from __future__ import annotations

import ctypes
import logging
from typing import Any

_log = logging.getLogger(__name__)

# Pseudo-handle values from windef.h.
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
PROCESS_PER_MONITOR_DPI_AWARE = 2


def enable_per_monitor_dpi_awareness(windll: Any = None) -> str:
    """Opt into the best available DPI awareness. Returns the mode that was set.

    Tries per-monitor v2 (Windows 10 1703+), then per-monitor (8.1+), then
    system-aware (Vista+). Returns ``"unchanged"`` when every call fails, for
    example because awareness was already set for this process.
    """
    windll = windll if windll is not None else getattr(ctypes, "windll", None)
    if windll is None:
        return "unavailable"
    attempts = (
        (
            "per-monitor-v2",
            lambda: windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            ),
            lambda result: bool(result),
        ),
        (
            "per-monitor",
            lambda: windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE),
            lambda result: result == 0,  # S_OK
        ),
        (
            "system",
            lambda: windll.user32.SetProcessDPIAware(),
            lambda result: bool(result),
        ),
    )
    for mode, call, succeeded in attempts:
        try:
            if succeeded(call()):
                _log.debug("DPI awareness: %s", mode)
                return mode
        except (AttributeError, OSError):
            continue
    _log.debug("DPI awareness unchanged")
    return "unchanged"
