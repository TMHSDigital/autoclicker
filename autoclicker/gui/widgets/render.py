# SPDX-License-Identifier: CC-BY-NC-4.0
"""Anti-aliased shapes for Tk canvases.

Tk's canvas does not anti-alias on Windows, so shapes are drawn with Pillow
at 3x and scaled down. Text stays a canvas item on top so it keeps ClearType.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw

SUPERSAMPLE = 3


@lru_cache(maxsize=64)
def rounded_rect(
    width: int,
    height: int,
    radius: int,
    fill: str,
    *,
    outline: str | None = None,
    outline_width: int = 1,
) -> Image.Image:
    """An RGBA image of a filled rounded rectangle; cached per argument set."""
    width, height = max(1, int(width)), max(1, int(height))
    radius = max(0, min(int(radius), width // 2, height // 2))
    big: Image.Image = Image.new("RGBA", (width * SUPERSAMPLE, height * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    draw.rounded_rectangle(
        (0, 0, width * SUPERSAMPLE - 1, height * SUPERSAMPLE - 1),
        radius=radius * SUPERSAMPLE,
        fill=fill,
        outline=outline,
        width=outline_width * SUPERSAMPLE if outline else 0,
    )
    small: Image.Image = big.resize((width, height), Image.Resampling.LANCZOS)
    return small


def ui_scale(widget: Any) -> float:
    """Display scale (1.0 at 96 dpi); 1.0 when Tk cannot say."""
    try:
        dpi = float(widget.winfo_fpixels("1i"))
    except Exception:
        return 1.0
    return dpi / 96.0 if dpi > 0 else 1.0


def px(value: int, scale: float) -> int:
    """``value`` logical pixels at ``scale``, rounded to a whole pixel."""
    return round(value * scale)
