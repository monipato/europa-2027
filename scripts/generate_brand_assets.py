"""Derive the app's logo assets from the source lockup image.

Run from the project root (requires Pillow — `pip install pillow`):
    python3 scripts/generate_brand_assets.py

Reads src/patitours.jpg (the flat, white-background logo lockup) and writes:
    src/assets/brand/patitours-logo.png        full lockup, light theme (navy ink)
    src/assets/brand/patitours-logo-dark.png   full lockup, dark theme (cream ink)
    src/assets/brand/patitours-icon.png        icon only (badge, no wordmark), light
    src/assets/brand/patitours-icon-dark.png   icon only, dark
    public/favicon.png                         square favicon, from the icon

The source file is a plain JPEG on a white background with no transparency,
so this script keys out the white background and, for the dark variants,
recolors the navy ink (wordmark + line art) to a light cream so it stays
legible on a dark header — everything else (the duck, globe, teal canoe,
gold sparkle) is left untouched. Re-run this after replacing src/patitours.jpg
with a new export of the logo.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "patitours.jpg"
ASSETS_DIR = ROOT / "src" / "assets" / "brand"
PUBLIC_DIR = ROOT / "public"

CREAM_INK = (240, 235, 222)
HEADER_LOGO_HEIGHT = 160  # px, @1x — displayed around 38-44px tall in the header
ICON_HEIGHT = 160
FAVICON_SIZE = 256

# Background-removal / ink-detection thresholds — tuned for this specific
# JPEG (near-pure-white background, navy ink, no other near-white or
# near-navy content). Re-check these visually if the source image changes.
WHITE_CUTOUT_LOW, WHITE_CUTOUT_HIGH = 6, 40
NAVY_INK_MIN_BLUE_LEAD = 8  # how much bluer than red a pixel must be to count as "ink"
NAVY_INK_DARK, NAVY_INK_LIGHT = 80, 120  # brightness range recolored ink -> cream


def remove_white_background(img: Image.Image) -> Image.Image:
    """Convert a flat white background to transparency, with a soft-edged
    cutout so anti-aliased pixels blend cleanly instead of leaving a halo."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    src = rgb.load()
    out = Image.new("RGBA", (w, h))
    dst = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = src[x, y]
            distance_from_white = max(255 - r, 255 - g, 255 - b)
            if distance_from_white <= WHITE_CUTOUT_LOW:
                alpha = 0
            elif distance_from_white >= WHITE_CUTOUT_HIGH:
                alpha = 255
            else:
                alpha = round((distance_from_white - WHITE_CUTOUT_LOW) / (WHITE_CUTOUT_HIGH - WHITE_CUTOUT_LOW) * 255)
            dst[x, y] = (r, g, b, alpha)
    return out


def navy_ink_amount(r: int, g: int, b: int) -> float:
    """0 = not navy ink, 1 = fully navy ink, ramped by brightness. Navy ink is
    dark and distinctly bluish (b notably > r); this also excludes the
    logo's other dark tones — the brown paddle (r > b) and the bright teal
    canoe/globe (too light to be "dark")."""
    if b - r < NAVY_INK_MIN_BLUE_LEAD:
        return 0.0
    brightness = max(r, g, b)
    if brightness <= NAVY_INK_DARK:
        return 1.0
    if brightness >= NAVY_INK_LIGHT:
        return 0.0
    return (NAVY_INK_LIGHT - brightness) / (NAVY_INK_LIGHT - NAVY_INK_DARK)


def recolor_ink_for_dark_theme(img: Image.Image) -> Image.Image:
    out = img.copy()
    w, h = out.size
    px = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            t = navy_ink_amount(r, g, b)
            if t > 0:
                px[x, y] = (
                    round(r + (CREAM_INK[0] - r) * t),
                    round(g + (CREAM_INK[1] - g) * t),
                    round(b + (CREAM_INK[2] - b) * t),
                    a,
                )
    return out


def resize_to_height(img: Image.Image, height: int) -> Image.Image:
    width = round(img.width * height / img.height)
    return img.resize((width, height), Image.LANCZOS)


def split_icon_from_wordmark(logo: Image.Image) -> Image.Image:
    """The lockup is [circular icon] [gap] [wordmark]; find the widest fully
    transparent vertical gap and crop everything left of it."""
    w, h = logo.size
    alpha = logo.split()[3]
    apx = alpha.load()
    col_has_content = [any(apx[x, y] > 10 for y in range(h)) for x in range(w)]

    gaps: list[tuple[int, int]] = []
    x = 0
    while x < w:
        if not col_has_content[x]:
            start = x
            while x < w and not col_has_content[x]:
                x += 1
            gaps.append((start, x))
        else:
            x += 1
    gap_start, _ = max(gaps, key=lambda g: g[1] - g[0])

    icon = logo.crop((0, 0, gap_start, h))
    return icon.crop(icon.getbbox())


def make_favicon(icon: Image.Image) -> Image.Image:
    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(icon, ((side - icon.width) // 2, (side - icon.height) // 2))
    return square.resize((FAVICON_SIZE, FAVICON_SIZE), Image.LANCZOS)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    cutout = remove_white_background(Image.open(SOURCE))
    logo_light = resize_to_height(cutout.crop(cutout.getbbox()), HEADER_LOGO_HEIGHT)
    logo_dark = recolor_ink_for_dark_theme(logo_light)

    icon_light = resize_to_height(split_icon_from_wordmark(logo_light), ICON_HEIGHT)
    icon_dark = recolor_ink_for_dark_theme(icon_light)

    logo_light.save(ASSETS_DIR / "patitours-logo.png")
    logo_dark.save(ASSETS_DIR / "patitours-logo-dark.png")
    icon_light.save(ASSETS_DIR / "patitours-icon.png")
    icon_dark.save(ASSETS_DIR / "patitours-icon-dark.png")
    make_favicon(icon_light).save(PUBLIC_DIR / "favicon.png")

    print("Generated logo/icon/favicon assets in src/assets/brand/ and public/")


if __name__ == "__main__":
    main()
