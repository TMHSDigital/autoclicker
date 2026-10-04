#!/usr/bin/env python3
"""
Draw the application icon (matches docs/images/logo.svg).

Writes autoclicker/assets/autoclicker.png and autoclicker/assets/autoclicker.ico.
Uses no fonts, so the output is identical on every machine.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 256
SCALE = 4  # supersample for smooth edges
TOP = (59, 140, 255)  # #3b8cff
BOTTOM = (0, 88, 201)  # #0058c9


def _gradient(size: int) -> Image.Image:
    """Diagonal top-left to bottom-right blue gradient."""
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            rgb = (round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM, strict=True))
            px[x, y] = (*rgb, 255)
    return grad


def draw_icon() -> Image.Image:
    s = SIZE * SCALE
    unit = s / 128  # logo.svg is drawn on a 128 grid

    def p(v: float) -> float:
        return v * unit

    tile = _gradient(s)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=p(28), fill=255)
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    icon.paste(tile, (0, 0), mask)

    # Click ripples centred on the cursor tip
    rings = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rings)
    for radius, width, alpha in ((13, 4, 217), (25, 3.5, 115), (37, 3, 46)):
        r = p(radius)
        draw.ellipse(
            (p(50) - r, p(46) - r, p(50) + r, p(46) + r),
            outline=(255, 255, 255, alpha),
            width=round(p(width)),
        )
    icon = Image.alpha_composite(icon, rings)

    cursor = [(50, 46), (50, 98), (63, 86), (72, 106), (82, 101.5), (73, 82), (91, 82)]
    points = [(p(x), p(y)) for x, y in cursor]

    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x, y + p(2)) for x, y in points], fill=(0, 36, 90, 90))
    icon = Image.alpha_composite(icon, shadow.filter(ImageFilter.GaussianBlur(p(2))))

    arrow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(arrow)
    adraw.polygon(points, fill=(255, 255, 255, 255))
    adraw.line([*points, points[0]], fill=(11, 61, 145, 255), width=round(p(2.5)), joint="curve")
    icon = Image.alpha_composite(icon, arrow)

    return icon.resize((SIZE, SIZE), Image.LANCZOS)


def create_icon() -> None:
    assets = Path(__file__).resolve().parent.parent / "autoclicker" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    image = draw_icon()
    image.save(assets / "autoclicker.png", format="PNG", optimize=True)
    image.save(
        assets / "autoclicker.ico",
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)],
    )
    print(f"Wrote {assets / 'autoclicker.png'} and {assets / 'autoclicker.ico'}")


if __name__ == "__main__":
    create_icon()
