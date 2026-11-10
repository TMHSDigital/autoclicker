#!/usr/bin/env python3
"""Draw docs/images/social-preview.png (1280x640) for the repository's social card.

Upload it under Settings > General > Social preview; GitHub has no API for it.
Uses the Windows Segoe UI fonts, the website's flat hero blue (docs/site.css)
and docs/images/screenshot-dark.png (`tools/ui_snapshots.py website`).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "docs" / "images"
FONTS = Path("C:/Windows/Fonts")
W, H = 1280, 640
BG = (11, 92, 196)  # --hero-bg
LINE = (38, 48, 60)  # the app's own border color, around the screenshot
TEXT = (255, 255, 255)  # --hero-text
ACCENT = (255, 255, 255)
MUTED = (220, 233, 255)  # --hero-soft
LEFT = 72
SHOT_W = 620
SHOT_RIGHT_MARGIN = 56


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def main() -> None:
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)
    shot_x = W - SHOT_W - SHOT_RIGHT_MARGIN
    text_right = shot_x - 40

    icon = Image.open(ROOT / "autoclicker" / "assets" / "autoclicker.png").convert("RGBA")
    icon = icon.resize((88, 88), Image.Resampling.LANCZOS)
    card.paste(icon, (LEFT, 92), icon)

    bold, tag, body, small = (
        font("segoeuib.ttf", 68),
        font("segoeui.ttf", 28),
        font("segoeui.ttf", 22),
        font("segoeui.ttf", 20),
    )
    lines = [
        ((LEFT, 210), "Windows", bold, TEXT),
        ((LEFT, 286), "Autoclicker", bold, TEXT),
        ((LEFT + 2, 392), "Pick a spot, set the pace, press F6.", tag, ACCENT),
        ((LEFT + 2, 440), "Record routines, click wherever an image", body, MUTED),
        ((LEFT + 2, 470), "appears, safety stops on by default.", body, MUTED),
        ((LEFT + 2, 548), "Free single .exe for Windows 10 and 11", small, MUTED),
    ]
    for (x, y), text, face, fill in lines:
        if x + draw.textlength(text, font=face) > text_right:
            raise SystemExit(f"Text runs into the screenshot: {text!r}")
        draw.text((x, y), text, font=face, fill=fill)

    shot = Image.open(IMAGES / "screenshot-dark.png").convert("RGBA")
    scale = SHOT_W / shot.width
    shot = shot.resize((SHOT_W, round(shot.height * scale)), Image.Resampling.LANCZOS)
    y = (H - shot.height) // 2
    shadow = Image.new("RGBA", (shot.width + 80, shot.height + 80), (0, 0, 0, 0))
    box = (40, 48, shot.width + 40, shot.height + 48)
    ImageDraw.Draw(shadow).rectangle(box, fill=(0, 20, 60, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    card.paste(shadow, (shot_x - 40, y - 40), shadow)
    card.paste(shot, (shot_x, y), shot)
    draw.rectangle((shot_x - 1, y - 1, shot_x + shot.width, y + shot.height), outline=LINE)

    out = IMAGES / "social-preview.png"
    card.save(out, optimize=True)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
