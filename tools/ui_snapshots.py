# SPDX-License-Identifier: CC-BY-NC-4.0
"""Render the main window in set states and save PNGs, for checking UI changes by eye.

    python tools/ui_snapshots.py                 # every scenario, into build/ui-snapshots/
    python tools/ui_snapshots.py sequence image  # just these
    python tools/ui_snapshots.py --list

Safe to run on a desktop someone is using: each scenario runs in its own process
with a throwaway %APPDATA% (your settings and profiles are not read or written),
no global hotkeys, no tray icon, no update check and no clicks. The window is
fully transparent, click-through, off the taskbar and never activated, and is
captured with PrintWindow, so nothing visible pops up or takes focus.

Menus that Tk shows as native popups (the sequence step menu, the tray menu)
cannot be captured this way; their entries are written to ``menus.txt`` instead.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "ui-snapshots"

# System colors of Windows' "High Contrast Black" theme, by GetSysColor index
# (window, window text, highlight, highlight text, button face, gray text,
# button text, hot-tracked link).
_HC_BLACK = {
    5: "#000000",
    8: "#ffffff",
    13: "#1aebff",
    14: "#000000",
    15: "#000000",
    17: "#3ff23f",
    18: "#ffffff",
    26: "#ffff00",
}


def _hc_palette() -> dict[str, str]:
    """The app palette that real High Contrast Black produces (via system_palette)."""
    from autoclicker.gui import high_contrast

    def colorref(hex_color: str) -> int:
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
        return r | g << 8 | b << 16

    class _User32:
        @staticmethod
        def GetSysColor(index: int) -> int:
            return colorref(_HC_BLACK[index])

    from unittest import mock

    with mock.patch.object(high_contrast, "is_high_contrast", return_value=True):
        palette = high_contrast.system_palette(_User32())
    assert palette is not None
    return palette


_STEPS = [
    {"x": 120, "y": 340, "button": "left", "click_type": "single", "delay_ms": 500},
    {"x": 860, "y": 410, "button": "right", "click_type": "single", "delay_ms": 1500},
    {"x": 470, "y": 95, "button": "left", "click_type": "double", "delay_ms": 250},
]


def _expand_panels(app: Any) -> None:
    for panel in (app.timing_panel, app.safety_panel):
        if not panel.expanded:
            panel.toggle()


def _default(app: Any) -> None:
    app.apply_form_values({"target_mode": "fixed", "x": 640, "y": 360})


def _panels(app: Any) -> None:
    app.apply_form_values(
        {"target_mode": "fixed", "x": 640, "y": 360, "start_at": "08:30", "stop_at": "17:00"}
    )
    _expand_panels(app)


def _image(app: Any) -> None:
    app.apply_form_values({"target_mode": "image", "image_missing_stop_seconds": 30})


def _sequence(app: Any) -> None:
    app.apply_form_values({"target_mode": "sequence", "sequence": _STEPS, "sequence_repeat": 3})
    app.sequence_list.selection_set(1)
    app.sequence_list.event_generate("<<ListboxSelect>>")


def _sequence_steps(app: Any) -> None:
    """Click, key and hold steps in one sequence (#119)."""
    steps = [
        _STEPS[0],
        {"type": "key", "key": "ctrl+s", "delay_ms": 800},
        {"type": "hold", "x": 860, "y": 410, "button": "left", "hold_ms": 1200, "delay_ms": 300},
        _STEPS[2],
    ]
    app.apply_form_values({"target_mode": "sequence", "sequence": steps, "sequence_repeat": 0})


def _running(app: Any) -> None:
    app.apply_form_values({"target_mode": "fixed", "x": 640, "y": 360, "max_clicks": 200})
    status = {
        "is_running": True,
        "click_count": 57,
        "max_clicks": 200,
        "runtime": "00:01:10",
        "seconds_left": 1730,
        "performance": {"clicks_per_second": 9.8},
    }
    app.click_engine.get_status = lambda: status
    app._on_status_update()
    app._paint_run_mode("running")
    app._set_status_message("Running...", "running")


def _high_contrast(app: Any) -> None:
    _panels(app)


def _website(app: Any) -> None:
    """The window from the second launch on, for docs/images/screenshot-dark.png."""
    app.dismiss_first_run_hint()
    app.apply_form_values({"target_mode": "fixed", "x": 640, "y": 360, "interval": 250})


SCENARIOS: dict[str, tuple[str, Callable[[Any], None]]] = {
    "default": ("Fixed point, panels closed", _default),
    "panels": ("Timing and Safety open, Start at and Stop at set", _panels),
    "image": ("Image mode with Stop if not seen for", _image),
    "sequence": ("Sequence mode, three steps, one selected", _sequence),
    "sequence-steps": ("Sequence with click, key and hold steps", _sequence_steps),
    "running": ("A run with a click limit and time left", _running),
    "high-contrast": ("Panels open under a High Contrast palette", _high_contrast),
    "website": ("Fixed point, first-run hint dismissed (website screenshot)", _website),
}


def _quiet_tk() -> None:
    """Make every Tk root start withdrawn and fully transparent, so it never flashes up."""
    import tkinter

    original = tkinter.Tk.__init__

    def init(self: Any, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        self.withdraw()
        self.attributes("-alpha", 0.0)

    tkinter.Tk.__init__ = init  # type: ignore[method-assign]


def _show_invisibly(root: Any) -> None:
    """Map the window so Tk paints it, without it being seen, clicked or focused.

    It stays fully transparent (alpha 0), passes clicks through
    (WS_EX_TRANSPARENT), never activates (WS_EX_NOACTIVATE) and is kept off the
    taskbar and Alt+Tab (WS_EX_TOOLWINDOW).
    """
    import win32con
    import win32gui

    frame = int(root.wm_frame(), 16)
    style = win32gui.GetWindowLong(frame, win32con.GWL_EXSTYLE)
    style |= (
        win32con.WS_EX_LAYERED
        | win32con.WS_EX_TRANSPARENT
        | win32con.WS_EX_NOACTIVATE
        | win32con.WS_EX_TOOLWINDOW
    )
    win32gui.SetWindowLong(frame, win32con.GWL_EXSTYLE, style)
    win32gui.ShowWindow(frame, win32con.SW_SHOWNOACTIVATE)
    for _ in range(5):
        root.update_idletasks()
        root.update()


def _capture(root: Any, path: Path) -> None:
    """Grab the window's client area with PrintWindow (DWM content; alpha does not apply)."""
    import ctypes

    import win32gui
    import win32ui
    from PIL import Image

    hwnd = root.winfo_id()
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width, height = right - left, bottom - top
    window_dc = win32gui.GetWindowDC(hwnd)
    source = win32ui.CreateDCFromHandle(window_dc)
    memory = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source, width, height)
    memory.SelectObject(bitmap)
    try:
        # PW_CLIENTONLY | PW_RENDERFULLCONTENT
        if not ctypes.windll.user32.PrintWindow(hwnd, memory.GetSafeHdc(), 1 | 2):
            raise RuntimeError("PrintWindow failed")
        info = bitmap.GetInfo()
        data = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB", (info["bmWidth"], info["bmHeight"]), data, "raw", "BGRX", 0, 1
        )
        image.save(path)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory.DeleteDC()
        source.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def _menu_entries(menu: Any) -> list[str]:
    lines = []
    last = menu.index("end")
    for i in range(0 if last is None else last + 1):
        kind = menu.type(i)
        lines.append("  ----" if kind == "separator" else f"  {menu.entrycget(i, 'label')}")
    return lines


def _run_one(name: str, out: Path) -> None:
    """Build the app with every global side effect stubbed, apply a scenario, save it."""
    from unittest import mock

    sys.path.insert(0, str(ROOT))
    from autoclicker.core.dpi import enable_per_monitor_dpi_awareness

    enable_per_monitor_dpi_awareness()
    from autoclicker.app.hotkeys import HotkeyManager
    from autoclicker.gui import main_window, theme

    class _NoHotkeys(HotkeyManager):
        """Real bindings and labels; never starts the thread that registers keys."""

        def start(self, bindings: dict[str, str] | None = None) -> None:
            if bindings is not None:
                self._bindings = dict(bindings)

    patches = [
        mock.patch.object(main_window, "HotkeyManager", _NoHotkeys),
        mock.patch.object(main_window, "create_tray_icon", return_value=None),
        mock.patch.object(main_window.AutoclickerApp, "_maybe_check_for_updates"),
    ]
    if name == "high-contrast":
        patches.append(mock.patch.object(theme, "system_palette", return_value=_hc_palette()))
    for patch in patches:
        patch.start()

    import win32gui

    _quiet_tk()
    app = main_window.AutoclickerApp()
    root = app.root
    SCENARIOS[name][1](app)
    _show_invisibly(root)
    app._fit_to_content()  # Tk applies the fitted size only once the window is mapped
    for _ in range(5):
        root.update_idletasks()
        root.update()
    _capture(root, out / f"{name}.png")
    if win32gui.GetForegroundWindow() == int(root.wm_frame(), 16):
        print(f"{name}: warning: the snapshot window took the focus", file=sys.stderr)
    if name == "sequence":
        lines = ["Sequence step menu (step 2):", *_menu_entries(app._sequence_step_menu(1))]
        (out / "menus.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    app.click_engine.stop_clicking()
    root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenarios", nargs="*", help="names to render (default: all)")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    parser.add_argument("--out", type=Path, default=OUT, help=f"output folder (default {OUT})")
    parser.add_argument("--one", help=argparse.SUPPRESS)  # internal: render in this process
    args = parser.parse_args(argv)

    if args.list:
        for name, (description, _) in SCENARIOS.items():
            print(f"{name:15} {description}")
        return 0
    unknown = [
        n for n in [*args.scenarios, *([args.one] if args.one else [])] if n not in SCENARIOS
    ]
    if unknown:
        parser.error(f"unknown scenario(s): {', '.join(unknown)}; see --list")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.one:
        _run_one(args.one, args.out)
        return 0

    failed = 0
    for name in args.scenarios or list(SCENARIOS):
        # A process each: the theme palette is module state, and every app gets
        # its own fresh %APPDATA% so saved settings never leak in or out.
        with tempfile.TemporaryDirectory(prefix="autoclicker-ui-") as appdata:
            env = {**os.environ, "APPDATA": appdata}
            result = subprocess.run(
                [sys.executable, __file__, "--one", name, "--out", str(args.out)],
                env=env,
                cwd=ROOT,
            )
        if result.returncode:
            failed += 1
            print(f"{name}: failed", file=sys.stderr)
        else:
            print(args.out / f"{name}.png")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
