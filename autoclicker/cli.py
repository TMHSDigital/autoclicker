# SPDX-License-Identifier: CC-BY-NC-4.0
"""Command-line options and the windowless (headless) run.

Flags override the saved settings for this launch. Without ``--headless`` they
are written into the window's form (so the user sees them) and ``--start``
presses Start. With ``--headless`` there is no window: the run uses the same
validation, hotkeys, corner failsafe and limits, then the process exits with a
code that says how the run ended. Headless runs never change saved settings.
"""

from __future__ import annotations

import argparse
import re
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from . import __version__
from .core.click_engine import (
    STOP_COMPLETED,
    STOP_EMERGENCY,
    STOP_ERROR,
    STOP_SAFETY,
    STOP_USER,
    RunOutcome,
)

# Process exit codes for --headless.
EXIT_OK = 0  # completed, or stopped with the Stop key
EXIT_USAGE = 2  # bad flags or settings
EXIT_EMERGENCY = 3
EXIT_SAFETY = 4  # corner failsafe or runaway guard
EXIT_ERROR = 5
EXIT_ALREADY_RUNNING = 6

EXIT_CODES = {
    STOP_COMPLETED: EXIT_OK,
    STOP_USER: EXIT_OK,
    STOP_EMERGENCY: EXIT_EMERGENCY,
    STOP_SAFETY: EXIT_SAFETY,
    STOP_ERROR: EXIT_ERROR,
}

_INTERVAL = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s)?\s*$", re.IGNORECASE)


class UsageError(ValueError):
    """A flag value that can't be used."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoclicker",
        description=(
            "Windows Autoclicker. Flags override the saved settings for this launch; "
            "without --headless they fill in the window."
        ),
        epilog=(
            "Examples:\n"
            "  autoclicker --cursor --interval 50ms --clicks 200 --start\n"
            "  autoclicker --profile Work --headless\n"
            "Headless exit codes: 0 done or stopped, 2 bad options, 3 emergency stop,\n"
            "4 failsafe or runaway guard, 5 error, 6 already running."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--at", metavar="X,Y", help="click this point (fixed location)")
    target.add_argument("--cursor", action="store_true", help="click wherever the cursor is")
    target.add_argument(
        "--sequence", action="store_true", help="click the saved sequence of points"
    )
    parser.add_argument("--profile", metavar="NAME", help="load a saved profile first")
    parser.add_argument(
        "--interval", metavar="TIME", help="wait between clicks or bursts, e.g. 100ms or 2s"
    )
    parser.add_argument("--variation", metavar="MS", help="random +/- milliseconds per interval")
    parser.add_argument("--button", choices=("left", "right", "middle"))
    clicks = parser.add_mutually_exclusive_group()
    clicks.add_argument("--double", action="store_true", help="double click")
    clicks.add_argument("--single", action="store_true", help="single click")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--hold", metavar="MS", help="hold the button for MS instead of clicking")
    action.add_argument("--key", metavar="KEY", help="press a key instead, e.g. f5 or ctrl+r")
    parser.add_argument("--burst", metavar="N:MS", help="N clicks per burst, MS apart")
    parser.add_argument("--clicks", metavar="N", help="stop after N clicks")
    parser.add_argument("--minutes", metavar="N", help="stop after N minutes")
    parser.add_argument("--repeat", metavar="N", help="sequence rounds (0 = until stopped)")
    parser.add_argument("--delay", metavar="SECONDS", help="countdown before clicking starts")
    parser.add_argument("--start", action="store_true", help="start clicking after launch")
    parser.add_argument("--minimized", action="store_true", help="start hidden in the tray")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="no window: run once with the given settings, then exit (implies --start)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def has_overrides(args: argparse.Namespace) -> bool:
    keys = (
        "at", "cursor", "sequence", "profile", "interval", "variation", "button", "double",
        "single", "burst", "clicks", "minutes", "repeat", "delay", "hold", "key",
    )  # fmt: skip
    return any(getattr(args, key) for key in keys)


def build_overrides(args: argparse.Namespace, load_profile: Callable[[str], Any]) -> dict:
    """Form values from the flags, shaped like a profile (``x``/``y`` for the point).

    Raises UsageError for values that can't be read. Range checks happen in the
    normal settings validation.
    """
    values: dict[str, Any] = {}
    if args.profile:
        profile = load_profile(args.profile)
        if profile is None:
            raise UsageError(f"No profile named {args.profile!r}")
        values.update(profile)
    if args.at:
        parts = [p.strip() for p in args.at.split(",")]
        if len(parts) != 2:
            raise UsageError("--at needs X,Y, for example --at 800,600")
        values.update(target_mode="fixed", x=parts[0], y=parts[1])
    if args.cursor:
        values["target_mode"] = "cursor"
    if args.sequence:
        values["target_mode"] = "sequence"
    if args.interval:
        match = _INTERVAL.match(args.interval)
        if not match:
            raise UsageError("--interval needs a number with ms or s, for example 100ms or 2s")
        number, unit = match.groups()
        values["interval"] = number
        values["interval_unit"] = "seconds" if (unit or "ms").lower() == "s" else "ms"
    if args.burst:
        parts = [p.strip() for p in args.burst.split(":")]
        if len(parts) != 2:
            raise UsageError("--burst needs N:MS, for example --burst 3:50")
        values.update(burst_clicks=parts[0], burst_pause=parts[1])
    simple = {
        "variation": "variation",
        "button": "mouse_button",
        "clicks": "max_clicks",
        "minutes": "auto_stop_minutes",
        "repeat": "sequence_repeat",
        "delay": "start_delay_seconds",
    }
    for flag, key in simple.items():
        value = getattr(args, flag)
        if value is not None:
            values[key] = value
    if args.hold is not None:
        values.update(action="hold", hold_ms=args.hold)
    if args.key is not None:
        values.update(action="key", key=args.key)
    if args.double:
        values["click_type"] = "double"
    if args.single:
        values["click_type"] = "single"
    return values


def _to_raw(saved: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Saved settings overlaid with profile-shaped overrides, as raw settings keys."""
    raw = dict(saved)
    for key, value in overrides.items():
        raw[{"x": "x_coord", "y": "y_coord"}.get(key, key)] = value
    return raw


def _emit(text: str, *, error: bool = False) -> None:
    """Print to the console; the windowed exe has none, so nothing is lost by trying."""
    stream = sys.stderr if error else sys.stdout
    if stream is not None:
        print(text, file=stream, flush=True)


def run_headless(args: argparse.Namespace) -> int:
    """Run once without a window and return the process exit code."""
    from .app.controller import AutoclickerController
    from .app.hotkeys import DEFAULT_HOTKEYS, HotkeyError, HotkeyManager, validate_bindings
    from .core.settings_manager import field_label
    from .core.single_instance import SingleInstance

    instance = SingleInstance()
    if not instance.acquire():
        _emit("Windows Autoclicker is already running; close it first.", error=True)
        return EXIT_ALREADY_RUNNING

    controller = AutoclickerController()
    try:
        overrides = build_overrides(args, controller.preset_manager.load_profile)
    except UsageError as e:
        _emit(f"autoclicker: {e}", error=True)
        return EXIT_USAGE

    raw = _to_raw(controller.settings.get_all(), overrides)
    result = controller.validate(raw)
    if not result["valid"]:
        for field, message in result["errors"].items():
            _emit(f"autoclicker: {field_label(field)}: {message}", error=True)
        return EXIT_USAGE

    try:
        delay = int(result["sanitized_settings"].get("start_delay_seconds", 0))
    except (TypeError, ValueError):
        delay = 0
    for remaining in range(delay, 0, -1):
        _emit(f"Starting in {remaining}... (Ctrl+C to cancel)")
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            _emit("Cancelled.")
            return EXIT_OK

    done = threading.Event()
    outcomes: list[RunOutcome] = []

    def finished(outcome: RunOutcome) -> None:
        outcomes.append(outcome)
        done.set()

    try:
        bindings = validate_bindings(dict(controller.settings.get("hotkeys") or {}))
    except (HotkeyError, TypeError, ValueError):
        bindings = dict(DEFAULT_HOTKEYS)

    def stop() -> None:
        controller.stop_clicking()

    def emergency() -> None:
        controller.emergency_stop()

    hotkeys = HotkeyManager(
        {"start": lambda: None, "stop": stop, "emergency": emergency, "toggle": stop},
        on_error=lambda message: _emit(message, error=True),
    )

    started = controller.validate_and_start_clicking(
        raw,
        failsafe=bool(result["sanitized_settings"].get("enable_failsafe", True)),
        pause_when_unfocused=bool(result["sanitized_settings"].get("pause_when_unfocused", False)),
        on_finished=finished,
        persist=False,
    )
    if not started.success:
        for field, message in (started.validation_errors or {}).items():
            _emit(f"autoclicker: {field_label(field)}: {message}", error=True)
        return EXIT_USAGE

    hotkeys.start(bindings)
    hotkeys.set_running(True)
    stop_keys = ", ".join(k for k in (bindings.get("stop"), bindings.get("emergency")) if k)
    _emit(f"Clicking. Press {stop_keys} (or Ctrl+C) to stop.")
    try:
        while not done.wait(0.2):
            pass
    except KeyboardInterrupt:
        controller.emergency_stop()
        done.wait(2)
    finally:
        hotkeys.unregister()
        controller.finish_run()

    outcome = outcomes[0] if outcomes else RunOutcome(STOP_ERROR, "No result", 0)
    _emit(f"{outcome.message} ({outcome.clicks:,} clicks)")
    return EXIT_CODES.get(outcome.reason, EXIT_ERROR)
