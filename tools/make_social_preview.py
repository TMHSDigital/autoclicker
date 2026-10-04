#!/usr/bin/env python3
"""Draw docs/images/social-preview.png (1280x640) for the repository's social card.

Upload it under Settings > General > Social preview; GitHub has no API for it.
Uses the Windows Segoe UI fonts and the light-theme screenshot.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "docs" / "images"
FONTS = Path("C:/Windows/Fonts")
W, H = 1280, 640
TOP = (59, 140, 255)
BOTTOM = (0, 88, 201)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def main() -> None:
    card = Image.new("RGB", (W, H))
    px = card.load()
    for y in range(H):
        for x in range(W):
            t = (x / W) * 0.6 + (y / H) * 0.4
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM, strict=True))

    draw = ImageDraw.Draw(card)
    icon = Image.open(ROOT / "autoclicker" / "assets" / "autoclicker.png").convert("RGBA")
    icon = icon.resize((96, 96), Image.Resampling.LANCZOS)
    card.paste(icon, (72, 96), icon)

    white = (255, 255, 255)
    soft = (220, 233, 255)
    draw.text((72, 216), "Windows", font=font("segoeuib.ttf", 76), fill=white)
    draw.text((72, 300), "Autoclicker", font=font("segoeuib.ttf", 76), fill=white)
    draw.text(
        (74, 410),
        "Pick a spot, set the pace, press F6.",
        font=font("segoeui.ttf", 32),
        fill=soft,
    )
    draw.text(
        (74, 462),
        "Sequences · hold and key actions · safety stops on by default",
        font=font("segoeui.ttf", 24),
        fill=soft,
    )
    draw.text(
        (74, 548),
        "Free single .exe · no installer · github.com/TMHSDigital/autoclicker",
        font=font("segoeui.ttf", 22),
        fill=soft,
    )

    shot = Image.open(IMAGES / "screenshot-light.png").convert("RGBA")
    scale = 560 / shot.height
    shot = shot.resize((round(shot.width * scale), 560), Image.Resampling.LANCZOS)
    x, y = W - shot.width - 70, (H - shot.height) // 2
    shadow = Image.new("RGBA", (shot.width + 60, shot.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle(
        (30, 34, shot.width + 30, shot.height + 34), fill=(0, 20, 60, 110)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    card.paste(shadow, (x - 30, y - 30), shadow)
    card.paste(shot, (x, y), shot)

    out = IMAGES / "social-preview.png"
    card.save(out, optimize=True)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
