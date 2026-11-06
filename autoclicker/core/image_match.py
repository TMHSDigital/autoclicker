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
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from PIL import Image, ImageChops, ImageGrab

from .app_data import app_data_dir
from .screen import ScreenBounds

# Search this far around the captured image by default (pixels on each side).
DEFAULT_MARGIN = 150
MAX_MARGIN = 2000
# Largest template accepted from a file: an 8K screen. Bigger is not a capture.
MAX_TEMPLATE_PIXELS = 7680 * 4320
# Most candidate positions compared in full per tolerant search, so a template
# whose probe colors are everywhere can't stall the watcher (#123).
_MAX_TOLERANT_CHECKS = 2000
# Largest base64 image accepted from an imported profile (characters).
MAX_EMBEDDED_IMAGE_CHARS = 24 * 1024 * 1024

# The app only ever writes PNG templates (captures and imports), so only the PNG
# decoder runs on template files and shared profile images (#157).
TEMPLATE_FORMATS = ("PNG",)


def images_dir() -> Path:
    """Folder that holds captured and imported images."""
    return app_data_dir() / "images"


def is_app_image(path: str | Path) -> bool:
    """True if ``path`` names a file directly inside images_dir().

    Captures and imported images always land there, so a stored path anywhere
    else (a hand-edited or copied settings file) is never opened. Checked on
    the text alone: resolving or opening a path elsewhere could make Windows
    connect to another computer (#98).
    """
    text = str(path or "")
    if not text.strip():
        return False
    folder = os.path.normcase(os.path.normpath(str(images_dir())))
    candidate = os.path.normcase(os.path.normpath(text))
    return os.path.dirname(candidate) == folder and os.path.basename(candidate) not in ("", ".")


def open_template(source: str | Path | IO[bytes]) -> Image.Image:
    """Load a template image as RGB. Raises ValueError for anything unusable."""
    try:
        with Image.open(source, formats=TEMPLATE_FORMATS) as image:
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
        with Image.open(io.BytesIO(raw), formats=TEMPLATE_FORMATS):
            pass
    except Exception as e:  # UnidentifiedImageError for anything but a PNG
        raise ValueError("The embedded image is not a PNG") from e
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
    image: Any = field(repr=False, compare=False)  # the RGB template
    # Up to four (x, y, rgb) pixels with rare colors, one per quadrant, used to
    # find candidates quickly when matching with a tolerance (#123).
    probes: tuple[tuple[int, int, tuple[int, int, int]], ...] = ()

    @classmethod
    def from_image(cls, needle: Image.Image) -> PreparedTemplate:
        """Rows, anchor and probes, counted with Pillow's C code (#162).

        Python loops over every pixel took about 2 s for a full-screen capture,
        on the Tk thread at every Start.
        """
        pin = needle.convert("RGB")
        width, height = pin.size
        data, stride = pin.tobytes(), width * 3
        rows = tuple(data[r * stride : (r + 1) * stride] for r in range(height))

        # Anchor on the row with the most distinct colors: a plain row (often
        # the first) would match almost everywhere and make the scan slow.
        def distinct_colors(r: int) -> int:
            return len(pin.crop((0, r, width, r + 1)).getcolors(width) or ())

        anchor = max(range(height), key=distinct_colors) if height else 0
        return cls(width, height, rows, anchor, pin, _probes(pin))


def _probes(pin: Image.Image) -> tuple[tuple[int, int, tuple[int, int, int]], ...]:
    """The rarest-colored pixel of each quadrant: few places on screen share it.

    Ordered rarest first, so the tolerant search starts with the most selective one.
    """
    width, height = pin.size
    if width == 0 or height == 0:
        return ()
    Color = tuple[int, int, int]
    colors: list[tuple[int, Color]] = pin.getcolors(width * height) or []  # type: ignore[assignment, unused-ignore]
    counts = {color: count for count, color in colors}
    half_w, half_h = max(1, (width + 1) // 2), max(1, (height + 1) // 2)
    probes: list[tuple[int, int, tuple[int, int, int]]] = []
    for x0, y0 in ((0, 0), (half_w, 0), (0, half_h), (half_w, half_h)):
        box = (x0, y0, min(width, x0 + half_w), min(height, y0 + half_h))
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        quadrant = pin.crop(box)
        in_quadrant: list[tuple[int, Color]] = quadrant.getcolors(width * height) or []  # type: ignore[assignment, unused-ignore]
        ranked = sorted((counts[c], c) for _n, c in in_quadrant)
        # Prefer a color no other probe uses: a second probe of the same color
        # narrows the candidates far less than a different color does.
        used = {probe[2] for probe in probes}
        color = next((c for _n, c in ranked if c not in used), ranked[0][1])
        x, y = _first_pixel(quadrant, color)
        probe = (x0 + x, y0 + y, color)
        if probe not in probes:
            probes.append(probe)
    return tuple(sorted(probes, key=lambda p: counts[p[2]]))


def _first_pixel(image: Image.Image, color: tuple[int, int, int]) -> tuple[int, int]:
    """(x, y) of the first pixel of ``color`` in row-major order (it must be present)."""
    data, key, width = image.tobytes(), bytes(color), image.size[0]
    index = data.find(key)
    while index % 3:  # a match straddling two pixels
        index = data.find(key, index + 1)
    return (index // 3) % width, (index // 3) // width


# Below this many candidate positions, checking each one directly is cheaper
# than building another probe mask over the whole region (#161).
_FEW_CANDIDATES = 64


def _within_lut(value: int, tolerance: int) -> list[int]:
    """Point table for one band: 255 where the band is within ``tolerance`` of ``value``."""
    return [255 if abs(v - value) <= tolerance else 0 for v in range(256)]


def _close_to(
    bands: tuple[Image.Image, ...], color: tuple[int, int, int], tolerance: int
) -> Image.Image:
    """Mode "L" mask: 255 where every channel is within ``tolerance`` of ``color``."""
    red, green, blue = (
        band.point(_within_lut(c, tolerance)) for band, c in zip(bands, color, strict=True)
    )
    return ImageChops.darker(ImageChops.darker(red, green), blue)


def _find_tolerant(
    hay: Image.Image, needle: PreparedTemplate, tolerance: int
) -> tuple[int, int] | None:
    """Like the exact search, but every channel of every pixel may differ by ``tolerance``.

    All the per-pixel work runs in Pillow's C code: each probe pixel gives a
    mask of the places it could be, shifted to template top-left positions and
    intersected, and only the surviving candidates are compared in full. The
    rarest probe goes first, and once few candidates are left the remaining
    probes are skipped, so a typical search builds one or two masks (#161).
    """
    hw, hh = hay.size
    cols, lines = hw - needle.width + 1, hh - needle.height + 1
    bands = hay.split()
    masks: dict[tuple[int, int, int], Image.Image] = {}  # one mask per probe color
    candidates = None
    for px, py, color in needle.probes:
        if color not in masks:
            masks[color] = _close_to(bands, color, tolerance)
        mask = masks[color].crop((px, py, px + cols, py + lines))
        candidates = mask if candidates is None else ImageChops.darker(candidates, mask)
        if candidates.histogram()[255] < _FEW_CANDIDATES:
            break
    if candidates is None:
        return None
    flags = candidates.tobytes()
    index = flags.find(b"\xff")
    for _ in range(_MAX_TOLERANT_CHECKS):
        if index < 0:
            break
        x, y = index % cols, index // cols
        window = hay.crop((x, y, x + needle.width, y + needle.height))
        # One (low, high) pair per RGB band.
        extrema: Any = ImageChops.difference(window, needle.image).getextrema()
        if all(high <= tolerance for _low, high in extrema):
            return x, y
        index = flags.find(b"\xff", index + 1)
    return None


def find_template(
    haystack: Image.Image, needle: Image.Image | PreparedTemplate, tolerance: int = 0
) -> tuple[int, int] | None:
    """Top-left (x, y) of the first occurrence of ``needle`` in ``haystack``.

    With ``tolerance`` 0 the match is exact; otherwise each color channel of
    each pixel may differ by up to ``tolerance`` (like the pixel condition).
    """
    if not isinstance(needle, PreparedTemplate):
        needle = PreparedTemplate.from_image(needle)
    hay = haystack if haystack.mode == "RGB" else haystack.convert("RGB")
    hw, hh = hay.size
    nw, nh = needle.width, needle.height
    if nw == 0 or nh == 0 or nw > hw or nh > hh:
        return None
    if tolerance > 0:
        return _find_tolerant(hay, needle, tolerance)
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
    # Per-channel difference allowed for every pixel; 0 = exact match (#123).
    tolerance: int = 0
    # Worked out from ``template`` unless the caller already has it (#162).
    prepared: PreparedTemplate | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.prepared is None:
            object.__setattr__(self, "prepared", PreparedTemplate.from_image(self.template))

    @property
    def ready(self) -> PreparedTemplate:
        """The prepared template (always set once the target exists)."""
        assert self.prepared is not None
        return self.prepared

    def locate(self, grabber=grab) -> tuple[int, int] | None:
        """Screen coordinates of the template's center, or None if it isn't there."""
        found = find_template(grabber(self.region), self.ready, self.tolerance)
        if found is None:
            return None
        width, height = self.ready.width, self.ready.height
        return self.region.left + found[0] + width // 2, self.region.top + found[1] + height // 2
