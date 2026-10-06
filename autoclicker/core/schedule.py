# SPDX-License-Identifier: CC-BY-NC-4.0
"""Start at a time of day (#121)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_HH_MM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_start_at(text: str) -> tuple[int, int] | None:
    """``"9:30"`` or ``"09:30"`` (24-hour) as (hour, minute); None if it isn't one."""
    match = _HH_MM.match(text.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def next_start(hour: int, minute: int, now: datetime) -> datetime:
    """The next time the clock shows hour:minute: today, or tomorrow if that has passed."""
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def describe_wait(seconds: float) -> str:
    """``2:05:09`` or ``5:09`` for a countdown label."""
    seconds = max(0, int(seconds + 0.999))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
