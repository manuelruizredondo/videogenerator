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
import warnings
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).parent

# ── Configuración de iconos ────────────────────────────────────────────────────

ICONS = [
    {
        "file":    "HIGH VIDEO.command",
        "bg":      (15, 20, 40),
        "accent":  (255, 200, 50),
        "symbol":  "▶",
        "line1":   "HIGH",
        "line2":   "VIDEO",
    },
    {
        "file":    "LOW VIDEO.command",
        "bg":      (35, 15, 40),
        "accent":  (200, 100, 255),
        "symbol":  "⚡",
        "line1":   "LOW",
        "line2":   "VIDEO",
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
        "file":         "Bajar de Sheets.command",
        "bg":           (10, 80, 35),
        "accent":       (52, 168, 83),
        "symbol":       "↓",
        "symbol_scale": 0.55,
        "line1":        "BAJAR",
        "line2":        "",
    },
    {
        "file":         "Subir a Sheets.command",
        "bg":           (15, 50, 90),
        "accent":       (66, 133, 244),
        "symbol":       "↑",
        "symbol_scale": 0.52,
        "line1":        "SUBIR",
        "line2":        "",
    },
    {
        "file":         "INSTAGRAM.command",
        "bg":           (40, 15, 40),
        "accent":       (225, 48, 108),
        "symbol":       "◈",
        "symbol_scale": 0.32,
        "line1":        "INSTA",
        "line2":        "GRAM",
    },
]

SIZE = 512   # Tamaño del icono en px


# ── Utilidades ────────────────────────────────────────────────────────────────

def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def best_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Busca una fuente disponible en el sistema para texto."""
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


def _font_renders_symbol(font: ImageFont.FreeTypeFont, symbol: str, size: int) -> bool:
    """
    Comprueba que la fuente renderiza el símbolo como un glifo único
    (no como tofu/caja de reemplazo).
    Renderiza el símbolo y una versión 'espejo' del mismo; si la fuente no lo
    soporta, ambos producen el mismo patrón de caja. También compara con un
    carácter ASCII para detectar glifos de sustitución idénticos.
    """
    from PIL import Image as _I, ImageDraw as _D
    sz = max(size, 64)

    def render(ch: str):
        img = _I.new("L", (sz, sz), 0)
        _D.Draw(img).text((0, 0), ch, font=font, fill=255)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return bytes(img.getdata())

    sym_pixels  = render(symbol)
    # Si el símbolo produce exactamente el mismo mapa que "?" probablemente
    # es el glifo de sustitución
    fallback    = render("?")
    empty       = render(" ")

    has_content = sym_pixels != empty
    not_tofu    = sym_pixels != fallback
    return has_content and not_tofu


def best_symbol_font(size: int, symbol: str = "↻") -> ImageFont.FreeTypeFont:
    """Busca la primera fuente que renderice el símbolo correctamente."""
    candidates = [
        "/System/Library/Fonts/Apple Symbols.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        str(PROJECT / "fonts/neutrif/font-bold.ttf"),
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                f = ImageFont.truetype(path, size)
                if _font_renders_symbol(f, symbol, size):
                    return f
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

    sym_scale = cfg.get("symbol_scale", 0.30)
    has_line2 = bool(cfg.get("line2"))

    # Símbolo: centrado verticalmente si no hay línea 2, o en mitad superior si las hay
    sym      = cfg["symbol"]
    sym_font = best_symbol_font(int(SIZE * sym_scale), symbol=sym)
    sw       = text_w(draw, sym, sym_font)
    bbox_sym = draw.textbbox((0, 0), sym, font=sym_font)
    sym_h    = bbox_sym[3] - bbox_sym[1]

    if has_line2:
        sym_y = int(SIZE * 0.12)
        line1_y_frac = 0.56
        line2_y_frac = 0.72
    else:
        # Símbolo en la zona superior 2/3, texto centrado debajo
        sym_y = int(SIZE * 0.08)
        line1_y_frac = 0.74

    draw.text(
        ((SIZE - sw) // 2, sym_y),
        sym, font=sym_font, fill=(*accent, 255),
    )

    # Línea 1 (texto principal)
    f1   = best_font(int(SIZE * 0.13))
    t1   = cfg["line1"]
    tw1  = text_w(draw, t1, f1)
    draw.text(
        ((SIZE - tw1) // 2, int(SIZE * line1_y_frac)),
        t1, font=f1, fill=(255, 255, 255, 240),
    )

    # Línea 2 (subtexto en accent) — solo si existe
    if not has_line2:
        return img
    f2   = best_font(int(SIZE * 0.115))
    t2   = cfg["line2"]
    tw2  = text_w(draw, t2, f2)
    draw.text(
        ((SIZE - tw2) // 2, int(SIZE * line2_y_frac)),
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


# ── Mapeo de iconos existentes ─────────────────────────────────────────────────

ICON_MAP = {
    "HIGH VIDEO.command":       "assets/icons/HIGH_VIDEO.png",
    "LOW VIDEO.command":        "assets/icons/LOW_VIDEO.png",
    "Preview.command":          "assets/icons/Preview.png",
    "INSTAGRAM.command":        "assets/icons/INSTAGRAM.png",
    "Bajar de Sheets.command":  "assets/icons/Bajar_de_Sheets.png",
    "Subir a Sheets.command":   "assets/icons/Subir_a_Sheets.png",
}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("═" * 50)
    print("  Asignando iconos a los archivos .command")
    print("═" * 50)

    for command_file, icon_rel in ICON_MAP.items():
        target    = PROJECT / command_file
        icon_path = PROJECT / icon_rel

        if not target.exists():
            print(f"  ⚠  No encontrado: {command_file}")
            continue
        if not icon_path.exists():
            print(f"  ⚠  Icono no encontrado: {icon_rel}")
            continue

        ok = apply_icon(str(icon_path), str(target))
        status = "✅" if ok else "❌"
        print(f"  {status}  {command_file}")

    print()
    print("  Abre el Finder para ver los iconos.")
    print("  (Si no aparecen, pulsa Cmd+Shift+R para refrescar.)")


if __name__ == "__main__":
    main()
