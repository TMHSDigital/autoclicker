# SPDX-License-Identifier: CC-BY-NC-4.0
"""Opt-in check for a newer release on GitHub.

The only request is an anonymous GET of the public "latest release" API for
this repository; nothing is downloaded or installed and no data is sent
beyond what any HTTPS request carries. It runs only when the user has turned
it on, at most once a day.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)

REPOSITORY = "TMHSDigital/autoclicker"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Release:
    version: str
    url: str


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSION.match(text.strip())
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def is_newer(candidate: str, current: str) -> bool:
    new, old = parse_version(candidate), parse_version(current)
    return new is not None and old is not None and new > old


def check_due(last_check: Any, now: float | None = None) -> bool:
    """True if no check happened in the last CHECK_INTERVAL_SECONDS."""
    now = time.time() if now is None else now
    try:
        last = float(last_check)
    except (TypeError, ValueError):
        return True
    return not 0 <= now - last < CHECK_INTERVAL_SECONDS


def fetch_latest_release(timeout: float = 5.0) -> Release | None:
    """The latest published release, or None if it can't be read."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "WindowsAutoclicker"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        _log.debug("Update check failed: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name", ""))
    if parse_version(tag) is None:
        return None
    return Release(version=tag.lstrip("v"), url=str(data.get("html_url") or RELEASES_PAGE))


def newer_release(
    current: str, fetch: Callable[[], Release | None] = fetch_latest_release
) -> Release | None:
    """The latest release if it is newer than ``current``."""
    release = fetch()
    if release is not None and is_newer(release.version, current):
        return release
    return None
