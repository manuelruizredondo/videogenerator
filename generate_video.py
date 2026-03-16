#!/usr/bin/env python3
"""
VideoGenerator — Generador de vídeos promocionales para escaparate dual 4K
===========================================================================
Canvas  : 3840 × 4320 px  (2× TVs 4K apiladas verticalmente)
Línea   : y = 2160 px  (separación física entre pantallas)
Codec   : H.264  |  Pixel fmt : yuv420p  |  FPS : configurable (por defecto 25)

Uso:
    python generate_video.py
    python generate_video.py -d data/productos.csv -o output/final.mp4
    python generate_video.py --data data/products.json --config config.json --output output/video.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════════════════════════════════
#  DIMENSIONES FIJAS DEL CANVAS
# ═══════════════════════════════════════════════════════════════════════════════

CANVAS_W: int = 3840
CANVAS_H: int = 4320
TV_SPLIT: int = 2160   # Píxel Y donde se unen físicamente las dos pantallas


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHÉ DE FUENTES
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent

_font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}

_FONT_DIRS = [
    Path("fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/usr/share/fonts/truetype/dejavu"),       # Linux
    Path("/usr/share/fonts/truetype/liberation"),   # Linux
    Path(__file__).parent / "fonts",
]

_BOLD_CANDIDATES = [
    "Montserrat-Bold.ttf",
    "Inter-Bold.ttf",
    "Roboto-Bold.ttf",
    "Arial Bold.ttf",
    "Arial_Bold.ttf",
    "ArialBD.ttf",
    "LiberationSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "Helvetica-Bold.ttf",
]

_REGULAR_CANDIDATES = [
    "Montserrat-Regular.ttf",
    "Inter-Regular.ttf",
    "Roboto-Regular.ttf",
    "Arial.ttf",
    "LiberationSans-Regular.ttf",
    "DejaVuSans.ttf",
    "Helvetica.ttf",
]


def _find_font(names: list[str]) -> Optional[str]:
    for d in _FONT_DIRS:
        for n in names:
            p = d / n
            if p.exists():
                return str(p)
    return None


def get_font(size: int, bold: bool = True, font_name: Optional[str] = None) -> ImageFont.FreeTypeFont:
    """
    Carga o recupera del caché una fuente TrueType/OTF.
    font_name puede ser:
      - Una ruta relativa al proyecto:  'fonts/neutrif/font-bold.ttf'
      - Solo el nombre de archivo:      'font-bold.ttf'  (busca en _FONT_DIRS)
    Si no se encuentra, recurre a la lista genérica bold/regular.
    """
    key = (size, font_name or bold)
    if key in _font_cache:
        return _font_cache[key]

    path: Optional[str] = None

    if font_name:
        # Opción 1: ruta relativa al proyecto (con subcarpetas)
        candidate = resolve_path(font_name)
        if candidate.exists():
            path = str(candidate)
        else:
            # Opción 2: solo nombre de archivo, buscar en _FONT_DIRS
            path = _find_font([font_name, Path(font_name).name])
        if not path:
            print(f"  ⚠  Fuente '{font_name}' no encontrada — usando fuente del sistema.", file=sys.stderr)

    if not path:
        path = _find_font(_BOLD_CANDIDATES if bold else _REGULAR_CANDIDATES)

    if path:
        font = ImageFont.truetype(path, size)
    else:
        print("  ⚠  No se encontró ninguna fuente TrueType. Coloca un .ttf en la carpeta fonts/", file=sys.stderr)
        font = ImageFont.load_default()

    _font_cache[key] = font
    return font


# ═══════════════════════════════════════════════════════════════════════════════
#  VÍDEO DE FONDO
# ═══════════════════════════════════════════════════════════════════════════════

_VIDEO_EXTS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".mts"})


def is_video_path(path: Optional[str]) -> bool:
    return bool(path) and Path(path).suffix.lower() in _VIDEO_EXTS


class VideoBackground:
    """
    Decodifica un vídeo de fondo frame a frame vía FFmpeg pipe.
    Usa -stream_loop -1 para repetir el vídeo en bucle automáticamente.
    Acepta width/height opcionales para cargar a una resolución distinta del
    canvas completo (e.g. panel derecho en template 'split').
    Consumo de memoria: O(1) — solo un frame en RAM en cada instante.
    """

    def __init__(
        self,
        path: Path,
        fps: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        w = width  if width  is not None else CANVAS_W
        h = height if height is not None else CANVAS_H
        self._w           = w
        self._h           = h
        self._frame_bytes = w * h * 3
        vf = (
            f"scale={w}:{h}"
            f":force_original_aspect_ratio=increase,"
            f"crop={w}:{h}"
        )
        self._proc = subprocess.Popen(
            [
                "ffmpeg",
                "-stream_loop", "-1",   # bucle infinito
                "-i", str(path),
                "-vf", vf,
                "-r", str(fps),
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def get_next_frame(self) -> np.ndarray:
        data = self._proc.stdout.read(self._frame_bytes)
        if len(data) < self._frame_bytes:
            # Leer stderr para dar un mensaje útil si el vídeo no pudo leerse
            err = self._proc.stderr.read().decode("utf-8", errors="replace").strip()
            if err:
                last = "\n".join(err.splitlines()[-5:])
                print(f"\n  ⚠️  Advertencia leyendo vídeo de fondo: {last}", file=sys.stderr)
            return np.zeros((self._h, self._w, 3), dtype=np.uint8)
        return np.frombuffer(data, dtype=np.uint8).reshape(self._h, self._w, 3).copy()

    def close(self) -> None:
        try:
            self._proc.kill()
            self._proc.wait()
        except Exception:
            pass


def load_background_source(
    path: Optional[str],
    fps: int,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> "np.ndarray | VideoBackground":
    """
    Imagen  → devuelve un ndarray estático (se reutiliza en todos los frames).
    Vídeo   → devuelve VideoBackground (un frame nuevo en cada llamada a get_next_frame).
    width/height permiten cargar a una resolución distinta del canvas completo
    (e.g. panel derecho en template 'split': CANVAS_W//2 × CANVAS_H).
    """
    if is_video_path(path):
        resolved = resolve_path(path)
        if resolved.exists():
            return VideoBackground(resolved, fps, width, height)
        print(f"  ⚠  Vídeo no encontrado: {path} — usando degradado.", file=sys.stderr)
    return load_background(path, width, height)


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGO  (header y footer)
# ═══════════════════════════════════════════════════════════════════════════════

def load_logo_from_cfg(l_cfg: Optional[dict]) -> Optional[Image.Image]:
    """Carga y redimensiona un logo a partir de su sección de config."""
    if not l_cfg or not l_cfg.get("file"):
        return None
    path = resolve_path(l_cfg["file"])
    if not path.exists():
        print(f"  ⚠  Logo no encontrado: {l_cfg['file']}", file=sys.stderr)
        return None
    img      = Image.open(path).convert("RGBA")
    target_w = int(l_cfg.get("width", 400))
    ratio    = target_w / img.width
    return img.resize((target_w, int(img.height * ratio)), Image.LANCZOS)


def compute_logo_pos_from_cfg(logo_img: Image.Image, l_cfg: dict) -> tuple[int, int]:
    """Calcula la posición (x, y) de la esquina superior-izquierda del logo."""
    position    = l_cfg.get("position", "top-center")
    margin_top  = int(l_cfg.get("margin_top",  150))
    margin_side = int(l_cfg.get("margin_side", 150))
    lw, lh      = logo_img.size

    if isinstance(position, list) and len(position) == 2:
        return (int(position[0]), int(position[1]))

    return {
        "top-center":    ((CANVAS_W - lw) // 2,        margin_top),
        "top-left":      (margin_side,                  margin_top),
        "top-right":     (CANVAS_W - lw - margin_side,  margin_top),
        "bottom-center": ((CANVAS_W - lw) // 2,        CANVAS_H - margin_top - lh),
        "bottom-left":   (margin_side,                  CANVAS_H - margin_top - lh),
        "bottom-right":  (CANVAS_W - lw - margin_side,  CANVAS_H - margin_top - lh),
    }.get(position, ((CANVAS_W - lw) // 2, margin_top))


# Mantener las funciones originales como alias para compatibilidad
def load_logo(cfg: dict) -> Optional[Image.Image]:
    return load_logo_from_cfg(cfg.get("logo"))

def compute_logo_pos(logo_img: Image.Image, cfg: dict) -> tuple[int, int]:
    return compute_logo_pos_from_cfg(logo_img, cfg.get("logo", {}))


def calc_logo_global_anim(
    t_g:       float,
    total_dur: float,
    l_cfg:     dict,
    base_pos:  tuple[int, int],
    logo_size: tuple[int, int],
) -> tuple[float, tuple[int, int]]:
    """
    Devuelve (alpha, pos) para el logo en tiempo global t_g.
    Los logos entran UNA SOLA VEZ al inicio del vídeo y salen al final.

    Entrada : ease-out cúbico  (rápido al salir del borde, suave al llegar)
    Salida  : ease-in cúbico   (suave al empezar, rápido al salir por el borde)
    """
    appear_at  = l_cfg.get("appear_at",      0.5)
    fade_dur   = l_cfg.get("fade_duration",  0.8)
    slide_dur  = l_cfg.get("slide_duration", 0.6)
    enter_from = l_cfg.get("enter_from")

    exit_start = max(total_dur - slide_dur, appear_at + slide_dur)

    # ── Alpha ─────────────────────────────────────────────────────────────────
    if t_g < appear_at:
        alpha = 0.0
    elif t_g < appear_at + fade_dur:
        alpha = (t_g - appear_at) / fade_dur
    elif t_g < exit_start:
        alpha = 1.0
    elif t_g < total_dur:
        alpha = 1.0 - (t_g - exit_start) / slide_dur
    else:
        alpha = 0.0
    alpha = max(0.0, min(1.0, alpha))

    if not enter_from:
        return alpha, base_pos

    # ── Progreso de entrada: ease-out cúbico ──────────────────────────────────
    if t_g < appear_at:
        ep_raw = 0.0
    elif t_g < appear_at + slide_dur:
        ep_raw = (t_g - appear_at) / slide_dur
    else:
        ep_raw = 1.0
    ep = 1.0 - (1.0 - ep_raw) ** 3        # ease-out

    # ── Progreso de salida: ease-in cúbico ────────────────────────────────────
    if t_g < exit_start:
        xp_raw = 0.0
    elif t_g < total_dur:
        xp_raw = (t_g - exit_start) / slide_dur
    else:
        xp_raw = 1.0
    xp = xp_raw ** 3                       # ease-in

    bx, by = base_pos
    lw, lh = logo_size

    def lerp(a: float, b: float, p: float) -> int:
        return int(a + (b - a) * p)

    if enter_from == "top":
        sy  = -lh
        cur = lerp(sy, by, ep) if xp == 0.0 else lerp(by, sy, xp)
        return alpha, (bx, cur)
    if enter_from == "bottom":
        sy  = CANVAS_H
        cur = lerp(sy, by, ep) if xp == 0.0 else lerp(by, sy, xp)
        return alpha, (bx, cur)
    if enter_from == "left":
        sx  = -lw
        cur = lerp(sx, bx, ep) if xp == 0.0 else lerp(bx, sx, xp)
        return alpha, (cur, by)
    if enter_from == "right":
        sx  = CANVAS_W
        cur = lerp(sx, bx, ep) if xp == 0.0 else lerp(bx, sx, xp)
        return alpha, (cur, by)
    return alpha, base_pos


def composite_logo(
    canvas:   Image.Image,
    logo_img: Image.Image,
    pos:      tuple[int, int],
    alpha:    float,
) -> None:
    """
    Composita el logo en canvas en pos con el alpha dado.
    Gestiona clipping cuando el logo está parcialmente fuera del canvas
    (necesario durante la animación de entrada).
    """
    if alpha <= 0.01:
        return

    lx, ly   = pos
    lw, lh   = logo_img.size
    src_x    = max(0, -lx)
    src_y    = max(0, -ly)
    dst_x    = max(0, lx)
    dst_y    = max(0, ly)
    clip_w   = min(lw - src_x, CANVAS_W - dst_x)
    clip_h   = min(lh - src_y, CANVAS_H - dst_y)

    if clip_w <= 0 or clip_h <= 0:
        return

    arr  = np.array(logo_img)
    crop = arr[src_y:src_y + clip_h, src_x:src_x + clip_w].copy()
    crop[:, :, 3] = (crop[:, :, 3].astype(float) * alpha).astype(np.uint8)
    canvas.alpha_composite(Image.fromarray(crop, "RGBA"), dest=(dst_x, dst_y))


# ═══════════════════════════════════════════════════════════════════════════════
#  ANIMACIÓN: CÁLCULO DE ALPHA
# ═══════════════════════════════════════════════════════════════════════════════

def calc_alpha(
    t: float,
    appear_at: float,
    fade_in: float,
    fade_out_start: float,
    fade_out: float,
) -> float:
    """
    Devuelve un valor 0.0‒1.0 para el instante t según la curva:
      0              → invisible
      appear_at      → empieza fade-in
      appear_at+fade_in → totalmente visible
      fade_out_start → empieza fade-out
      fade_out_start+fade_out → invisible
    """
    if t < appear_at:
        return 0.0
    if t < appear_at + fade_in:
        return (t - appear_at) / fade_in
    if t < fade_out_start:
        return 1.0
    if t < fade_out_start + fade_out:
        return 1.0 - (t - fade_out_start) / fade_out
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  TEXTO: WRAP Y DIBUJO CENTRADO
# ═══════════════════════════════════════════════════════════════════════════════

# Imagen dummy reutilizable para medición de texto (no se pinta nunca)
_MEASURE_IMG  = Image.new("RGBA", (1, 1))
_MEASURE_DRAW = ImageDraw.Draw(_MEASURE_IMG)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """
    Divide el texto en líneas que caben dentro de max_w píxeles.
    Respeta saltos de línea explícitos con \\n en el texto.
    """
    result = []
    for paragraph in text.split("\n"):
        words, current = paragraph.split(), []
        for word in words:
            candidate = " ".join(current + [word])
            bbox = _MEASURE_DRAW.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_w:
                current.append(word)
            else:
                if current:
                    result.append(" ".join(current))
                current = [word]
        result.append(" ".join(current) if current else "")
    return result or [""]


def _parse_px(value, default: int = 0) -> int:
    """Convierte un valor de píxeles a int. Acepta '7px', '7', 7, 7.0, etc."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    return int(str(value).lower().replace("px", "").strip() or default)


def _char_advance(font: ImageFont.FreeTypeFont, ch: str) -> int:
    """
    Ancho visual (bounding box) de un carácter.
    Usamos bbox en lugar del advance tipográfico para que el kerning óptico
    sea más ajustado; preview.py compensa la diferencia al generar CSS.
    """
    bb = _MEASURE_DRAW.textbbox((0, 0), ch, font=font)
    return bb[2] - bb[0]


def _measure_line_w(line: str, font: ImageFont.FreeTypeFont, letter_spacing: int) -> int:
    """Ancho total de una línea aplicando letter_spacing entre caracteres."""
    if not line:
        return 0
    total = 0
    for ch in line:
        total += _char_advance(font, ch) + letter_spacing
    return total - letter_spacing  # el último carácter no lleva spacing extra


def _draw_line(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    line: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    letter_spacing: int,
) -> None:
    """Dibuja una línea carácter a carácter respetando letter_spacing."""
    for ch in line:
        draw.text((x, y), ch, font=font, fill=fill)
        x += _char_advance(font, ch) + letter_spacing


def draw_text_centered(
    canvas: Image.Image,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    cx: int,
    cy: int,
    color: tuple[int, int, int],
    alpha: float,
    line_spacing: float = 1.25,
    shadow_color: tuple[int, int, int] = (0, 0, 0),
    shadow_alpha_factor: float = 0.65,
    letter_spacing: int = 0,
    shadow: bool = True,
    x_left: Optional[int] = None,
) -> None:
    """
    Dibuja un bloque de texto con sombra opcional y alpha.
    Por defecto centra cada línea en cx.
    Si x_left se especifica, alinea todas las líneas a la izquierda desde esa x
    (usado en template 'split').
    """
    if alpha <= 0.01:
        return

    bbox_sample = _MEASURE_DRAW.textbbox((0, 0), "Ágjy", font=font)
    line_h  = bbox_sample[3] - bbox_sample[1]
    total_h = line_h * line_spacing * len(lines)
    y_start = cy - total_h / 2

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    int_alpha  = int(alpha * 255)
    shadow_a   = int(alpha * 255 * shadow_alpha_factor)
    shadow_off = max(3, font.size // 25)

    for i, line in enumerate(lines):
        lw = _measure_line_w(line, font, letter_spacing)
        x  = x_left if x_left is not None else (cx - lw // 2)
        y  = int(y_start + i * line_h * line_spacing)
        if shadow:
            _draw_line(draw, x + shadow_off, y + shadow_off, line, font,
                       (*shadow_color, shadow_a), letter_spacing)
        _draw_line(draw, x, y, line, font, (*color, int_alpha), letter_spacing)

    canvas.alpha_composite(layer)


def draw_prices(
    canvas:       Image.Image,
    price_text:   str,
    font_price:   ImageFont.FreeTypeFont,
    price_color:  tuple[int, int, int],
    before_text:  str,
    font_before:  Optional[ImageFont.FreeTypeFont],
    before_color: tuple[int, int, int],
    strike_color: tuple[int, int, int],
    cx: int,
    cy: int,
    alpha: float,
    gap:  int = 100,
    shadow_color: tuple[int, int, int] = (0, 0, 0),
    shadow_alpha_factor: float = 0.65,
    letter_spacing: int = 0,
    letter_spacing_before: int = 0,
    price_badge: Optional[dict] = None,
    price_before_badge: Optional[dict] = None,
    shadow: bool = True,
    shadow_before: bool = True,
    x_left: Optional[int] = None,
) -> None:
    """
    Dibuja el precio actual y, si before_text no está vacío, el precio anterior
    tachado a su izquierda. Ambos quedan centrados juntos en (cx, cy).
    Cada precio puede tener un badge (fondo pill) configurable.
    """
    if alpha <= 0.01:
        return

    # Si no hay texto que mostrar, no dibujar nada (ni badge)
    show_before = bool(before_text and font_before)
    if not price_text and not show_before:
        return

    # ── Medir textos ──────────────────────────────────────────────────────────
    w_p    = _measure_line_w(price_text, font_price, letter_spacing)
    bb_p   = _MEASURE_DRAW.textbbox((0, 0), price_text, font=font_price)
    h_p    = bb_p[3] - bb_p[1]

    if show_before:
        w_b  = _measure_line_w(before_text, font_before, letter_spacing_before)
        bb_b = _MEASURE_DRAW.textbbox((0, 0), before_text, font=font_before)
        h_b  = bb_b[3] - bb_b[1]
        total_w = w_b + gap + w_p
    else:
        w_b = h_b = 0
        total_w = w_p

    x_start = x_left if x_left is not None else (cx - total_w // 2)

    # ── Capa RGBA para composición con alpha ──────────────────────────────────
    layer     = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw      = ImageDraw.Draw(layer)
    int_a     = int(alpha * 255)
    shadow_a  = int(alpha * 255 * shadow_alpha_factor)

    def _draw_badge(badge: dict, x: int, y: int, w: int,
                    bb1: int, bb3: int) -> None:
        """
        Dibuja el badge anclado a los bounds visuales reales del glifo.
        bb1/bb3 son los offsets superior/inferior del bbox respecto al punto
        de dibujo y (mismo sistema que textbbox devuelve).
        """
        pad    = int(badge.get("padding", 30))
        pad_x  = int(badge.get("padding_x", pad))
        pad_y  = int(badge.get("padding_y", pad))
        radius = int(badge.get("border_radius", 999))
        bg     = badge.get("background", [0, 0, 0, 117])
        br, bg_, bb_, ba = (int(v) for v in bg)
        ba_final = int(ba * alpha)
        draw.rounded_rectangle(
            [x - pad_x, y + bb1 - pad_y,
             x + w + pad_x, y + bb3 + pad_y],
            radius=radius,
            fill=(br, bg_, bb_, ba_final),
        )

    # ── Badge precio anterior ─────────────────────────────────────────────────
    if show_before:
        x_b = x_start
        # Centrar el texto en cy usando los bounds visuales reales
        y_b = cy - (bb_b[1] + bb_b[3]) // 2
        if price_before_badge:
            _draw_badge(price_before_badge, x_b, y_b, w_b, bb_b[1], bb_b[3])
        shadow_off_b = max(3, font_before.size // 25)
        if shadow_before:
            _draw_line(draw, x_b + shadow_off_b, y_b + shadow_off_b, before_text,
                       font_before, (*shadow_color, shadow_a), letter_spacing_before)
        _draw_line(draw, x_b, y_b, before_text, font_before,
                   (*before_color, int_a), letter_spacing_before)
        # Tachado centrado en el centro visual del glifo
        strike_y     = y_b + (bb_b[1] + bb_b[3]) // 2
        strike_thick = max(5, font_before.size // 12)
        draw.rectangle(
            [x_b, strike_y - strike_thick // 2,
             x_b + w_b, strike_y + strike_thick // 2],
            fill=(*strike_color, int_a),
        )

    # ── Badge precio actual ───────────────────────────────────────────────────
    x_p = x_start + (w_b + gap if show_before else 0)
    # Centrar usando los bounds visuales reales del glifo
    y_p = cy - (bb_p[1] + bb_p[3]) // 2
    if price_badge:
        _draw_badge(price_badge, x_p, y_p, w_p, bb_p[1], bb_p[3])
    shadow_off_p = max(3, font_price.size // 25)
    if shadow:
        _draw_line(draw, x_p + shadow_off_p, y_p + shadow_off_p, price_text,
                   font_price, (*shadow_color, shadow_a), letter_spacing)
    _draw_line(draw, x_p, y_p, price_text, font_price,
               (*price_color, int_a), letter_spacing)

    canvas.alpha_composite(layer)


# ═══════════════════════════════════════════════════════════════════════════════
#  FONDO: CARGA, ESCALA Y DEGRADADOS
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_path(path: str) -> Path:
    """Resuelve rutas relativas al directorio del proyecto."""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return PROJECT_ROOT / p


def load_background(
    path: Optional[str],
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> np.ndarray:
    """
    Carga una imagen de fondo y la escala (cover) a las dimensiones indicadas.
    Por defecto usa el canvas completo (CANVAS_W × CANVAS_H).
    Si no hay imagen, genera un degradado oscuro por defecto.
    Devuelve un array numpy uint8 RGB.
    """
    w = width  if width  is not None else CANVAS_W
    h = height if height is not None else CANVAS_H
    resolved = resolve_path(path) if path else None
    if resolved and resolved.exists():
        img = Image.open(resolved).convert("RGB")
        # Escala "cover": rellenar todo el área manteniendo aspecto
        img_ratio    = img.width / img.height
        canvas_ratio = w / h
        if img_ratio > canvas_ratio:
            new_h = h
            new_w = int(h * img_ratio)
        else:
            new_w = w
            new_h = int(w / img_ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        x = (new_w - w) // 2
        y = (new_h - h) // 2
        img = img.crop((x, y, x + w, y + h))
    else:
        if path:
            print(f"  ⚠  Imagen no encontrada: {path} — usando degradado.", file=sys.stderr)
        # Degradado oscuro azul/gris de arriba a abajo
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        for row in range(h):
            t = row / h
            arr[row, :, 0] = int(15 + 20 * t)
            arr[row, :, 1] = int(15 + 15 * t)
            arr[row, :, 2] = int(60 + 40 * (1 - t))
        return arr
    return np.array(img)


def make_overlay(alpha_value: int) -> Image.Image:
    """Capa oscura semitransparente para mejorar el contraste del texto."""
    return Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, alpha_value))


def make_vignette(strength: int = 80) -> np.ndarray:
    """
    Genera una viñeta radial que oscurece los bordes del canvas.
    Devuelve un array RGBA uint8.
    """
    cx, cy = CANVAS_W / 2, CANVAS_H / 2
    xs = np.linspace(0, CANVAS_W, CANVAS_W)
    ys = np.linspace(0, CANVAS_H, CANVAS_H)
    xg, yg = np.meshgrid(xs, ys)
    dist = np.sqrt(((xg - cx) / cx) ** 2 + ((yg - cy) / cy) ** 2)
    dist = np.clip(dist, 0, 1)
    alpha_arr = (dist ** 1.8 * strength).astype(np.uint8)
    vig = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    vig[:, :, 3] = alpha_arr   # solo canal alpha, negro
    return vig


# ═══════════════════════════════════════════════════════════════════════════════
#  PRE-CÓMPUTO POR SLIDE (fuentes + líneas de texto)
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_font_size(product: dict, field_key: str, default: int) -> int:
    """
    Devuelve el font_size efectivo: usa el valor del producto si existe,
    si no el valor por defecto del config.
    El campo en el producto se llama  font_size_<field_key>
    (ej: font_size_titulo_1, font_size_descripcion, font_size_precio).
    """
    raw = product.get(f"font_size_{field_key}")
    if raw:
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            pass
    return default


def precompute_slide(product: dict, cfg: dict) -> dict:
    """
    Calcula una sola vez (por slide) las fuentes y el texto partido en líneas.
    El font_size de cada elemento puede ser sobreescrito por el producto.
    Soporta templates 'centered' (por defecto) y 'split' (panel izquierdo de texto
    + panel derecho de vídeo que entra desde la derecha).
    """
    safe_m   = cfg["safe_margin"]
    template = product.get("template", "centered")

    if template == "split":
        # split_ratio: fracción del canvas donde empieza el panel de vídeo.
        # 0.5 → panel desde el 50% · 0.4 → panel desde el 40% …
        # El TEXTO usa el ancho completo del canvas (igual que centered) pero
        # alineado a la izquierda y con z-order por encima del panel de vídeo.
        split_ratio = float(product.get("split_ratio", cfg.get("split_ratio", 0.5)))
        split_x     = int(CANVAS_W * split_ratio)   # x donde empieza el panel de vídeo
        text_w      = CANVAS_W - 2 * safe_m         # texto usa todo el ancho disponible
        cx          = CANVAS_W // 2                 # cx no se usa (texto es left-aligned)
        x_left      = safe_m                        # alineación izquierda desde margen
    else:
        split_ratio = 0.5
        split_x     = CANVAS_W // 2
        text_w      = CANVAS_W - 2 * safe_m
        cx          = CANVAS_W // 2
        x_left      = None

    titles_cfg = cfg.get("titles") or [cfg.get("title", {})]
    d_cfg      = cfg["description"]
    p_cfg      = cfg["price"]
    pb_cfg     = cfg.get("price_before")

    # Tamaños efectivos (config por defecto, sobreescrito por el producto)
    eff_title_sizes = [
        _resolve_font_size(product, tc.get("field", f"titulo_{i+1}"), tc["font_size"])
        for i, tc in enumerate(titles_cfg)
    ]
    eff_desc_size   = _resolve_font_size(product, "descripcion", d_cfg["font_size"])
    eff_price_size  = _resolve_font_size(product, "precio",      p_cfg["font_size"])
    eff_pb_size     = _resolve_font_size(product, "precio_antes", pb_cfg["font_size"]) if pb_cfg else 0

    fonts_title  = [
        get_font(eff_title_sizes[i], bold=True, font_name=tc.get("font"))
        for i, tc in enumerate(titles_cfg)
    ]
    titles_lines = [
        wrap_text(str(product.get(tc.get("field", "titulo_1")) or ""), f, text_w)
        for tc, f in zip(titles_cfg, fonts_title)
    ]

    font_desc  = get_font(eff_desc_size,  bold=False, font_name=d_cfg.get("font"))
    font_price = get_font(eff_price_size, bold=True,  font_name=p_cfg.get("font"))
    font_price_before = (
        get_font(eff_pb_size, bold=False, font_name=pb_cfg.get("font"))
        if pb_cfg else None
    )

    # Pre-computar todos los valores estáticos de render (no cambian entre frames)
    titles_render = [
        {
            "color":          tuple(tc["color"]),
            "line_spacing":   float(tc.get("line_height", 1.25)),
            "letter_spacing": _parse_px(tc.get("letter_spacing", 0)),
            "shadow":         bool(tc.get("shadow", True)),
            "appear_at":      tc["appear_at"],
            "fade_duration":  tc["fade_duration"],
        }
        for tc in titles_cfg
    ]
    desc_render = {
        "color":          tuple(d_cfg["color"]),
        "line_spacing":   float(d_cfg.get("line_height", 1.25)),
        "letter_spacing": _parse_px(d_cfg.get("letter_spacing", 0)),
        "shadow":         bool(d_cfg.get("shadow", True)),
        "appear_at":      d_cfg["appear_at"],
        "fade_duration":  d_cfg["fade_duration"],
    }
    price_render = {
        "color":          tuple(p_cfg["color"]),
        "letter_spacing": _parse_px(p_cfg.get("letter_spacing", 0)),
        "shadow":         bool(p_cfg.get("shadow", True)),
        "appear_at":      p_cfg["appear_at"],
        "fade_duration":  p_cfg["fade_duration"],
        "badge":          p_cfg.get("badge") or None,
    }
    pb_render = {
        "color":          tuple(pb_cfg.get("color",              [170, 170, 170])) if pb_cfg else (170, 170, 170),
        "strike_color":   tuple(pb_cfg.get("strikethrough_color", [220, 80, 80]))  if pb_cfg else (220, 80, 80),
        "letter_spacing": _parse_px(pb_cfg.get("letter_spacing", 0)) if pb_cfg else 0,
        "shadow":         bool(pb_cfg.get("shadow", True)) if pb_cfg else True,
        "gap":            int(pb_cfg.get("gap", 100)) if pb_cfg else 100,
        "badge":          pb_cfg.get("badge") or None if pb_cfg else None,
    } if pb_cfg else None

    return {
        "fonts_title":        fonts_title,
        "titles_lines":       titles_lines,
        "font_desc":          font_desc,
        "font_price":         font_price,
        "font_price_before":  font_price_before,
        "desc_lines":         wrap_text(str(product.get("descripcion") or ""), font_desc, text_w),
        "price_lines":        [str(product.get("precio") or "")],
        "price_before_text":  str(product.get("precio_antes") or ""),
        "eff_title_sizes":    eff_title_sizes,
        # Valores estáticos pre-computados para evitar recalcular en cada frame
        "titles_render":      titles_render,
        "desc_render":        desc_render,
        "price_render":       price_render,
        "pb_render":          pb_render,
        # Layout
        "template":           template,
        "cx":                 cx,
        "x_left":             x_left,
        "split_x":            split_x,   # x donde empieza el panel de vídeo
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  RENDERIZADO DE UN FRAME
# ═══════════════════════════════════════════════════════════════════════════════

def render_frame(
    bg_arr:    np.ndarray,
    precomp:   dict,
    cfg:       dict,
    t:         float,
    slide_dur: float,
    overlay:   Image.Image,
    vignette:  Image.Image,
    logo_img:        Optional[Image.Image]     = None,
    logo_pos:        Optional[tuple[int, int]] = None,
    logo_footer_img: Optional[Image.Image]     = None,
    logo_footer_pos: Optional[tuple[int, int]] = None,
    t_global:        float                     = 0.0,
    total_video_dur: float                     = 0.0,
) -> bytes:
    """
    Genera un único frame RGB24 en el instante t y lo devuelve como bytes.
    """
    safe_m     = cfg["safe_margin"]
    split_safe = cfg["split_safe_zone"]
    fade_out   = cfg["fade_out_duration"]
    fo_start   = slide_dur - fade_out

    titles_cfg = cfg.get("titles") or [cfg.get("title", {})]
    d_cfg      = cfg["description"]
    p_cfg      = cfg["price"]

    # ── 1. Canvas base + fondo (depende del template) ────────────────────────
    bg_appear_at   = cfg.get("bg_appear_at",  0.0)
    intro_r, intro_g, intro_b = cfg.get("intro_bg_color", [10, 10, 14])
    bg_alpha = calc_alpha(t, bg_appear_at, 0.8, fo_start, fade_out)

    canvas   = Image.new("RGBA", (CANVAS_W, CANVAS_H), (intro_r, intro_g, intro_b, 255))
    template = precomp.get("template", "centered")

    ov_appear  = cfg.get("overlay_appear_at",    0.6)
    ov_fade_in = cfg.get("overlay_fade_duration", 1.2)
    ov_alpha   = calc_alpha(t, ov_appear, ov_fade_in, fo_start, fade_out)

    if template == "split":
        # ── TEMPLATE SPLIT ────────────────────────────────────────────────────
        # split_x: x donde empieza la zona de vídeo (leído del precomp)
        # El panel ocupa [split_x, CANVAS_W] en su posición final.
        # Entra desde la derecha con animación ease-out cúbico.
        split_x         = precomp.get("split_x", CANVAS_W // 2)
        video_panel_w   = CANVAS_W - split_x          # ancho del panel de vídeo
        panel_slide_dur = float(cfg.get("panel_slide_duration", 0.7))
        t_since         = max(0.0, t - bg_appear_at)
        p_raw           = min(1.0, t_since / panel_slide_dur) if panel_slide_dur > 0 else 1.0
        progress        = 1.0 - (1.0 - p_raw) ** 3   # ease-out cúbico

        # x_panel: CANVAS_W (fuera) → split_x (posición final)
        x_panel = split_x + int(video_panel_w * (1.0 - progress))

        if bg_alpha > 0.01:
            int_bg_a = int(bg_alpha * 255)
            # bg_arr ya tiene dimensiones (CANVAS_H, video_panel_w, 3) —
            # cargado exactamente al tamaño del panel (ocupa todo el alto).
            paste_w = min(video_panel_w, CANVAS_W - x_panel)
            # El panel de vídeo se pinta ENCIMA del canvas oscuro (sin overlay).
            # Orden de profundidad: fondo oscuro → vídeo → texto/logos.
            if paste_w > 0:
                rgba      = np.empty((CANVAS_H, paste_w, 4), dtype=np.uint8)
                rgba[:, :, :3] = bg_arr[:, :paste_w]
                rgba[:, :, 3]  = int_bg_a
                canvas.alpha_composite(Image.fromarray(rgba, "RGBA"), dest=(x_panel, 0))


    else:
        # ── TEMPLATE CENTERED (lógica original) ───────────────────────────────
        if bg_alpha > 0.01:
            # ── Ken Burns: zoom lento desde 100 % hasta (100 + bg_zoom) % ─────
            bg_zoom = cfg.get("bg_zoom", 0.0)
            if bg_zoom > 0.0:
                t_norm  = min(t / slide_dur, 1.0)
                zoom    = 1.0 + bg_zoom * t_norm
                new_w   = int(CANVAS_W * zoom)
                new_h   = int(CANVAS_H * zoom)
                zoomed  = Image.fromarray(bg_arr, "RGB").resize(
                    (new_w, new_h), Image.BILINEAR
                )
                ox = (new_w - CANVAS_W) // 2
                oy = (new_h - CANVAS_H) // 2
                bg_img = zoomed.crop((ox, oy, ox + CANVAS_W, oy + CANVAS_H)).convert("RGBA")
            else:
                bg_img = Image.fromarray(bg_arr, "RGB").convert("RGBA")

            bg_data = np.array(bg_img)
            bg_data[:, :, 3] = int(bg_alpha * 255)
            canvas.alpha_composite(Image.fromarray(bg_data, "RGBA"))

            # ── 2. Overlay ────────────────────────────────────────────────────
            if ov_alpha > 0.01:
                ov_arr = np.array(overlay)
                ov_arr[:, :, 3] = (ov_arr[:, :, 3].astype(float) * ov_alpha).astype(np.uint8)
                canvas.alpha_composite(Image.fromarray(ov_arr, "RGBA"))

            # ── 3. Viñeta ─────────────────────────────────────────────────────
            vig_arr = np.array(vignette)
            vig_arr[:, :, 3] = (vig_arr[:, :, 3].astype(float) * bg_alpha).astype(np.uint8)
            canvas.alpha_composite(Image.fromarray(vig_arr, "RGBA"))

    # ── Centros verticales de cada zona de texto ──────────────────────────────
    #   TV superior  : y ∈ [safe_m, TV_SPLIT - split_safe]
    #   TV inferior  : y ∈ [TV_SPLIT + split_safe, CANVAS_H - safe_m]
    tv_top_start     = safe_m
    tv_top_end       = TV_SPLIT - split_safe
    tv_top_span      = tv_top_end - tv_top_start
    tv_bottom_top    = TV_SPLIT + split_safe + safe_m
    tv_bottom_bottom = CANVAS_H - safe_m
    tv_bottom_span   = tv_bottom_bottom - tv_bottom_top

    # Posicionar títulos secuencialmente con margin_top por título.
    # Usamos la altura real del bloque renderizado (n_líneas × line_h × spacing)
    # para que cuando un título ocupe 2–3 líneas empuje hacia abajo al siguiente.
    def _title_block_half_h(font, n_lines: int, line_spacing: float) -> int:
        bbox = _MEASURE_DRAW.textbbox((0, 0), "Ágjy", font=font)
        lh   = bbox[3] - bbox[1]
        return int(lh * line_spacing * n_lines / 2)

    n_titles  = len(titles_cfg)
    title_cys: list[int] = []
    for i, tc in enumerate(titles_cfg):
        font_i    = precomp["fonts_title"][i]
        n_lines_i = len(precomp["titles_lines"][i])
        ls_i      = float(tc.get("line_height", 1.25))
        half_h    = _title_block_half_h(font_i, n_lines_i, ls_i)
        if i == 0:
            default_mt = int(tv_top_span * 0.25)
            cy = tv_top_start + tc.get("margin_top", default_mt) + half_h
        else:
            prev_tc      = titles_cfg[i - 1]
            prev_font    = precomp["fonts_title"][i - 1]
            prev_n_lines = len(precomp["titles_lines"][i - 1])
            prev_ls      = float(prev_tc.get("line_height", 1.25))
            prev_half    = _title_block_half_h(prev_font, prev_n_lines, prev_ls)
            default_mt   = int(precomp["eff_title_sizes"][i - 1] * 0.3)
            cy = title_cys[-1] + prev_half + tc.get("margin_top", default_mt) + half_h
        title_cys.append(cy)

    # Descripción: 30 % desde arriba de la zona inferior
    desc_cy  = tv_bottom_top + int(tv_bottom_span * 0.28)

    # Precio: 68 % desde arriba de la zona inferior
    price_cy = tv_bottom_top + int(tv_bottom_span * 0.68)

    cx     = precomp.get("cx",    CANVAS_W // 2)
    x_left = precomp.get("x_left", None)

    # ── 4. Títulos (TV superior) ───────────────────────────────────────────────
    for i, (tr, lines, font, cy) in enumerate(
        zip(precomp["titles_render"], precomp["titles_lines"], precomp["fonts_title"], title_cys)
    ):
        alpha = calc_alpha(t, tr["appear_at"], tr["fade_duration"], fo_start, fade_out)
        draw_text_centered(
            canvas, lines, font,
            cx, cy,
            color=tr["color"],
            alpha=alpha,
            line_spacing=tr["line_spacing"],
            letter_spacing=tr["letter_spacing"],
            shadow=tr["shadow"],
            x_left=x_left,
        )

    # ── 5. Descripción ─────────────────────────────────────────────────────────
    dr         = precomp["desc_render"]
    desc_alpha = calc_alpha(t, dr["appear_at"], dr["fade_duration"], fo_start, fade_out)
    draw_text_centered(
        canvas, precomp["desc_lines"], precomp["font_desc"],
        cx, desc_cy,
        color=dr["color"],
        alpha=desc_alpha,
        line_spacing=dr["line_spacing"],
        letter_spacing=dr["letter_spacing"],
        shadow=dr["shadow"],
        x_left=x_left,
    )

    # ── 6. Precio (con tachado opcional) ──────────────────────────────────────
    pr          = precomp["price_render"]
    pbr         = precomp["pb_render"]
    price_alpha = calc_alpha(t, pr["appear_at"], pr["fade_duration"], fo_start, fade_out)
    draw_prices(
        canvas,
        price_text   = precomp["price_lines"][0],
        font_price   = precomp["font_price"],
        price_color  = pr["color"],
        before_text  = precomp["price_before_text"],
        font_before  = precomp["font_price_before"],
        before_color = pbr["color"]        if pbr else (170, 170, 170),
        strike_color = pbr["strike_color"] if pbr else (220,  80,  80),
        cx     = cx,
        cy     = price_cy,
        alpha  = price_alpha,
        gap    = pbr["gap"] if pbr else 100,
        shadow_color          = (0, 0, 0),
        letter_spacing        = pr["letter_spacing"],
        letter_spacing_before = pbr["letter_spacing"] if pbr else 0,
        price_badge           = pr["badge"],
        price_before_badge    = pbr["badge"] if pbr else None,
        shadow                = pr["shadow"],
        shadow_before         = pbr["shadow"] if pbr else True,
        x_left                = x_left,
    )

    # ── 7. Logos (globales: entran una vez, se mantienen y salen al final) ────
    for cfg_key, l_img, l_pos in (
        ("logo",        logo_img,        logo_pos),
        ("logo_footer", logo_footer_img, logo_footer_pos),
    ):
        if l_img is None or l_pos is None:
            continue
        l_cfg            = cfg.get(cfg_key, {})
        alpha, anim_pos  = calc_logo_global_anim(
            t_global, total_video_dur, l_cfg, l_pos, l_img.size
        )
        composite_logo(canvas, l_img, anim_pos, alpha)

    return canvas.convert("RGB").tobytes()


# ═══════════════════════════════════════════════════════════════════════════════
#  CARGA DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

def load_products(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo de datos no encontrado: {path}")
    if p.suffix.lower() != ".json":
        raise ValueError(f"Formato no soportado: {p.suffix}  (usa .json)")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("productos", [])


def load_config(path: str = "config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
#  GENERACIÓN DEL VÍDEO
# ═══════════════════════════════════════════════════════════════════════════════

def generate_video(products: list[dict], cfg: dict, output_path: str) -> None:
    fps         = cfg["fps"]
    _all_elems  = (cfg.get("titles") or [cfg.get("title", {})]) + [cfg["description"], cfg["price"]]
    _last_t     = max(e.get("appear_at", 0) + e.get("fade_duration", 0) for e in _all_elems)
    default_dur = _last_t + cfg.get("hold_duration", 2.0) + cfg["fade_out_duration"]
    n           = len(products)

    total_frames = sum(
        int(fps * float(p.get("duracion", default_dur))) for p in products
    )
    total_secs = total_frames / fps

    print(f"\n  Slides      : {n}")
    print(f"  Resolución  : {CANVAS_W}×{CANVAS_H} px")
    print(f"  FPS         : {fps}")
    print(f"  Duración    : {total_secs:.1f} s  ({total_frames} frames)")
    print(f"  Salida      : {output_path}\n")

    # Pre-construir overlay, viñeta y logo (constantes para todo el vídeo)
    overlay  = make_overlay(cfg["overlay_alpha"])
    vig_arr  = make_vignette(cfg.get("vignette_strength", 70))
    vignette = Image.fromarray(vig_arr, "RGBA")
    logo_img        = load_logo_from_cfg(cfg.get("logo"))
    logo_pos        = compute_logo_pos_from_cfg(logo_img, cfg.get("logo", {})) if logo_img is not None else None
    logo_footer_img = load_logo_from_cfg(cfg.get("logo_footer"))
    logo_footer_pos = compute_logo_pos_from_cfg(logo_footer_img, cfg.get("logo_footer", {})) if logo_footer_img is not None else None

    # FFmpeg: recibe frames RGB24 en stdin y los codifica en H.264
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f",        "rawvideo",
        "-vcodec",   "rawvideo",
        "-s",        f"{CANVAS_W}x{CANVAS_H}",
        "-pix_fmt",  "rgb24",
        "-r",        str(fps),
        "-i",        "pipe:0",
        "-vcodec",   "libx264",
        "-pix_fmt",  "yuv420p",
        "-preset",   cfg.get("encoder_preset", "slow"),
        "-crf",      str(cfg.get("encoder_crf", 18)),
        "-movflags", "+faststart",
        output_path,
    ]

    import threading

    # stderr → fichero temporal para evitar deadlock por buffer lleno
    # (si usáramos PIPE y llamáramos a proc.wait() antes de leer stderr,
    #  FFmpeg se bloquearía escribiendo y nunca terminaría)
    import tempfile
    _stderr_file = tempfile.TemporaryFile()

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stderr=_stderr_file,
    )

    frames_written  = 0
    t_global_base   = 0.0
    bar_width       = 36
    ffmpeg_error    = False

    def print_progress(label: str, pct: float) -> None:
        filled = int(bar_width * pct / 100)
        bar    = "█" * filled + "░" * (bar_width - filled)
        print(f"\r  {pct:5.1f}%  [{bar}]  {label:<35}", end="", flush=True)

    try:
        for idx, product in enumerate(products):
            slide_dur    = float(product.get("duracion", default_dur))
            frames_slide = int(fps * slide_dur)
            _name        = product.get("producto") or product.get("titulo_1") or f"Slide {idx + 1}"
            label        = f"({idx + 1}/{n}) {_name}"

            # Para el template 'split' cargamos el fondo exactamente al tamaño del
            # panel de vídeo (video_panel_w × CANVAS_H) para que ocupe todo el alto
            # sin ser un recorte del canvas completo.
            _template    = product.get("template", "centered")
            if _template == "split":
                _split_ratio = float(product.get("split_ratio", cfg.get("split_ratio", 0.5)))
                _split_x     = int(CANVAS_W * _split_ratio)
                _bg_w        = CANVAS_W - _split_x   # ancho del panel de vídeo
            else:
                _bg_w = CANVAS_W
            bg_source = load_background_source(
                product.get("imagen") or product.get("fondo"), fps, _bg_w, CANVAS_H
            )
            is_video  = isinstance(bg_source, VideoBackground)
            precomp   = precompute_slide(product, cfg)

            for fi in range(frames_slide):
                # Comprobar si FFmpeg murió antes de tiempo
                if proc.poll() is not None:
                    ffmpeg_error = True
                    break

                bg_arr   = bg_source.get_next_frame() if is_video else bg_source
                t        = fi / fps
                t_global = t_global_base + t
                frame    = render_frame(
                    bg_arr, precomp, cfg, t, slide_dur, overlay, vignette,
                    logo_img, logo_pos, logo_footer_img, logo_footer_pos,
                    t_global, total_secs,
                )
                try:
                    proc.stdin.write(frame)
                except BrokenPipeError:
                    ffmpeg_error = True
                    break

                frames_written += 1
                print_progress(label, frames_written / total_frames * 100)

            if is_video:
                bg_source.close()
            if ffmpeg_error:
                break
            t_global_base += slide_dur   # acumular duración exacta (sin drift)

    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass

    ret = proc.wait()

    # Leer stderr del fichero temporal (ya sin riesgo de deadlock)
    _stderr_file.seek(0)
    stderr_output = _stderr_file.read().decode("utf-8", errors="replace").strip()
    _stderr_file.close()

    print_progress("¡Completado!", 100.0)
    print()  # nueva línea al terminar

    if ret == 0 and not ffmpeg_error:
        size_mb = Path(output_path).stat().st_size / (1024 ** 2)
        print(f"\n  ✅  Vídeo generado correctamente ({size_mb:.1f} MB)")
        print(f"      → {Path(output_path).resolve()}")
    else:
        print(f"\n  ❌  FFmpeg terminó con error (código {ret})", file=sys.stderr)
        if stderr_output:
            # Mostrar las últimas 20 líneas del log de FFmpeg
            lines = stderr_output.splitlines()
            print("\n  — Log de FFmpeg —", file=sys.stderr)
            for line in lines[-20:]:
                print(f"  {line}", file=sys.stderr)
        sys.exit(ret if ret != 0 else 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERFAZ DE LÍNEA DE COMANDOS
# ═══════════════════════════════════════════════════════════════════════════════

def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generador de vídeos promocionales para escaparate dual 4K",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "-d", "--data",
        default="data/products.json",
        help="Ruta al archivo de productos (.json)",
    )
    p.add_argument(
        "-c", "--config",
        default="config.json",
        help="Archivo de configuración visual",
    )
    p.add_argument(
        "-o", "--output",
        default="output/escaparate.mp4",
        help="Ruta del vídeo MP4 de salida",
    )
    return p


def main() -> None:
    args = build_cli().parse_args()

    print("═" * 60)
    print("  VideoGenerator — Escaparate Dual 4K")
    print("═" * 60)

    # Verificar dependencia de FFmpeg — busca en PATH y rutas comunes de macOS/Linux
    _FFMPEG_EXTRA = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    ffmpeg_path = shutil.which("ffmpeg") or next(
        (p for d in _FFMPEG_EXTRA if (p := str(Path(d) / "ffmpeg")) and Path(p).exists()),
        None,
    )
    if not ffmpeg_path:
        print("  ❌  FFmpeg no encontrado. Instálalo con: brew install ffmpeg", file=sys.stderr)
        sys.exit(1)
    os.environ["PATH"] = os.pathsep.join(_FFMPEG_EXTRA) + os.pathsep + os.environ.get("PATH", "")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    cfg      = load_config(args.config)
    products = load_products(args.data)

    if not products:
        print("  ❌  No hay productos en el archivo de datos.", file=sys.stderr)
        sys.exit(1)

    generate_video(products, cfg, args.output)


if __name__ == "__main__":
    main()
