# SPDX-License-Identifier: CC-BY-NC-4.0
"""Find a captured image inside a small screen region (#87).

Matching is exact (same pixels) and limited to a region around where the
image was captured, which keeps it fast with plain Pillow: each row of the
region is searched for the template's first row with ``bytes.find`` (C speed),
and only those hits are checked row by row. No OpenCV or NumPy needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageGrab

from .screen import ScreenBounds

# Search this far around the captured image by default (pixels on each side).
DEFAULT_MARGIN = 150
MAX_MARGIN = 2000


def find_template(haystack: Image.Image, needle: Image.Image) -> tuple[int, int] | None:
    """Top-left (x, y) of the first exact occurrence of ``needle`` in ``haystack``."""
    hay = haystack.convert("RGB")
    pin = needle.convert("RGB")
    hw, hh = hay.size
    nw, nh = pin.size
    if nw == 0 or nh == 0 or nw > hw or nh > hh:
        return None
    hb, nb = hay.tobytes(), pin.tobytes()
    hrow, nrow = hw * 3, nw * 3

    # Anchor on the needle row with the most distinct colors: a plain row
    # (often the first) would match almost everywhere and make the scan slow.
    def distinct_colors(r: int) -> int:
        row = nb[r * nrow : (r + 1) * nrow]
        return len({row[i : i + 3] for i in range(0, nrow, 3)})

    anchor = max(range(nh), key=distinct_colors)
    key = nb[anchor * nrow : (anchor + 1) * nrow]
    last_x = (hw - nw) * 3  # furthest byte offset where the needle still fits
    for y in range(hh - nh + 1):
        top = y * hrow
        row = hb[top + anchor * hrow : top + (anchor + 1) * hrow]
        offset = row.find(key)
        while 0 <= offset <= last_x:
            if offset % 3 == 0 and all(
                hb[top + r * hrow + offset : top + r * hrow + offset + nrow]
                == nb[r * nrow : (r + 1) * nrow]
                for r in range(nh)
            ):
                return offset // 3, y
            offset = row.find(key, offset + 1)
    return None


def search_region(capture: ScreenBounds, margin: int, desktop: ScreenBounds) -> ScreenBounds:
    """The capture rectangle grown by ``margin`` on each side, clipped to the desktop."""
    left = max(desktop.left, capture.left - margin)
    top = max(desktop.top, capture.top - margin)
    right = min(desktop.right, capture.right + margin)
    bottom = min(desktop.bottom, capture.bottom + margin)
    return ScreenBounds(left, top, max(0, right - left), max(0, bottom - top))


def grab(bounds: ScreenBounds) -> Image.Image:
    """Screenshot of a desktop rectangle (absolute coordinates, any monitor)."""
    return ImageGrab.grab(
        bbox=(bounds.left, bounds.top, bounds.right, bounds.bottom), all_screens=True
    )


@dataclass(frozen=True)
class ImageTarget:
    """Click the center of ``template`` wherever it appears inside ``region``."""

    template: Any  # PIL.Image.Image
    region: ScreenBounds

    def locate(self, grabber=grab) -> tuple[int, int] | None:
        """Screen coordinates of the template's center, or None if it isn't there."""
        found = find_template(grabber(self.region), self.template)
        if found is None:
            return None
        width, height = self.template.size
        return self.region.left + found[0] + width // 2, self.region.top + found[1] + height // 2
