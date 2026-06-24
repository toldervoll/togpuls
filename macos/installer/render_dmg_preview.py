"""Mock-up av hvordan DMG-vinduet ser ut med ikoner og labels på plass.

Brukes til designgjennomgang — ikke en del av selve byggekjeden. Komponerer
``Togpuls.app``-ikonet, Applications-symlenken og ``Installer.command`` på
toppen av bakgrunnen produsert av :mod:`render_dmg_background`, sammen med
labels under hvert ikon — som Finder gjør i et reelt DMG-vindu.

Kjør (fra repo-rot)::

    macos/.venv/bin/python macos/installer/render_dmg_preview.py \\
        macos/installer/dmg-preview.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from render_dmg_background import (
    APPS_XY,
    INSTALLER_XY,
    LAV_10,
    LAV_40,
    LAV_60,
    LAV_80,
    LAV_90,
    LAV_100,
    MINT_60,
    REPO_ROOT,
    TOGPULS_XY,
    WHITE,
    WIDTH,
    HEIGHT,
    _font,
    render as render_background,
)


ICON_SIZE = 96
BRAND_PNG = REPO_ROOT / "togpuls" / "static" / "icons" / "icon-512.png"


def _rounded_icon(size: int, fill: tuple, radius: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, size, size), radius=radius, fill=fill + (255,)
    )
    return img


def _shadow_under(base: Image.Image, center: tuple, size: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    cx, cy = center
    half = size // 2
    ImageDraw.Draw(layer).rounded_rectangle(
        (cx - half + 2, cy - half + 6, cx + half + 2, cy + half + 6),
        radius=22,
        fill=(0, 0, 0, 120),
    )
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=7)))


def _paste_centered(base: Image.Image, icon: Image.Image, center: tuple) -> None:
    cx, cy = center
    w, h = icon.size
    base.alpha_composite(icon, (cx - w // 2, cy - h // 2))


def _draw_label(draw: ImageDraw.ImageDraw, text: str, center_x: int, top_y: int) -> None:
    font = _font(13)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    # Liten mørk "platform" bak teksten for å øke lesbarheten — speiler Finder.
    pad_x, pad_y = 6, 2
    plate_box = (
        center_x - tw / 2 - pad_x,
        top_y - pad_y - 1,
        center_x + tw / 2 + pad_x,
        top_y + (bbox[3] - bbox[1]) + pad_y + 1,
    )
    draw.rounded_rectangle(plate_box, radius=4, fill=(0, 0, 0, 110))
    draw.text((center_x - tw / 2, top_y - bbox[1]), text, font=font, fill=WHITE + (255,))


def _togpuls_app_icon() -> Image.Image:
    """Bruk det ekte brand-ikonet, med avrundede hjørner som macOS-stilen."""
    src = Image.open(BRAND_PNG).convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    mask = Image.new("L", (ICON_SIZE, ICON_SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, ICON_SIZE, ICON_SIZE), radius=22, fill=255
    )
    out = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    out.paste(src, (0, 0), mask)
    return out


def _applications_icon() -> Image.Image:
    """Forenklet versjon av macOS Applications-mappa: lavender folder med «A»."""
    size = ICON_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Mappekropp
    draw.rounded_rectangle((4, 22, size - 4, size - 6), radius=14, fill=LAV_60 + (255,))
    # Mappefane på toppen
    draw.rounded_rectangle((6, 14, size // 2, 30), radius=6, fill=LAV_60 + (255,))
    # Lysere overflate
    draw.rounded_rectangle((4, 28, size - 4, size - 6), radius=12, fill=LAV_40 + (255,))
    # Stor "A" som i Applications-mappa
    font = _font(48)
    label = "A"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2, (size + 28 - th) / 2 - bbox[1] - 4),
        label,
        font=font,
        fill=LAV_90 + (255,),
    )
    return img


def _installer_command_icon() -> Image.Image:
    """Generisk «shell-script»-ikon: terminal-vindu med >_ prompt."""
    size = ICON_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Vindusramme
    draw.rounded_rectangle(
        (4, 8, size - 4, size - 8), radius=12, fill=(20, 24, 60, 255)
    )
    # Tittellinje med "trafikk-lys"
    draw.rounded_rectangle((4, 8, size - 4, 26), radius=12, fill=(40, 47, 110, 255))
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse((12 + i * 12, 14, 20 + i * 12, 22), fill=color + (255,))
    # Prompt
    font = _font(22)
    draw.text((16, 38), ">_", font=font, fill=(174, 240, 200, 255))
    return img


def render(out: Path) -> None:
    # Bygg bakgrunnen i en midlertidig fil og åpne den som RGBA-canvas.
    tmp_bg = Path("/tmp/_dmg_bg_preview.png")
    render_background(tmp_bg)
    canvas = Image.open(tmp_bg).convert("RGBA")

    # Skygger under ikonene gir dybde.
    for xy in (TOGPULS_XY, APPS_XY, INSTALLER_XY):
        _shadow_under(canvas, xy, ICON_SIZE)

    # Plasser ikonene på samme koordinater som create-dmg vil bruke.
    _paste_centered(canvas, _togpuls_app_icon(), TOGPULS_XY)
    _paste_centered(canvas, _applications_icon(), APPS_XY)
    _paste_centered(canvas, _installer_command_icon(), INSTALLER_XY)

    draw = ImageDraw.Draw(canvas)
    label_offset_y = ICON_SIZE // 2 + 10
    _draw_label(draw, "Togpuls", TOGPULS_XY[0], TOGPULS_XY[1] + label_offset_y)
    _draw_label(draw, "Applications", APPS_XY[0], APPS_XY[1] + label_offset_y)
    _draw_label(
        draw, "Installer.command", INSTALLER_XY[0], INSTALLER_XY[1] + label_offset_y
    )

    # Vindusramme (titlebar + grå kant) for å gi inntrykk av Finder-vinduet.
    frame = Image.new("RGBA", (WIDTH, HEIGHT + 22), (236, 236, 236, 255))
    fdraw = ImageDraw.Draw(frame)
    # Titlebar
    fdraw.rectangle((0, 0, WIDTH, 22), fill=(228, 228, 232, 255))
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        fdraw.ellipse((10 + i * 18, 6, 22 + i * 18, 18), fill=color + (255,))
    fdraw.text(
        (WIDTH / 2 - 28, 4),
        "Togpuls 0.1.0",
        font=_font(11),
        fill=(60, 60, 70, 255),
    )
    frame.alpha_composite(canvas, (0, 22))

    out.parent.mkdir(parents=True, exist_ok=True)
    frame.convert("RGB").save(out, "PNG", optimize=True)
    print(f"→ {out}")


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path("dmg-preview.png")
    render(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
