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
import ctypes
import hashlib
import io
import sys
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class PreparedTemplate:
    """A template's RGB rows and its search anchor, worked out once per run (#97)."""

    width: int
    height: int
    rows: tuple[bytes, ...]
    anchor: int  # row with the most distinct colors

    @classmethod
    def from_image(cls, needle: Image.Image) -> PreparedTemplate:
        pin = needle.convert("RGB")
        width, height = pin.size
        data, stride = pin.tobytes(), width * 3
        rows = tuple(data[r * stride : (r + 1) * stride] for r in range(height))

        # Anchor on the row with the most distinct colors: a plain row (often
        # the first) would match almost everywhere and make the scan slow.
        def distinct_colors(r: int) -> int:
            return len({rows[r][i : i + 3] for i in range(0, stride, 3)})

        anchor = max(range(height), key=distinct_colors) if height else 0
        return cls(width, height, rows, anchor)


def find_template(
    haystack: Image.Image, needle: Image.Image | PreparedTemplate
) -> tuple[int, int] | None:
    """Top-left (x, y) of the first exact occurrence of ``needle`` in ``haystack``."""
    if not isinstance(needle, PreparedTemplate):
        needle = PreparedTemplate.from_image(needle)
    hay = haystack if haystack.mode == "RGB" else haystack.convert("RGB")
    hw, hh = hay.size
    nw, nh = needle.width, needle.height
    if nw == 0 or nh == 0 or nw > hw or nh > hh:
        return None
    hb = hay.tobytes()
    hrow, nrow = hw * 3, nw * 3
    rows, anchor = needle.rows, needle.anchor
    key = rows[anchor]
    last_x = (hw - nw) * 3  # furthest byte offset where the needle still fits
    for y in range(hh - nh + 1):
        top = y * hrow
        row = hb[top + anchor * hrow : top + (anchor + 1) * hrow]
        offset = row.find(key)
        while 0 <= offset <= last_x:
            if offset % 3 == 0 and all(
                hb[top + r * hrow + offset : top + r * hrow + offset + nrow] == rows[r]
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


_SRCCOPY = 0x00CC0020
_DIB_RGB_COLORS = 0


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


def _grab_region_win32(bounds: ScreenBounds) -> Image.Image | None:
    """Copy just ``bounds`` from the screen with BitBlt; None if that isn't possible.

    Pillow's all_screens grab copies the whole virtual desktop and then crops,
    which costs about 50 ms on a two-monitor desktop however small the region
    (#97). Coordinates are physical pixels (the process is per-monitor DPI aware)
    relative to the primary monitor, as GetDC(NULL) uses them.
    """
    if sys.platform != "win32" or bounds.width <= 0 or bounds.height <= 0:
        return None
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for fn in (user32.GetDC, gdi32.CreateCompatibleDC, gdi32.CreateCompatibleBitmap,
               gdi32.SelectObject):  # fmt: skip
        fn.restype = ctypes.c_void_p
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                             ctypes.c_uint32]  # fmt: skip
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]  # fmt: skip

    width, height = bounds.width, bounds.height
    screen = user32.GetDC(None)
    if not screen:
        return None
    memory = bitmap = old = None
    try:
        memory = gdi32.CreateCompatibleDC(screen)
        bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
        if not memory or not bitmap:
            return None
        old = gdi32.SelectObject(memory, bitmap)
        if not gdi32.BitBlt(memory, 0, 0, width, height, screen, bounds.left, bounds.top,
                            _SRCCOPY):  # fmt: skip
            return None
        header = _BitmapInfoHeader()
        header.biSize = ctypes.sizeof(_BitmapInfoHeader)
        header.biWidth = width
        header.biHeight = -height  # top-down rows
        header.biPlanes = 1
        header.biBitCount = 32
        buffer = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(memory, bitmap, 0, height, buffer, ctypes.byref(header),
                                _DIB_RGB_COLORS)  # fmt: skip
        if lines != height:
            return None
        return Image.frombuffer("RGB", (width, height), buffer.raw, "raw", "BGRX", 0, 1)
    finally:
        if memory and old:
            gdi32.SelectObject(memory, old)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory:
            gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)


def grab(bounds: ScreenBounds) -> Image.Image:
    """Screenshot of a desktop rectangle (absolute coordinates, any monitor)."""
    try:
        image = _grab_region_win32(bounds)
    except (AttributeError, OSError, ValueError):
        image = None
    if image is not None:
        return image
    return ImageGrab.grab(
        bbox=(bounds.left, bounds.top, bounds.right, bounds.bottom), all_screens=True
    )


@dataclass(frozen=True)
class ImageTarget:
    """Click the center of ``template`` wherever it appears inside ``region``."""

    template: Any  # PIL.Image.Image
    region: ScreenBounds
    prepared: PreparedTemplate = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "prepared", PreparedTemplate.from_image(self.template))

    def locate(self, grabber=grab) -> tuple[int, int] | None:
        """Screen coordinates of the template's center, or None if it isn't there."""
        found = find_template(grabber(self.region), self.prepared)
        if found is None:
            return None
        width, height = self.prepared.width, self.prepared.height
        return self.region.left + found[0] + width // 2, self.region.top + found[1] + height // 2
