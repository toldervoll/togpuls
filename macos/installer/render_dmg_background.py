"""Genererer bakgrunnsbildet til Togpuls-DMG-en.

Layouten skal være selv-forklarende: brukeren skal kunne fullføre hele
installasjonen ved å se på DMG-vinduet, uten å besøke nettsiden. Derfor
har bakgrunnen tre lag tekst:

* Brand-merke og tittel øverst.
* «Dra Togpuls til Applications» med visuell pil mellom ikonene.
* Privacy-detouren beskrevet eksplisitt under, så ingen blir overrasket
  av Gatekeeper-dialogen på macOS Sequoia 26 og nyere.
* En liten henvisning til ``togpuls.kengu.no/install`` for full guide.

Ikon-koordinatene må stemme med ``create-dmg``-targeten i Makefile.

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


WIDTH, HEIGHT = 640, 460

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
TOGPULS_XY = (190, 195)
APPS_XY = (450, 195)

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
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    return img


def _radial_glow(size: tuple, center: tuple, color: tuple, max_radius: int) -> Image.Image:
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


def _arrow(img: Image.Image, x0: int, x1: int, y: int) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    color = LAV_40 + (235,)
    draw.line((x0, y, x1 - 14, y), fill=color, width=3)
    draw.ellipse((x0 - 4, y - 4, x0 + 4, y + 4), fill=color)
    draw.polygon(
        [(x1, y), (x1 - 16, y - 10), (x1 - 16, y + 10)],
        fill=color,
    )
    glow = layer.filter(ImageFilter.GaussianBlur(radius=2))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def _hairline(img: Image.Image, xy0: tuple, xy1: tuple, alpha: int = 60) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line([xy0, xy1], fill=LAV_40 + (alpha,), width=1)
    img.alpha_composite(layer)


def _brand_mark(img: Image.Image, center: tuple, size: int) -> None:
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

    sc = LAV_40 + (255,)
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + spoke_len * math.cos(angle)
        y1 = cy + spoke_len * math.sin(angle)
        draw.line((cx, cy, x1, y1), fill=sc, width=stroke)
        draw.ellipse((x1 - half, y1 - half, x1 + half, y1 + half), fill=sc)

    draw.ellipse((cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r), fill=sc)
    draw.ellipse(
        (cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
        fill=MINT_60 + (255,),
    )

    img.alpha_composite(layer)


def _title(img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    title_font = _font(28)
    subtitle_font = _font(12)

    mark_size = 56
    gap = 14

    bbox = draw.textbbox((0, 0), "Togpuls", font=title_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    total_w = mark_size + gap + text_w
    left = (WIDTH - total_w) // 2
    top = 28

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


def _numbered_step(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    center_y: int,
    number: str,
    lines: list,
    accent: bool = False,
) -> None:
    """Tegn et nummerert steg: «1.»-prefiks i mint, tekst i lavender.

    ``lines`` er en liste med strenger (én pr. linje). Hele blokken
    sentreres horisontalt rundt WIDTH/2 med tallet til venstre.
    """
    num_font = _font(15)
    body_font = _font(14)

    # Mål total bredde for sentrering.
    num_bbox = draw.textbbox((0, 0), number, font=num_font)
    num_w = num_bbox[2] - num_bbox[0]
    line_widths = []
    for line in lines:
        lb = draw.textbbox((0, 0), line, font=body_font)
        line_widths.append(lb[2] - lb[0])
    max_line_w = max(line_widths)

    gap = 10
    total_w = num_w + gap + max_line_w
    left = (WIDTH - total_w) // 2

    # Nummeret — i mint som matchner brand-prikken, vertikalt sentrert på
    # første linje.
    line_h = body_font.size + 4
    first_line_y = center_y - (len(lines) - 1) * line_h / 2
    num_color = MINT_40 if accent else MINT_60
    draw.text(
        (left, first_line_y - num_bbox[3] / 2 - num_bbox[1]),
        number,
        font=num_font,
        fill=num_color + (255,),
    )

    # Body-tekst — venstrejustert under tallet.
    text_x = left + num_w + gap
    for i, line in enumerate(lines):
        y = first_line_y + i * line_h
        lb = draw.textbbox((0, 0), line, font=body_font)
        h = lb[3] - lb[1]
        draw.text(
            (text_x, y - h / 2 - lb[1]),
            line,
            font=body_font,
            fill=LAV_10 + (235,),
        )


def render(out: Path) -> None:
    base = _gradient(WIDTH, HEIGHT, LAV_70, LAV_90).convert("RGBA")

    # Myk radial glød der ikonene plasseres — knytter dem til bakgrunnen.
    base.alpha_composite(_radial_glow(base.size, TOGPULS_XY, LAV_60, 180))
    base.alpha_composite(_radial_glow(base.size, APPS_XY, LAV_60, 140))

    draw = ImageDraw.Draw(base)

    _title(base, draw)
    _hairline(base, (180, 120), (WIDTH - 180, 120), alpha=55)

    # Pulsringer rundt Togpuls-ikonet — vår identitet, ikke Applications'.
    _pulse_rings(
        base,
        TOGPULS_XY,
        [(72, 80), (96, 55), (122, 32), (150, 18)],
    )

    # Pil fra Togpuls til Applications.
    _arrow(base, TOGPULS_XY[0] + 64, APPS_XY[0] - 60, TOGPULS_XY[1])

    # Steg-tekst under ikonene. Plassering må klare av ikon-etikettene
    # som Finder rendrer rundt y=240 (icon-size 96 + label-høyde).
    _numbered_step(
        draw,
        base,
        center_y=295,
        number="1.",
        lines=["Dra Togpuls til Applications-mappen til høyre."],
    )
    _numbered_step(
        draw,
        base,
        center_y=355,
        number="2.",
        lines=[
            "Første gang du åpner Togpuls: Systeminnstillinger →",
            "Personvern og sikkerhet → «Åpne likevel».",
        ],
    )

    # Henvisning til full guide nederst.
    footer_font = _font(11)
    _draw_text_centered(
        draw,
        (WIDTH / 2, HEIGHT - 24),
        "Full installasjonsguide: togpuls.kengu.no/install",
        footer_font,
        LAV_40 + (180,),
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out, "PNG", optimize=True)
    print(f"→ {out}")


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path("dmg-background.png")
    render(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
