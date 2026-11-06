# SPDX-License-Identifier: CC-BY-NC-4.0
"""Deprecated alias for :mod:`autoclicker.utils.profiles` (renamed in 1.6.0).

Scheduled for removal in 2.0; import from ``autoclicker.utils.profiles``.
"""

from .profiles import (
    EXPORT_FORMAT,
    EXPORT_VERSION,
    PROFILE_KEYS,
    ImportResult,
    PresetManager,
    describe_profile,
)

__all__ = [
    "EXPORT_FORMAT",
    "EXPORT_VERSION",
    "PROFILE_KEYS",
    "ImportResult",
    "PresetManager",
    "describe_profile",
]
