#!/usr/bin/env python3
"""
generate_instagram.py — Genera vídeos independientes para Instagram (Reels/Stories).

Resolución : 1080 × 1920 px  (9:16 portrait)
Un MP4 por slide, guardados en output/instagram/
Los tamaños de texto y márgenes se escalan proporcionalmente desde el original.

Uso:
    python generate_instagram.py
    python generate_instagram.py -d data/products.json -o output/instagram
"""

import argparse
import copy
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import generate_video as gv

# ── Dimensiones Instagram ─────────────────────────────────────────────────────
IG_W    = 1080
IG_H    = 1920
# Factor de escala base respecto al canvas original (3840 px de ancho)
SCALE_W = IG_W / 3840   # ≈ 0.28125

# ── Multiplicadores de escala por elemento ────────────────────────────────────
# Ajusta estos valores para subir/bajar tamaños relativos en Instagram.
# 1.0 = escala pura proporcional · >1.0 = más grande que proporcional
LOGO_SCALE        = 1.6   # logos header y footer
TITULO3_SCALE     = 1.55  # titulo_3 (suele ser el más pequeño del config)

# ─────────────────────────────────────────────────────────────────────────────


def scale_config(cfg: dict) -> dict:
    """Devuelve una copia del config escalada para 1080×1920."""
    c = copy.deepcopy(cfg)

    def sc(v) -> int:
        return max(1, round(v * SCALE_W))

    # Geometría global
    c["safe_margin"]     = sc(cfg["safe_margin"])
    c["split_safe_zone"] = sc(cfg["split_safe_zone"])

    # Títulos — titulo_3 usa un factor mayor para que no quede demasiado pequeño
    for tc in c.get("titles", []):
        t_scale = TITULO3_SCALE if tc.get("field") == "titulo_3" else 1.0
        def sct(v, mult=t_scale): return max(1, round(v * SCALE_W * mult))
        tc["font_size"] = sct(tc["font_size"])
        if "margin_top" in tc:
            tc["margin_top"] = sc(tc["margin_top"])
        if "letter_spacing" in tc:
            tc["letter_spacing"] = sct(tc["letter_spacing"])
        if "line_height" in tc:
            tc["line_height"] = sc(tc["line_height"])

    # Descripción y precio
    for section in ("description", "price"):
        if section in c:
            c[section]["font_size"] = sc(cfg[section]["font_size"])
            if "letter_spacing" in cfg[section]:
                c[section]["letter_spacing"] = sc(cfg[section]["letter_spacing"])
            if "margin_top" in cfg[section]:
                c[section]["margin_top"] = sc(cfg[section]["margin_top"])

    # Precio tachado
    if "price_before" in c:
        c["price_before"]["font_size"] = sc(cfg["price_before"]["font_size"])
        if "gap" in cfg["price_before"]:
            c["price_before"]["gap"] = sc(cfg["price_before"]["gap"])
        if "letter_spacing" in cfg.get("price_before", {}):
            c["price_before"]["letter_spacing"] = sc(cfg["price_before"]["letter_spacing"])

    # Logos — se escalan con LOGO_SCALE para que sean visibles en portrait
    def scl(v): return max(1, round(v * SCALE_W * LOGO_SCALE))
    for key in ("logo", "logo_footer"):
        if key in c:
            c[key]["width"]       = scl(cfg[key].get("width",       400))
            c[key]["margin_top"]  = sc(cfg[key].get("margin_top",   150))
            c[key]["margin_side"] = sc(cfg[key].get("margin_side",  150))

    # Badge del precio
    for section in ("price", "price_before"):
        if section in c and "badge" in c[section]:
            b = c[section]["badge"]
            for k in ("padding", "padding_x", "padding_y", "border_radius"):
                if k in b:
                    b[k] = sc(b[k])

    # Encoder: calidad buena pero más rápido que el original
    c["encoder_preset"] = "fast"
    c["encoder_crf"]    = 20

    # Instagram: fondo visible desde el frame 1 y sin fade-out al final,
    # para que el vídeo funcione bien en bucle (Reels/Stories).
    c["bg_appear_at"]       = 0.0   # sin intro oscura
    c["bg_fade_in_duration"] = 0.0  # fondo a plena opacidad desde frame 0
    c["fade_out_duration"]  = 0.0   # sin fade-out al final

    return c


def patch_canvas() -> None:
    """Ajusta las constantes de canvas de generate_video para Instagram."""
    gv.CANVAS_W = IG_W
    gv.CANVAS_H = IG_H
    gv.TV_SPLIT = IG_H // 2   # 960 → punto medio del frame portrait


def slugify(name: str) -> str:
    """Convierte un nombre de producto en un slug válido para nombre de archivo."""
    name = name.strip().lower()
    name = re.sub(r'[àáâãäå]', 'a', name)
    name = re.sub(r'[èéêë]',   'e', name)
    name = re.sub(r'[ìíîï]',   'i', name)
    name = re.sub(r'[òóôõö]',  'o', name)
    name = re.sub(r'[ùúûü]',   'u', name)
    name = re.sub(r'[ñ]',      'n', name)
    name = re.sub(r'[ç]',      'c', name)
    name = re.sub(r'[^\w\s-]', '',  name)
    name = re.sub(r'[\s_]+',   '_', name)
    return name[:40].strip('_')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera vídeos Instagram 1080×1920 — un archivo MP4 por slide",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", "--data",   default="data/products.json")
    parser.add_argument("-c", "--config", default="config.json")
    parser.add_argument("-o", "--outdir", default="output/instagram")
    args = parser.parse_args()

    # Verificar FFmpeg
    _EXTRA = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    ffmpeg = shutil.which("ffmpeg") or next(
        (str(Path(d) / "ffmpeg") for d in _EXTRA if (Path(d) / "ffmpeg").exists()), None
    )
    if not ffmpeg:
        print("  ❌  FFmpeg no encontrado. Instálalo con: brew install ffmpeg", file=sys.stderr)
        sys.exit(1)
    os.environ["PATH"] = os.pathsep.join(_EXTRA) + os.pathsep + os.environ.get("PATH", "")

    print("═" * 60)
    print("  Instagram Videos — 1080 × 1920 px  (Reels / Stories)")
    print("═" * 60)

    # Parchear el canvas ANTES de cualquier cálculo
    patch_canvas()

    cfg      = gv.load_config(args.config)
    products = gv.load_products(args.data)

    if not products:
        print("  ❌  Sin productos en el archivo de datos.", file=sys.stderr)
        sys.exit(1)

    cfg_ig = scale_config(cfg)
    outdir  = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"  Resolución  : {IG_W} × {IG_H} px")
    print(f"  Slides      : {len(products)}")
    print(f"  Destino     : {outdir.resolve()}")
    print()

    errors = 0
    for i, product in enumerate(products, 1):
        name  = product.get("producto", f"slide_{i}")
        slug  = slugify(name)
        fname = f"{i:02d}_{slug}.mp4"
        out   = str(outdir / fname)

        print(f"  [{i}/{len(products)}] {name}")
        print(f"          → {fname}")

        try:
            gv.generate_video([product], cfg_ig, out)
        except Exception as e:
            print(f"  ⚠  Error en '{name}': {e}", file=sys.stderr)
            errors += 1

        print()

    print("─" * 60)
    if errors:
        print(f"  ⚠  Completado con {errors} error(es).")
    else:
        print(f"  ✅  {len(products)} vídeos generados en:")
        print(f"      {outdir.resolve()}")

    subprocess.run(["open", str(outdir)])


if __name__ == "__main__":
    main()
