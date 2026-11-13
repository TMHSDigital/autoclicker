# SPDX-License-Identifier: CC-BY-NC-4.0
"""The settings a run reads, declared once (#169).

Each ``Field`` names a setting key, how its value is parsed, its default, its
label in error messages and whether a profile saves it. The settings manager,
the controller and profiles derive their key lists from ``FIELDS``, so a new
run setting is added here plus the widget that shows it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .image_match import DEFAULT_MARGIN
from .safety import DEFAULT_MAX_CPS

Kind = Literal["int", "float", "choice", "bool", "str", "list"]


@dataclass(frozen=True)
class Field:
    key: str
    kind: Kind
    default: Any
    # Name in validation errors; None falls back to the key, capitalised.
    label: str | None = None
    # True when a profile saves and restores it (the point x/y is saved separately).
    in_profile: bool = False
    choices: tuple[str, ...] = ()


# In the order a run reads them; PROFILE_KEYS keeps this order too.
FIELDS: tuple[Field, ...] = (
    Field("target_mode", "choice", "fixed", "Target", True,
          ("fixed", "cursor", "sequence", "image")),
    Field("x_coord", "int", 100, "X"),
    Field("y_coord", "int", 100, "Y"),
    Field("interval", "float", 1000, "Interval", True),
    Field("interval_unit", "choice", "ms", "Interval unit", True, ("ms", "seconds")),
    Field("variation", "int", 0, "Variation", True),
    Field("mouse_button", "choice", "left", "Mouse button", True, ("left", "right", "middle")),
    Field("click_type", "choice", "single", "Click type", True, ("single", "double")),
    Field("burst_clicks", "int", 1, "Burst clicks", True),
    Field("burst_pause", "float", 1000, "Burst pause", True),
    Field("max_clicks", "int", 0, "Limit clicks", True),
    Field("auto_stop_minutes", "int", 0, "Auto-stop", True),
    Field("enable_failsafe", "bool", True),
    Field("pause_when_unfocused", "bool", False, "Pause when unfocused"),
    Field("max_cps_ceiling", "int", DEFAULT_MAX_CPS, "Max clicks per second"),
    Field("start_delay_seconds", "int", 3, "Start delay"),
    Field("start_at", "str", "", "Start at"),
    Field("stop_at", "str", "", "Stop at"),
    Field("sequence", "list", [], "Sequence", True),
    Field("sequence_repeat", "int", 0, "Repeat", True),
    Field("action", "choice", "click", "Action", True, ("click", "hold", "key")),
    Field("hold_ms", "float", 500, "Hold", True),
    Field("key", "str", "", "Key", True),
    Field("condition", "choice", "none", "Only when", True, ("none", "wait", "stop")),
    Field("condition_x", "int", 0, "Watched pixel X", True),
    Field("condition_y", "int", 0, "Watched pixel Y", True),
    Field("condition_color", "str", "#000000", "Watched color", True),
    Field("condition_tolerance", "int", 16, "Color tolerance", True),
    Field("image_path", "str", "", "Image", True),
    Field("image_region", "list", [], "Image search area", True),
    Field("image_margin", "int", DEFAULT_MARGIN, "Search margin", True),
    Field("image_tolerance", "int", 0, "Image tolerance", True),
    # 0 = wait for the image as long as it takes (#174).
    Field("image_missing_stop_seconds", "int", 0, "Stop if the image is not seen for", True),
    Field("click_spread", "int", 0, "Spread", True),
)  # fmt: skip


def keys_of(kind: Kind) -> frozenset[str]:
    """The keys of every field of one kind."""
    return frozenset(f.key for f in FIELDS if f.kind == kind)


RUN_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS)
PROFILE_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS if f.in_profile)
CHOICES: dict[str, tuple[str, ...]] = {f.key: f.choices for f in FIELDS if f.kind == "choice"}
DEFAULTS: dict[str, Any] = {f.key: f.default for f in FIELDS}
LABELS: dict[str, str] = {f.key: f.label for f in FIELDS if f.label is not None}
