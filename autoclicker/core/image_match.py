# SPDX-License-Identifier: CC-BY-NC-4.0
"""Find a captured image inside a small screen region (#87).

Matching is exact (same pixels) and limited to a region around where the
image was captured, which keeps it fast with plain Pillow: each row of the
region is searched for the template's first row with ``bytes.find`` (C speed),
and only those hits are checked row by row. No OpenCV or NumPy needed.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from PIL import Image, ImageGrab

from .app_data import app_data_dir
from .screen import ScreenBounds

# Search this far around the captured image by default (pixels on each side).
DEFAULT_MARGIN = 150
MAX_MARGIN = 2000
# Largest template accepted from a file: an 8K screen. Bigger is not a capture.
MAX_TEMPLATE_PIXELS = 7680 * 4320
# Largest base64 image accepted from an imported profile (characters).
MAX_EMBEDDED_IMAGE_CHARS = 24 * 1024 * 1024


def images_dir() -> Path:
    """Folder that holds captured and imported images."""
    return app_data_dir() / "images"


def open_template(source: str | Path | IO[bytes]) -> Image.Image:
    """Load a template image as RGB. Raises ValueError for anything unusable."""
    try:
        with Image.open(source) as image:
            width, height = image.size
            if width * height > MAX_TEMPLATE_PIXELS:
                raise ValueError("The image is too large")
            return image.convert("RGB")
    except ValueError:
        raise
    except Exception as e:  # OSError, Image.DecompressionBombError, truncated files
        raise ValueError(f"Unreadable image: {e}") from e


def encode_image(path: str | Path) -> str:
    """A PNG file as base64 text, for embedding in a profiles export."""
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def store_embedded_image(data: Any) -> str:
    """Decode a base64 PNG from an imported profile into images_dir(); returns its path.

    The image is re-encoded by Pillow, so only pixels are kept. Raises ValueError
    if it isn't a usable PNG. Files are named by content, so importing the same
    profile twice reuses one file.
    """
    if not isinstance(data, str) or len(data) > MAX_EMBEDDED_IMAGE_CHARS:
        raise ValueError("The embedded image is missing or too large")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError("The embedded image is not valid base64") from e
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format != "PNG":
                raise ValueError("The embedded image is not a PNG")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Unreadable image: {e}") from e
    template = open_template(io.BytesIO(raw))
    folder = images_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"imported-{hashlib.sha256(raw).hexdigest()[:16]}.png"
    if not path.is_file():
        template.save(path, format="PNG")
    return str(path)


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
