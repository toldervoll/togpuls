"""Genererer bakgrunnsbildet til Togpuls-DMG-en.

Brand-trofast layout: navy gradient (Lavender 90 → 100), pulserende ringer
rundt der app-ikonet plasseres, mintgrønne stegmerker, og selve Togpuls-
merket i tittelen. Ikon-koordinatene må stemme med ``create-dmg``-targeten
i Makefile.

Kjør (fra repo-rot)::

    macos/.venv/bin/pip install Pillow
    macos/.venv/bin/python macos/installer/render_dmg_background.py \\
        macos/installer/dmg-background.png
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH, HEIGHT = 600, 400

# Brand-paletten (fra togpuls/static/styles.css).
LAV_100 = (17, 20, 60)
LAV_90 = (24, 28, 86)
LAV_80 = (38, 47, 125)
LAV_70 = (59, 70, 171)
LAV_60 = (90, 104, 196)
LAV_40 = (174, 183, 226)
LAV_10 = (240, 241, 250)
MINT_60 = (26, 142, 96)
MINT_40 = (90, 195, 154)
WHITE = (255, 255, 255)

# Posisjonene create-dmg plasserer ikonene på (må stemme med Makefile).
TOGPULS_XY = (150, 180)
APPS_XY = (450, 180)
INSTALLER_XY = (300, 320)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    """Vertikal gradient — én linje per y."""
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    return img


def _radial_glow(size: tuple, center: tuple, color: tuple, max_radius: int) -> Image.Image:
    """Lag et radialt glow-lag som tones mykt ut fra center."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    steps = 24
    for i in range(steps, 0, -1):
        r = int(max_radius * i / steps)
        alpha = int(40 * (1 - i / steps) ** 2)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alpha,))
    return layer.filter(ImageFilter.GaussianBlur(radius=18))


def _draw_text_centered(draw, xy, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((xy[0] - w / 2, xy[1] - h / 2 - bbox[1]), text, font=font, fill=fill)


def _pulse_rings(img: Image.Image, center: tuple, radii_alpha) -> None:
    """Konsentriske ringer som speiler «pulsen» fra Togpuls-merket."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    for r, alpha in radii_alpha:
        draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            outline=LAV_40 + (alpha,),
            width=2,
        )
    layer = layer.filter(ImageFilter.GaussianBlur(radius=1.2))
    img.alpha_composite(layer)


def _step_badge(img: Image.Image, center: tuple, number: int) -> None:
    """Mintgrønt nummerert merke med myk skygge."""
    r = 22
    cx, cy = center

    # Skygge under merket.
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((cx - r, cy - r + 4, cx + r, cy + r + 4), fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=5))
    img.alpha_composite(shadow)

    # Selve merket — med en lysere kant for litt 3D-følelse.
    badge = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge)
    bdraw.ellipse((cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1), fill=MINT_40 + (255,))
    bdraw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MINT_60 + (255,))

    font = _font(20)
    bbox = bdraw.textbbox((0, 0), str(number), font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    bdraw.text(
        (cx - tw / 2, cy - th / 2 - bbox[1]),
        str(number),
        font=font,
        fill=WHITE + (255,),
    )
    img.alpha_composite(badge)


def _arrow(img: Image.Image, x0: int, x1: int, y: int) -> None:
    """Pen pil fra (x0, y) til (x1, y) i lavender, med rundede endepunkt."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    color = LAV_40 + (235,)

    # Stilken
    draw.line((x0, y, x1 - 14, y), fill=color, width=3)
    # Rundt startpunkt
    draw.ellipse((x0 - 4, y - 4, x0 + 4, y + 4), fill=color)
    # Pilspiss
    draw.polygon(
        [(x1, y), (x1 - 16, y - 10), (x1 - 16, y + 10)],
        fill=color,
    )

    # Liten skygge under pilen.
    glow = layer.filter(ImageFilter.GaussianBlur(radius=2))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def _hairline(img: Image.Image, xy0: tuple, xy1: tuple, alpha: int = 60) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line([xy0, xy1], fill=LAV_40 + (alpha,), width=1)
    img.alpha_composite(layer)


def _brand_mark(
    img: Image.Image,
    center: tuple,
    size: int,
    spoke_color: tuple = LAV_40,
    dot_color: tuple = MINT_60,
    alpha: int = 255,
) -> None:
    """Tegn Togpuls-merket (8 eiker + senterdisc + mintprikk) programmatisk.

    Geometrien er skalert fra ``togpuls/static/icons/icon.svg`` (viewBox 512×512:
    eiker fra senter til radius 150, stroke 22; senterdisc r=44; prikk r=20).
    """

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center

    scale = size / 512
    spoke_len = 150 * scale
    stroke = max(2, int(round(22 * scale)))
    disc_r = max(3, int(round(44 * scale)))
    dot_r = max(2, int(round(20 * scale)))
    half = stroke / 2

    sc = spoke_color + (alpha,)
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + spoke_len * math.cos(angle)
        y1 = cy + spoke_len * math.sin(angle)
        draw.line((cx, cy, x1, y1), fill=sc, width=stroke)
        # Rundt endepunkt så eikene ikke har skarpe kuttkanter.
        draw.ellipse((x1 - half, y1 - half, x1 + half, y1 + half), fill=sc)

    draw.ellipse((cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r), fill=sc)
    draw.ellipse(
        (cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
        fill=dot_color + (alpha,),
    )

    img.alpha_composite(layer)


def _title(img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    """Brand-merket og tittel sentrert øverst."""
    title_font = _font(28)
    subtitle_font = _font(12)

    mark_size = 56
    gap = 14

    bbox = draw.textbbox((0, 0), "Togpuls", font=title_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    total_w = mark_size + gap + text_w
    left = (WIDTH - total_w) // 2
    top = 22

    cx, cy = left + mark_size // 2, top + mark_size // 2

    # Myk halo så merket løfter seg fra gradienten.
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(halo)
    for i in range(10):
        r = mark_size // 2 + 18 - i
        a = int(10 + i * 3)
        hdraw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=LAV_40 + (a,))
    halo = halo.filter(ImageFilter.GaussianBlur(radius=12))
    img.alpha_composite(halo)

    _brand_mark(img, (cx, cy), mark_size)

    text_x = left + mark_size + gap
    text_y = cy - text_h / 2 - bbox[1]
    draw.text((text_x, text_y), "Togpuls", font=title_font, fill=LAV_10 + (255,))

    _draw_text_centered(
        draw,
        (WIDTH / 2, top + mark_size + 16),
        "installer for macOS",
        subtitle_font,
        LAV_40 + (220,),
    )


def render(out: Path) -> None:
    base = _gradient(WIDTH, HEIGHT, LAV_70, LAV_90).convert("RGBA")

    # Mykt radialt glow rundt der app-ikonet ligger — det «pulserer» ut fra ikonet.
    base.alpha_composite(_radial_glow(base.size, TOGPULS_XY, LAV_60, 180))
    base.alpha_composite(_radial_glow(base.size, INSTALLER_XY, LAV_60, 140))

    draw = ImageDraw.Draw(base)

    # Topp-tittel med brand-ikon.
    _title(base, draw)
    _hairline(base, (160, 120), (440, 120), alpha=55)

    # Konsentriske pulse-ringer rundt ikonposisjonene.
    _pulse_rings(
        base,
        TOGPULS_XY,
        [(72, 80), (96, 55), (122, 32), (150, 18)],
    )
    _pulse_rings(
        base,
        INSTALLER_XY,
        [(60, 90), (84, 60), (108, 35), (132, 18)],
    )

    # Nummererte stegmerker til venstre for hvert ikon.
    _step_badge(base, (52, TOGPULS_XY[1]), 1)
    _step_badge(base, (52, INSTALLER_XY[1]), 2)

    # Pil mellom Togpuls og Applications.
    _arrow(base, TOGPULS_XY[0] + 64, APPS_XY[0] - 60, TOGPULS_XY[1])

    out.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out, "PNG", optimize=True)
    print(f"→ {out}")


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path("dmg-background.png")
    render(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
