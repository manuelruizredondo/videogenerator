#!/usr/bin/env python3
"""
preview.py — Genera un preview HTML estático de todos los slides.
Muestra el layout, tipografía, colores y zonas seguras a escala.

Uso:
    python preview.py
    python preview.py -d data/products.json -c config.json -o output/preview.html
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import ImageFont as _PILFont, Image as _PILImage, ImageDraw as _PILDraw
    _pil_available = True
except ImportError:
    _pil_available = False

CANVAS_W = 3840
CANVAS_H = 4320
TV_SPLIT = 2160

PREVIEW_W = 500                          # Ancho del slide en el preview (px)
SCALE     = PREVIEW_W / CANVAS_W        # 0.13020…
PREVIEW_H = round(CANVAS_H * SCALE)     # ~562 px


# ─── Utilidades ───────────────────────────────────────────────────────────────

def sc(px: float) -> str:
    """Convierte píxeles del canvas al tamaño del preview."""
    return f"{px * SCALE:.2f}px"


def rgb(color: list) -> str:
    return f"rgb({color[0]},{color[1]},{color[2]})"


def parse_px(value, default: int = 0) -> int:
    """Convierte '7px', '7', 7, 7.0… a int."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    return int(str(value).lower().replace("px", "").strip() or default)


def resolve_font_size(product: dict, field_key: str, default: int) -> int:
    """Devuelve el font_size efectivo: producto > config."""
    raw = product.get(f"font_size_{field_key}")
    if raw:
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            pass
    return default


# Caracteres representativos para calcular la corrección bbox → advance
_SAMPLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_ls_corr_cache: dict    = {}
_glyph_h_cache: dict    = {}


def _ls_correction(font_path: str, canvas_font_size: int) -> float:
    """
    Diferencia media (bbox_width − advance_width) × SCALE para una fuente.

    El vídeo (Pillow) avanza por bbox_width + letter_spacing, mientras que
    el CSS avanza por advance_width + letter-spacing. Para que el HTML
    replique el spacing visual del vídeo hay que añadir esta corrección
    al letter-spacing CSS de cada elemento.
    """
    if not _pil_available:
        return 0.0
    key = (font_path, canvas_font_size)
    if key in _ls_corr_cache:
        return _ls_corr_cache[key]
    try:
        path = resolve_path(font_path)
        font = _PILFont.truetype(str(path), canvas_font_size)
        img  = _PILImage.new("RGBA", (canvas_font_size * 2, canvas_font_size * 2))
        drw  = _PILDraw.Draw(img)
        diffs = []
        for ch in _SAMPLE_CHARS:
            bb   = drw.textbbox((0, 0), ch, font=font)
            bbox_w  = bb[2] - bb[0]
            adv_w   = int(font.getlength(ch))
            diffs.append(bbox_w - adv_w)
        result = (sum(diffs) / len(diffs)) * SCALE
    except Exception:
        result = 0.0
    _ls_corr_cache[key] = result
    return result


def _title_block_half_h(font_path: str, canvas_font_size: int,
                         n_lines: int, line_spacing: float) -> int:
    """
    Semialtura del bloque de título en píxeles CANVAS.
    Equivalente exacto a generate_video._title_block_half_h().
    """
    if not _pil_available:
        return int(canvas_font_size * line_spacing * n_lines / 2)
    try:
        path = resolve_path(font_path)
        font = _PILFont.truetype(str(path), canvas_font_size)
        img  = _PILImage.new("RGBA", (canvas_font_size * 4, canvas_font_size * 2))
        drw  = _PILDraw.Draw(img)
        bb   = drw.textbbox((0, 0), "Ágjy", font=font)
        lh   = bb[3] - bb[1]
        return int(lh * line_spacing * n_lines / 2)
    except Exception:
        return int(canvas_font_size * line_spacing * n_lines / 2)


def _glyph_height_css(font_path: str, canvas_font_size: int) -> float:
    """
    Altura visual del glifo (bb[3] - bb[1]) en píxeles CSS.
    Equivalente a la altura que el vídeo usa para dimensionar el badge.
    """
    if not _pil_available:
        return canvas_font_size * SCALE
    key = (font_path, canvas_font_size)
    if key in _glyph_h_cache:
        return _glyph_h_cache[key]
    try:
        path = resolve_path(font_path)
        font = _PILFont.truetype(str(path), canvas_font_size)
        img  = _PILImage.new("RGBA", (canvas_font_size * 20, canvas_font_size * 2))
        drw  = _PILDraw.Draw(img)
        # Muestra representativa de caracteres de precio
        bb = drw.textbbox((0, 0), "0123456789€$ Desde", font=font)
        result = (bb[3] - bb[1]) * SCALE
    except Exception:
        result = canvas_font_size * SCALE
    _glyph_h_cache[key] = result
    return result


PROJECT_ROOT = Path(__file__).parent


def resolve_path(path: str) -> Path:
    """Resuelve una ruta relativa al directorio del proyecto."""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return PROJECT_ROOT / p


def image_url(img_path: str, output_path: str) -> str:
    """
    Devuelve una ruta relativa desde el HTML de salida hasta la imagen.
    Si la imagen no existe devuelve ''.
    """
    src = resolve_path(img_path)
    if not src.exists():
        return ""
    return os.path.relpath(src, start=Path(output_path).parent)


_VIDEO_EXTS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".mts"})

def is_video_path(path: str) -> bool:
    return bool(path) and Path(path).suffix.lower() in _VIDEO_EXTS


def load_json(path: str) -> dict | list:
    p = resolve_path(path)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ─── Generación de slides ─────────────────────────────────────────────────────

def font_family_name(font_file: str) -> str:
    """Devuelve un nombre CSS válido para el @font-face a partir del nombre de archivo."""
    return Path(font_file).stem   # ej: 'Montserrat-Bold.ttf' → 'Montserrat-Bold'


def font_weight_from_name(font_file: str) -> int:
    """Infiere el font-weight numérico a partir del nombre del archivo."""
    name = Path(font_file).stem.lower()
    if any(k in name for k in ("black", "heavy", "extrabold", "extra-bold")):
        return 900
    if any(k in name for k in ("bold",)):
        return 700
    if any(k in name for k in ("semibold", "semi-bold", "medium", "demi")):
        return 600
    if any(k in name for k in ("light", "thin", "extralight")):
        return 300
    return 400


def compute_logo_preview(cfg: dict, output_path: str, section: str = "logo") -> str:
    """Genera el HTML de un logo (header o footer) para el preview."""
    l_cfg = cfg.get(section)
    if not l_cfg or not l_cfg.get("file"):
        return ""

    logo_url = image_url(l_cfg["file"], output_path)
    if not logo_url:
        return ""

    lw_preview = int(l_cfg.get("width", 400)) * SCALE
    position   = l_cfg.get("position", "top-center")
    mt = int(l_cfg.get("margin_top",  150)) * SCALE
    ms = int(l_cfg.get("margin_side", 150)) * SCALE

    if isinstance(position, list) and len(position) == 2:
        style = f"left:{position[0]*SCALE:.2f}px;top:{position[1]*SCALE:.2f}px;"
    elif position == "top-left":
        style = f"left:{ms:.2f}px;top:{mt:.2f}px;"
    elif position == "top-right":
        style = f"right:{ms:.2f}px;top:{mt:.2f}px;"
    elif position == "bottom-center":
        style = f"left:50%;transform:translateX(-50%);bottom:{mt:.2f}px;"
    elif position == "bottom-left":
        style = f"left:{ms:.2f}px;bottom:{mt:.2f}px;"
    elif position == "bottom-right":
        style = f"right:{ms:.2f}px;bottom:{mt:.2f}px;"
    else:  # top-center
        style = f"left:50%;transform:translateX(-50%);top:{mt:.2f}px;"

    return (
        f'<img src="{logo_url}" alt="{section}" style="'
        f'position:absolute;{style}'
        f'width:{lw_preview:.2f}px;height:auto;'
        f'object-fit:contain;z-index:10;pointer-events:none;">'
    )


def build_slide(product: dict, cfg: dict, index: int, total: int, output_path: str) -> str:
    safe_m     = cfg["safe_margin"]
    split_safe = cfg["split_safe_zone"]
    _all_elems   = (cfg.get("titles") or [cfg.get("title", {})]) + [cfg["description"], cfg["price"]]
    _last_t      = max(e.get("appear_at", 0) + e.get("fade_duration", 0) for e in _all_elems)
    _default_dur = _last_t + cfg.get("hold_duration", 2.0) + cfg["fade_out_duration"]
    duration     = float(product.get("duracion", _default_dur))

    # Template del slide
    template = product.get("template", "centered")
    is_split  = template == "split"

    # split_ratio: fracción del canvas para el texto (0.5 = 50/50, 0.4 = 40/60…)
    split_ratio   = float(product.get("split_ratio", cfg.get("split_ratio", 0.5))) if is_split else 0.5
    split_pct     = split_ratio * 100          # CSS: % del slide para el texto
    video_pct     = (1.0 - split_ratio) * 100  # CSS: % del slide para el vídeo

    # Color de fondo de intro (usado como bg del panel izquierdo en split)
    intro_bg = cfg.get("intro_bg_color", [10, 10, 14])
    intro_bg_css = f"rgb({intro_bg[0]},{intro_bg[1]},{intro_bg[2]})"

    # Posiciones Y (misma lógica que generate_video.py)
    tv_bottom_top    = TV_SPLIT + split_safe + safe_m
    tv_bottom_bottom = CANVAS_H - safe_m
    tv_bottom_span   = tv_bottom_bottom - tv_bottom_top
    desc_cy          = tv_bottom_top + int(tv_bottom_span * 0.28)
    price_cy         = tv_bottom_top + int(tv_bottom_span * 0.68)

    # Fondo (imagen o vídeo)
    bg_path     = product.get("imagen") or product.get("fondo", "")
    bg_is_video = is_video_path(bg_path)
    bg_url      = image_url(bg_path, output_path) if bg_path else ""

    # Para split: el fondo va en el panel derecho; el div base tiene el color de intro
    if is_split:
        base_bg_style = f"background:{intro_bg_css};"
        if bg_is_video and bg_url:
            panel_media_html = (
                f'<video autoplay muted loop playsinline style="'
                f'width:100%;height:100%;object-fit:cover;">'
                f'<source src="{bg_url}"></video>'
            )
        elif bg_url:
            panel_media_html = (
                f'<img src="{bg_url}" style="'
                f'width:100%;height:100%;object-fit:cover;">'
            )
        else:
            panel_media_html = f'<div style="width:100%;height:100%;background:{intro_bg_css};"></div>'
        bg_video_html = ""  # no se usa en split (va en el panel)
    else:
        base_bg_style = ""
        panel_media_html = ""
        if bg_is_video and bg_url:
            bg_style = "background:#000;"
            bg_video_html = (
                f'<video autoplay muted loop playsinline style="'
                f'position:absolute;inset:0;width:100%;height:100%;'
                f'object-fit:cover;z-index:0;">'
                f'<source src="{bg_url}"></video>'
            )
        elif bg_url:
            bg_style = (
                f"background-image:url('{bg_url}');"
                f"background-size:cover;background-position:center;"
            )
            bg_video_html = ""
        else:
            bg_style = "background:linear-gradient(175deg,#0d1b3e 0%,#0a2744 45%,#071830 100%);"
            bg_video_html = ""

    slide_bg_style = base_bg_style if is_split else bg_style
    overlay_a = cfg["overlay_alpha"] / 255 * 0.85  # estado intermedio visible

    # Títulos: extraer familias, tamaños y colores
    titles_cfg = cfg.get("titles") or [cfg.get("title", {})]
    t_families = [
        font_family_name(tc.get("font", "")) if tc.get("font") else "system-ui"
        for tc in titles_cfg
    ]
    eff_t_sizes = [
        resolve_font_size(product, tc.get("field", f"titulo_{i+1}"), tc["font_size"])
        for i, tc in enumerate(titles_cfg)
    ]
    t_fss    = [s * SCALE for s in eff_t_sizes]
    t_colors = [rgb(tc["color"]) for tc in titles_cfg]
    t_ls     = [
        parse_px(tc.get("letter_spacing", 0)) * SCALE
        + _ls_correction(tc.get("font", ""), tc["font_size"])
        for tc in titles_cfg
    ]
    t_weights = [font_weight_from_name(tc.get("font", "")) for tc in titles_cfg]
    t_lhs     = [float(tc.get("line_height", 1.25)) for tc in titles_cfg]
    t_shadows = [bool(tc.get("shadow", True)) for tc in titles_cfg]

    # Posicionar títulos secuencialmente con margin_top
    tv_top_start = safe_m
    tv_top_end   = TV_SPLIT - split_safe
    tv_top_span  = tv_top_end - tv_top_start
    n_titles     = len(titles_cfg)
    t_half_hs = [
        _title_block_half_h(
            tc.get("font", ""),
            eff_t_sizes[i],
            1,
            float(tc.get("line_height", 1.25)),
        )
        for i, tc in enumerate(titles_cfg)
    ]
    title_cys: list[int] = []
    for i, tc in enumerate(titles_cfg):
        half_h = t_half_hs[i]
        if i == 0:
            default_mt = int(tv_top_span * 0.25)
            cy = tv_top_start + tc.get("margin_top", default_mt) + half_h
        else:
            prev_half  = t_half_hs[i - 1]
            default_mt = int(eff_t_sizes[i - 1] * 0.3)
            cy = title_cys[-1] + prev_half + tc.get("margin_top", default_mt) + half_h
        title_cys.append(cy)

    d_family = font_family_name(cfg["description"].get("font", "")) if cfg["description"].get("font") else "system-ui"
    p_family = font_family_name(cfg["price"].get("font", ""))       if cfg["price"].get("font")       else "system-ui"

    eff_d_size = resolve_font_size(product, "descripcion", cfg["description"]["font_size"])
    eff_p_size = resolve_font_size(product, "precio",      cfg["price"]["font_size"])
    d_fs = eff_d_size * SCALE
    p_fs = eff_p_size * SCALE

    d_color = rgb(cfg["description"]["color"])
    p_color = rgb(cfg["price"]["color"])

    d_ls     = (parse_px(cfg["description"].get("letter_spacing", 0)) * SCALE
                + _ls_correction(cfg["description"].get("font", ""), eff_d_size))
    p_ls     = (parse_px(cfg["price"].get("letter_spacing", 0)) * SCALE
                + _ls_correction(cfg["price"].get("font", ""), eff_p_size))
    d_weight = font_weight_from_name(cfg["description"].get("font", ""))
    p_weight = font_weight_from_name(cfg["price"].get("font", ""))
    d_lh     = float(cfg["description"].get("line_height", 1.25))
    p_lh     = float(cfg["price"].get("line_height", 1.25))
    d_shadow = bool(cfg["description"].get("shadow", True))
    p_shadow = bool(cfg["price"].get("shadow", True))

    # Precio anterior (tachado)
    pb_cfg      = cfg.get("price_before")
    pb_shadow   = bool(pb_cfg.get("shadow", True)) if pb_cfg else True
    pb_family   = font_family_name(pb_cfg.get("font", "")) if (pb_cfg and pb_cfg.get("font")) else "system-ui"
    eff_pb_size = resolve_font_size(product, "precio_antes", pb_cfg["font_size"]) if pb_cfg else 0
    pb_fs       = eff_pb_size * SCALE if pb_cfg else 0
    pb_color    = rgb(pb_cfg["color"]) if pb_cfg else "rgb(170,170,170)"
    pb_strike   = rgb(pb_cfg.get("strikethrough_color", [220, 80, 80])) if pb_cfg else "rgb(220,80,80)"
    pb_gap      = (pb_cfg.get("gap", 100) * SCALE) if pb_cfg else 0
    pb_ls       = (
        parse_px(pb_cfg.get("letter_spacing", 0)) * SCALE
        + _ls_correction(pb_cfg.get("font", ""), eff_pb_size)
        if pb_cfg else 0
    )
    pb_weight = font_weight_from_name(pb_cfg.get("font", "")) if pb_cfg else 400

    def _badge_css(badge, font_path: str, canvas_font_size: int) -> str:
        if not badge:
            return ""
        bg  = badge.get("background", [0, 0, 0, 117])
        r, g, b, a = (int(v) for v in bg)
        px  = parse_px(badge.get("padding_x", badge.get("padding", 30))) * SCALE
        py  = parse_px(badge.get("padding_y", badge.get("padding", 30))) * SCALE
        rad = parse_px(badge.get("border_radius", 999)) * SCALE
        glyph_h = _glyph_height_css(font_path, canvas_font_size)
        h = glyph_h + 2 * py
        return (
            f"background:rgba({r},{g},{b},{a/255:.3f});"
            f"display:inline-flex;align-items:center;"
            f"height:{h:.2f}px;padding:0 {px:.2f}px;"
            f"border-radius:{rad:.2f}px;box-sizing:content-box;"
        )

    price_badge_css = _badge_css(
        cfg["price"].get("badge"), cfg["price"].get("font", ""), eff_p_size
    )
    price_before_badge_css = _badge_css(
        pb_cfg.get("badge") if pb_cfg else None,
        pb_cfg.get("font", "") if pb_cfg else "",
        eff_pb_size,
    )

    _SHADOW_TXT   = "text-shadow:1px 2px 6px rgba(0,0,0,.85),0 0 20px rgba(0,0,0,.5);"
    _SHADOW_PRICE = "text-shadow:1px 2px 10px rgba(0,0,0,.9);"
    _NO_SHADOW    = "text-shadow:none;"

    def _shadow_css(enabled: bool, strong: bool = False) -> str:
        if not enabled:
            return _NO_SHADOW
        return _SHADOW_PRICE if strong else _SHADOW_TXT

    pb_text = product.get("precio_antes") or ""

    # Zona segura
    safe_top_px    = (TV_SPLIT - split_safe) * SCALE
    safe_height_px = split_safe * 2 * SCALE

    logo_html        = compute_logo_preview(cfg, output_path, "logo")
    logo_footer_html = compute_logo_preview(cfg, output_path, "logo_footer")

    # ── Alineación de texto según template ───────────────────────────────────
    if is_split:
        # El texto usa el ancho completo del canvas (como en centered) pero
        # alineado a la izquierda. El panel de vídeo entra por detrás (z-index bajo).
        text_area_right  = f"{safe_m * SCALE:.2f}px"
        text_align_css   = "left"
        titles_align_css = "flex-start"
        price_justify    = "flex-start"
    else:
        text_area_right  = f"{safe_m * SCALE:.2f}px"
        text_align_css   = "center"
        titles_align_css = "center"
        price_justify    = "center"

    # Construir HTML de títulos
    titles_html = "".join(
        f'<div class="txt title-txt" style="'
        f'position:relative;transform:none;'
        f'margin-top:{(titles_cfg[i].get("margin_top", int((tv_top_end - tv_top_start) * 0.25) if i == 0 else int(titles_cfg[i-1]["font_size"] * 0.3))) * SCALE:.2f}px;'
        f'font-size:{t_fss[i]:.2f}px;'
        f"font-family:'{t_families[i]}',system-ui,sans-serif;"
        f'font-weight:{t_weights[i]};'
        f'line-height:{t_lhs[i]};'
        f'color:{t_colors[i]};'
        f'letter-spacing:{t_ls[i]:.2f}px;'
        f'{_shadow_css(t_shadows[i])}'
        f'width:100%;text-align:{text_align_css};">'
        f'{(product.get(titles_cfg[i].get("field","titulo_1")) or "").replace(chr(10), "<br>")}'
        f'</div>'
        for i in range(n_titles)
    )

    # ── HTML del panel derecho (solo split) ───────────────────────────────────
    if is_split:
        split_panel_html = f"""
        <!-- Panel derecho: entra desde la derecha ({video_pct:.0f}% del ancho) -->
        <!-- Orden z: fondo oscuro (base) → vídeo (encima) → texto/logos (top) -->
        <div class="split-panel" style="left:{split_pct:.2f}%;width:{video_pct:.2f}%;z-index:2;">
          {panel_media_html}
        </div>
"""
        full_overlay_html = ""  # sin overlay en el área de texto
    else:
        split_panel_html  = ""
        full_overlay_html = (
            f'<div style="position:absolute;inset:0;background:rgba(0,0,0,{overlay_a:.2f});'
            f'pointer-events:none;z-index:1;"></div>'
        )

    return f"""
    <div class="slide-wrapper" data-index="{index}">
      <div class="slide-meta">
        <span class="slide-num">Slide {index + 1} / {total}</span>
        <span class="slide-dur">{duration:.0f} s · {template}</span>
      </div>
      <div class="slide" style="{slide_bg_style}">

        <!-- Fondo de vídeo (template centered) -->
        {bg_video_html}

        <!-- Overlay / panel split -->
        {full_overlay_html}
        {split_panel_html}

        <!-- Logo header -->
        {logo_html}

        <!-- Logo footer -->
        {logo_footer_html}

        <!-- Títulos (TV superior) -->
        <div style="
            position:absolute;
            top:{tv_top_start * SCALE:.2f}px;
            left:{safe_m * SCALE:.2f}px;
            right:{text_area_right};
            display:flex;
            flex-direction:column;
            align-items:{titles_align_css};
            z-index:5;">
          {titles_html}
        </div>

        <!-- Descripción (TV inferior — arriba) -->
        <div class="txt desc-txt" style="
            top:{desc_cy * SCALE:.2f}px;
            font-size:{d_fs:.2f}px;
            font-family:'{d_family}',system-ui,sans-serif;
            font-weight:{d_weight};
            line-height:{d_lh};
            color:{d_color};
            letter-spacing:{d_ls:.2f}px;
            {_shadow_css(d_shadow)}
            left:{safe_m * SCALE:.2f}px;
            right:{text_area_right};
            text-align:{text_align_css};">
          {(product.get("descripcion") or "").replace(chr(10), "<br>")}
        </div>

        <!-- Precio (TV inferior — abajo; solo si hay texto) -->
        {(f'''<div style="
            position:absolute;
            top:{price_cy * SCALE:.2f}px;
            transform:translateY(-50%);
            left:{safe_m * SCALE:.2f}px;
            right:{text_area_right};
            display:flex;
            align-items:center;
            justify-content:{price_justify};
            gap:{pb_gap:.2f}px;
            z-index:5;">
          {(
            "<span style='"
            f"font-family:{pb_family},system-ui,sans-serif;"
            f"font-size:{pb_fs:.2f}px;"
            f"font-weight:{pb_weight};"
            f"color:{pb_color};"
            "text-decoration:line-through;"
            f"text-decoration-color:{pb_strike};"
            f"text-decoration-thickness:{max(2, round(pb_fs/12)):.0f}px;"
            f"letter-spacing:{pb_ls:.2f}px;"
            f"{_shadow_css(pb_shadow, strong=True)}"
            f"white-space:nowrap;{price_before_badge_css}'>"
            f"{pb_text.replace(chr(10), '<br>')}</span>"
          ) if (pb_cfg and pb_text) else ""}
          <span class="price-txt" style="
            font-family:'{p_family}',system-ui,sans-serif;
            font-size:{p_fs:.2f}px;
            font-weight:{p_weight};
            line-height:{p_lh};
            color:{p_color};
            letter-spacing:{p_ls:.2f}px;
            {_shadow_css(p_shadow, strong=True)}
            white-space:nowrap;
            {price_badge_css}">
            {(product.get("precio") or "").replace(chr(10), "<br>")}
          </span>
        </div>''') if ((product.get("precio") or "") or pb_text) else ""}

        <!-- Indicadores de zona segura (toggle) -->
        <div class="guide split-guide" style="top:{TV_SPLIT * SCALE:.2f}px;">
          <span class="guide-label">unión pantallas · y=2160</span>
        </div>
        <div class="guide safe-band" style="top:{safe_top_px:.2f}px;height:{safe_height_px:.2f}px;"></div>
        <div class="guide margin-top"    style="top:{safe_m * SCALE:.2f}px;"></div>
        <div class="guide margin-bottom" style="bottom:{safe_m * SCALE:.2f}px;"></div>
        <div class="guide margin-left"   style="left:{safe_m * SCALE:.2f}px;"></div>
        <div class="guide margin-right"  style="right:{safe_m * SCALE:.2f}px;"></div>

      </div>
      <div class="slide-title-label">{product.get("producto", "—")}</div>
    </div>"""


# ─── HTML completo ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Preview — Escaparate Dual 4K</title>
  <style>
    {font_faces}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:      #0e0e0e;
      --surface: #1a1a1a;
      --border:  #2a2a2a;
      --accent:  #f5a623;
      --red:     #ff4444;
      --yellow:  rgba(255,210,0,0.55);
    }}

    body {{
      background: var(--bg);
      color: #ddd;
      font-family: 'Montserrat', system-ui, sans-serif;
      padding: 32px 24px 64px;
      min-height: 100vh;
    }}

    /* ── Header ── */
    .header {{
      text-align: center;
      margin-bottom: 28px;
    }}
    .header h1 {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: .18em;
      text-transform: uppercase;
      color: #888;
      margin-bottom: 10px;
    }}
    .badges {{
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 11px;
    }}
    .badge {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 4px 12px;
      color: #777;
    }}

    /* ── Toolbar ── */
    .toolbar {{
      display: flex;
      justify-content: center;
      gap: 10px;
      margin-bottom: 36px;
      flex-wrap: wrap;
    }}
    .btn {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 16px;
      font-size: 11px;
      font-family: inherit;
      color: #aaa;
      cursor: pointer;
      letter-spacing: .06em;
      transition: background .15s, color .15s, border-color .15s;
    }}
    .btn:hover  {{ background: #252525; color: #ddd; }}
    .btn.active {{ background: #2a2a2a; border-color: var(--accent); color: var(--accent); }}

    /* ── Grid de slides ── */
    .slides-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 40px;
      justify-content: center;
    }}

    /* ── Wrapper individual ── */
    .slide-wrapper {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }}
    .slide-meta {{
      display: flex;
      width: {preview_w}px;
      justify-content: space-between;
      font-size: 10px;
      color: #555;
      letter-spacing: .06em;
      text-transform: uppercase;
    }}
    .slide-title-label {{
      font-size: 11px;
      color: #666;
      max-width: {preview_w}px;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    /* ── El slide ── */
    .slide {{
      width: {preview_w}px;
      height: {preview_h}px;
      position: relative;
      overflow: hidden;
      border-radius: 4px;
      border: 1px solid var(--border);
      cursor: crosshair;
      transition: box-shadow .2s;
    }}
    .slide:hover {{ box-shadow: 0 0 0 2px rgba(245,166,35,.35); }}

    /* ── Textos ── */
    .txt {{
      position: absolute;
      text-align: center;
      transform: translateY(-50%);
      line-height: 1.25;
      font-family: 'Montserrat', system-ui, sans-serif;
      word-break: break-word;
      hyphens: auto;
      z-index: 5;
    }}
    .title-txt  {{ font-weight: 900; }}
    .desc-txt   {{ font-weight: 400; }}
    .price-txt  {{ font-weight: 900; }}

    /* ── Guías (visibles solo con clase .show-guides en body) ── */
    .guide {{ position: absolute; pointer-events: none; display: none; }}
    body.show-guides .guide {{ display: block; }}

    .split-guide {{
      left: 0; right: 0; height: 1px;
      background: var(--red);
      opacity: .8;
      z-index: 20;
    }}
    .split-guide .guide-label {{
      position: absolute;
      right: 6px; top: 3px;
      font-size: 7px;
      color: var(--red);
      font-family: 'Montserrat', monospace;
      letter-spacing: .05em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .safe-band {{
      left: 0; right: 0;
      background: rgba(255,200,0,.07);
      border-top: 1px dashed rgba(255,200,0,.35);
      border-bottom: 1px dashed rgba(255,200,0,.35);
      z-index: 19;
    }}
    .margin-top    {{ left:0;right:0;height:1px;   background:rgba(0,200,255,.3); z-index:18; }}
    .margin-bottom {{ left:0;right:0;height:1px;   background:rgba(0,200,255,.3); z-index:18; }}
    .margin-left   {{ top:0;bottom:0;width:1px;    background:rgba(0,200,255,.3); z-index:18; }}
    .margin-right  {{ top:0;bottom:0;width:1px;    background:rgba(0,200,255,.3); z-index:18; }}

    /* ── Template SPLIT: panel derecho que entra desde la derecha ── */
    @keyframes slideInRight {{
      from {{ transform: translateX(100%); }}
      to   {{ transform: translateX(0);    }}
    }}
    .split-panel {{
      position: absolute;
      top: 0; bottom: 0;
      z-index: 0;
      animation: slideInRight 0.7s cubic-bezier(0,0,.2,1) forwards;
    }}
  </style>
</head>
<body>

  <div class="header">
    <h1>Preview — Escaparate Dual 4K</h1>
    <div class="badges">
      <span class="badge">3840 × 4320 px</span>
      <span class="badge">{n_slides} slides</span>
      <span class="badge">{total_dur:.0f} s totales</span>
      <span class="badge">{fps} fps · H.264</span>
      <span class="badge">Escala {scale_pct}%</span>
    </div>
  </div>

  <div class="toolbar">
    <button class="btn" id="btn-guides" onclick="toggleGuides()">Mostrar guías</button>
    <button class="btn" id="btn-fullscreen" onclick="toggleFullscreen()">Vista ampliada</button>
  </div>

  <div class="slides-grid" id="grid">
{slides_html}
  </div>

  <!-- Lightbox de ampliación -->
  <div id="lightbox" style="
      display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);
      z-index:999;align-items:center;justify-content:center;cursor:zoom-out;"
    onclick="closeLightbox()">
    <div id="lb-content" style="max-height:90vh;overflow-y:auto;padding:10px;">
    </div>
  </div>

  <script>
    let guidesOn = false;
    function toggleGuides() {{
      guidesOn = !guidesOn;
      document.body.classList.toggle('show-guides', guidesOn);
      document.getElementById('btn-guides').classList.toggle('active', guidesOn);
      document.getElementById('btn-guides').textContent = guidesOn ? 'Ocultar guías' : 'Mostrar guías';
    }}

    let fullscreen = false;
    function toggleFullscreen() {{
      fullscreen = !fullscreen;
      const grid = document.getElementById('grid');
      const btn  = document.getElementById('btn-fullscreen');
      const slides = document.querySelectorAll('.slide');
      const wrappers = document.querySelectorAll('.slide-wrapper');
      const targetW = fullscreen ? 800 : {preview_w};
      const targetH = fullscreen ? {preview_h_large} : {preview_h};
      slides.forEach(s => {{
        s.style.width  = targetW + 'px';
        s.style.height = targetH + 'px';
      }});
      document.querySelectorAll('.slide-meta,.slide-title-label').forEach(el => {{
        el.style.width = targetW + 'px';
        el.style.maxWidth = targetW + 'px';
      }});
      btn.textContent = fullscreen ? 'Vista normal' : 'Vista ampliada';
      btn.classList.toggle('active', fullscreen);
    }}

    function closeLightbox() {{
      document.getElementById('lightbox').style.display = 'none';
    }}
    document.addEventListener('keydown', e => {{ if (e.key==='Escape') closeLightbox(); }});
  </script>

</body>
</html>
"""


def build_font_faces(cfg: dict, output_path: str) -> str:
    """
    Genera bloques @font-face para cada fuente configurada que exista en fonts/.
    Devuelve el CSS listo para incrustar en <style>.
    """
    seen: set[str] = set()
    blocks: list[str] = []

    # Recopilar todas las fuentes referenciadas en el config
    font_sources: list[str] = []
    for tc in cfg.get("titles", []) + [cfg.get("title", {})]:
        if tc and tc.get("font"):
            font_sources.append(tc["font"])
    for section in ("description", "price", "price_before"):
        font_sources.append(cfg.get(section, {}).get("font", ""))

    for font_file in font_sources:
        if not font_file or font_file in seen:
            continue
        seen.add(font_file)

        # Resolver: primero como ruta relativa al proyecto, luego en fonts/
        font_path = resolve_path(font_file)
        if not font_path.exists():
            font_path = resolve_path(f"fonts/{font_file}")
        if not font_path.exists():
            font_path = resolve_path(f"fonts/{Path(font_file).name}")

        if not font_path.exists():
            print(f"  ⚠  Fuente '{font_file}' no encontrada — el preview usará fuente del sistema.", file=sys.stderr)
            continue

        rel_path  = os.path.relpath(font_path, start=Path(output_path).parent)
        family    = font_family_name(font_file)
        weight    = font_weight_from_name(font_file)
        suffix    = font_path.suffix.lower()
        fmt_map   = {".ttf": "truetype", ".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}
        fmt       = fmt_map.get(suffix, "truetype")

        blocks.append(
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  src: url('{rel_path}') format('{fmt}');\n"
            f"  font-weight: {weight};\n"
            f"  font-style: normal;\n"
            f"  font-synthesis: none;\n"
            f"  font-display: swap;\n"
            f"}}"
        )

    return "\n".join(blocks)


def generate_preview(products: list, cfg: dict, output_path: str) -> None:
    _p_cfg      = cfg["price"]
    _default_dur = _p_cfg["appear_at"] + _p_cfg["fade_duration"] + cfg.get("hold_duration", 2.0) + cfg["fade_out_duration"]
    total_dur    = sum(float(p.get("duracion", _default_dur)) for p in products)

    font_faces  = build_font_faces(cfg, output_path)
    slides_html = "\n".join(
        build_slide(p, cfg, i, len(products), output_path) for i, p in enumerate(products)
    )

    # Tamaño ampliado (para toggle de fullscreen)
    preview_h_large = round(800 / CANVAS_W * CANVAS_H)

    html = HTML_TEMPLATE.format(
        preview_w      = PREVIEW_W,
        preview_h      = PREVIEW_H,
        preview_h_large= preview_h_large,
        n_slides       = len(products),
        total_dur      = total_dur,
        fps            = cfg["fps"],
        scale_pct      = round(SCALE * 100, 1),
        slides_html    = slides_html,
        font_faces     = font_faces,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  ✅  Preview generado: {Path(output_path).resolve()}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un preview HTML de los slides del escaparate"
    )
    parser.add_argument("-d", "--data",   default="data/products.json")
    parser.add_argument("-c", "--config", default="config.json")
    parser.add_argument("-o", "--output", default="output/preview.html")
    args = parser.parse_args()

    cfg  = load_json(args.config)
    data = load_json(args.data)
    products = data if isinstance(data, list) else data.get("productos", [])

    if not products:
        print("  ❌  No hay productos en el archivo de datos.", file=sys.stderr)
        sys.exit(1)

    print(f"  Generando preview de {len(products)} slides...")
    generate_preview(products, cfg, args.output)

    import subprocess
    subprocess.run(["open", args.output])


if __name__ == "__main__":
    main()
