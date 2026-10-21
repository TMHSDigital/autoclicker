# SPDX-License-Identifier: CC-BY-NC-4.0
"""Short texts for the hero readouts and the collapsed panels.

Pure functions over the raw strings in the entries and variables, so they
run without Tk. Bad numbers never raise: they read as unset or as "?".
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

SEP = " · "  # middle dot between parts
DEFAULT_MAX_CPS = 50


class Stats(NamedTuple):
    clicks: str
    runtime: str
    rate: str


def _num(text: Any, default: float = 0) -> float:
    """``text`` as a number, or ``default`` when blank or not a number."""
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def _plain(value: float) -> str:
    """``100.0`` prints as ``100``; ``1.5`` stays ``1.5``."""
    return str(int(value)) if value == int(value) else f"{value:g}"


def format_stats(status: Mapping[str, Any]) -> Stats:
    """Tile values from ``ClickEngine.get_status()``."""
    clicks = f"{int(status.get('click_count', 0)):,}"
    runtime = str(status.get("runtime", "00:00:00"))
    perf = status.get("performance")
    rate = "--"
    if perf is not None:
        cps = float(perf.get("clicks_per_second", 0))
        if cps > 0 or status.get("is_running"):
            rate = f"{cps:.1f}/s"
    return Stats(clicks, runtime, rate)


def click_summary(
    *,
    mouse_button: str,
    click_type: str,
    action: str,
    interval: str,
    interval_unit: str,
    variation: str,
    hold_ms: str,
    key: str,
) -> str:
    """One line like ``Left click · every 100 ms ± 20 ms``."""
    button = (mouse_button or "left").lower()
    if action == "hold":
        what = f"Hold {button} {_plain(_num(hold_ms))} ms"
    elif action == "key":
        what = f"Press {key.strip() or '?'}"
    elif click_type == "double":
        what = f"Double {button} click"
    else:
        what = f"{button.capitalize()} click"

    unit = "s" if interval_unit == "seconds" else "ms"
    every = _num(interval, -1)
    every_text = _plain(every) if every >= 0 else "?"
    text = f"{what}{SEP}every {every_text} {unit}"
    jitter = _num(variation)
    if jitter > 0:
        text += f" ± {_plain(jitter)} ms"
    return text


def timing_summary(*, burst_clicks: str, burst_pause: str, start_delay: str, start_at: str) -> str:
    """Non-default Timing values, or ``no delay · no burst``."""
    parts: list[str] = []
    burst = int(_num(burst_clicks, 1))
    if burst > 1:
        parts.append(f"burst of {burst}, {_plain(_num(burst_pause))} ms apart")
    delay = _num(start_delay)
    if delay > 0:
        parts.append(f"{_plain(delay)} s delay")
    if start_at.strip():
        parts.append(f"at {start_at.strip()}")
    return SEP.join(parts) if parts else f"no delay{SEP}no burst"


def safety_summary(
    *,
    limit_clicks: bool,
    max_clicks: str,
    auto_stop_minutes: str,
    max_cps: str,
    condition: str,
    failsafe: bool,
    pause_unfocused: bool,
) -> str:
    """Safety values that matter at a glance, failsafe first."""
    parts = ["failsafe on" if failsafe else "failsafe off"]
    limits: list[str] = []
    clicks = int(_num(max_clicks)) if limit_clicks else 0
    if clicks > 0:
        limits.append(f"{clicks:,} clicks")
    minutes = _num(auto_stop_minutes)  # always live; only the click count has a toggle
    if minutes > 0:
        limits.append(f"{_plain(minutes)} min")
    parts.append("stop after " + " or ".join(limits) if limits else "no limit")
    cps = _num(max_cps, DEFAULT_MAX_CPS)
    if cps <= 0:
        parts.append("speed limit off")
    elif cps != DEFAULT_MAX_CPS:
        parts.append(f"max {_plain(cps)}/s")
    if condition == "wait":
        parts.append("wait for pixel")
    elif condition == "stop":
        parts.append("stop on pixel")
    if pause_unfocused:
        parts.append("pause when unfocused")
    return SEP.join(parts)
