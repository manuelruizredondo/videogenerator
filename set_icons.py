#!/usr/bin/env python3
"""
set_icons.py — Genera iconos PNG personalizados y los asigna a los archivos .command.
No requiere dependencias externas más allá de Pillow.

Uso:
    python set_icons.py
"""

import subprocess
import tempfile
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).parent

# ── Configuración de iconos ────────────────────────────────────────────────────

ICONS = [
    {
        "file":    "Generar Vídeo.command",
        "bg":      (15, 20, 40),
        "accent":  (255, 200, 50),
        "symbol":  "▶",
        "line1":   "GENERAR",
        "line2":   "VÍDEO",
    },
    {
        "file":    "Preview.command",
        "bg":      (20, 35, 25),
        "accent":  (80, 220, 120),
        "symbol":  "⬡",
        "line1":   "PREVIEW",
        "line2":   "HTML",
    },
    {
        "file":    "Preview Vídeo.command",
        "bg":      (35, 15, 40),
        "accent":  (200, 100, 255),
        "symbol":  "⚡",
        "line1":   "PREVIEW",
        "line2":   "VÍDEO",
    },
]

SIZE = 512   # Tamaño del icono en px


# ── Utilidades ────────────────────────────────────────────────────────────────

def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def best_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Busca una fuente disponible en el sistema."""
    candidates_bold = [
        str(PROJECT / "fonts/neutrif/font-bold.ttf"),
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]
    candidates_reg = [
        str(PROJECT / "fonts/neutrif/font-regular.ttf"),
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in (candidates_bold if bold else candidates_reg):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def make_icon(cfg: dict) -> Image.Image:
    img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg     = cfg["bg"]
    accent = cfg["accent"]

    # Fondo con esquinas redondeadas
    rounded_rect(draw, (0, 0, SIZE, SIZE), radius=90, fill=(*bg, 255))

    # Borde sutil
    for t in range(3):
        draw.rounded_rectangle(
            [t, t, SIZE - t, SIZE - t],
            radius=90 - t,
            outline=(*accent, 60 - t * 15),
            width=1,
        )

    # Línea decorativa horizontal
    lw = int(SIZE * 0.55)
    lx = (SIZE - lw) // 2
    draw.rounded_rectangle(
        [lx, SIZE // 2 - 2, lx + lw, SIZE // 2 + 2],
        radius=2,
        fill=(*accent, 80),
    )

    # Símbolo grande centrado en mitad superior
    sym_font = best_font(int(SIZE * 0.30))
    sym      = cfg["symbol"]
    sw       = text_w(draw, sym, sym_font)
    draw.text(
        ((SIZE - sw) // 2, int(SIZE * 0.12)),
        sym, font=sym_font, fill=(*accent, 255),
    )

    # Línea 1 (texto principal)
    f1   = best_font(int(SIZE * 0.13))
    t1   = cfg["line1"]
    tw1  = text_w(draw, t1, f1)
    draw.text(
        ((SIZE - tw1) // 2, int(SIZE * 0.56)),
        t1, font=f1, fill=(255, 255, 255, 240),
    )

    # Línea 2 (subtexto en accent)
    f2   = best_font(int(SIZE * 0.115))
    t2   = cfg["line2"]
    tw2  = text_w(draw, t2, f2)
    draw.text(
        ((SIZE - tw2) // 2, int(SIZE * 0.72)),
        t2, font=f2, fill=(*accent, 220),
    )

    return img


# ── Aplicar icono con osascript ────────────────────────────────────────────────

def apply_icon(icon_png: str, target_file: str) -> bool:
    """
    Asigna icon_png como icono de target_file usando NSWorkspace vía osascript.
    Escribe el script a un archivo temporal para evitar problemas con comillas.
    No requiere herramientas de terceros.
    """
    script = (
        'use framework "AppKit"\n'
        'use framework "Foundation"\n'
        f'set iconPath to "{icon_png}"\n'
        f'set filePath to "{target_file}"\n'
        "set theImage to current application's NSImage's alloc()'s "
        "initWithContentsOfFile:iconPath\n"
        "set didSet to current application's NSWorkspace's sharedWorkspace()'s "
        "setIcon:theImage forFile:filePath options:0\n"
        "return didSet\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".applescript", delete=False
    ) as f:
        f.write(script)
        tmp = f.name
    try:
        result = subprocess.run(
            ["osascript", tmp], capture_output=True, text=True
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    finally:
        os.unlink(tmp)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("═" * 50)
    print("  Asignando iconos a los archivos .command")
    print("═" * 50)

    icons_dir = PROJECT / "assets" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    for cfg in ICONS:
        target = PROJECT / cfg["file"]
        if not target.exists():
            print(f"  ⚠  No encontrado: {cfg['file']}")
            continue

        # Generar PNG
        icon_path = icons_dir / (Path(cfg["file"]).stem.replace(" ", "_") + ".png")
        img = make_icon(cfg)
        img.save(str(icon_path), "PNG")

        # Aplicar
        ok = apply_icon(str(icon_path), str(target))
        status = "✅" if ok else "❌"
        print(f"  {status}  {cfg['file']}")

    print()
    print("  Abre el Finder para ver los nuevos iconos.")
    print("  (Si no aparecen, pulsa Cmd+R para refrescar.)")


if __name__ == "__main__":
    main()
