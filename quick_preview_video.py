#!/usr/bin/env python3
"""
quick_preview_video.py — Genera un vídeo de previsualización rápida a baja resolución.

Renderiza a 1/4 de la resolución original (960×1080 px) con encoder ultrafast.
Útil para comprobar animaciones, textos y tiempos antes de generar el vídeo final.

Uso:
    python quick_preview_video.py
    python quick_preview_video.py -d data/products.json -o output/preview_video.mp4
"""

import argparse
import copy
import sys

# ── Importar el motor de generación ──────────────────────────────────────────
import generate_video as gv

# ── Factor de escala ──────────────────────────────────────────────────────────
SCALE = 0.25   # 1/4 de la resolución original → 16× más rápido de renderizar


def scale_config(cfg: dict) -> dict:
    """Devuelve una copia del config adaptada a la resolución de preview."""
    c = copy.deepcopy(cfg)

    def sc(v: float) -> int:
        return round(v * SCALE)

    # Geometría global
    c["safe_margin"]     = sc(cfg["safe_margin"])
    c["split_safe_zone"] = sc(cfg["split_safe_zone"])

    # Títulos: font_size + margin_top
    for tc in c.get("titles", []):
        tc["font_size"] = sc(tc["font_size"])
        if "margin_top" in tc:
            tc["margin_top"] = sc(tc["margin_top"])

    # Descripción y precio principal
    for section in ("description", "price"):
        c[section]["font_size"] = sc(cfg[section]["font_size"])

    # Precio anterior (tachado)
    if "price_before" in c:
        c["price_before"]["font_size"] = sc(cfg["price_before"]["font_size"])
        if "gap" in c["price_before"]:
            c["price_before"]["gap"] = sc(cfg["price_before"]["gap"])

    # Logos (header y footer)
    for key in ("logo", "logo_footer"):
        if key in c:
            c[key]["width"]       = sc(cfg[key].get("width",       400))
            c[key]["margin_top"]  = sc(cfg[key].get("margin_top",  150))
            c[key]["margin_side"] = sc(cfg[key].get("margin_side", 150))

    # Encoder rápido — calidad no importa para preview
    c["encoder_preset"] = "ultrafast"
    c["encoder_crf"]    = 28

    return c


def patch_canvas() -> None:
    """Ajusta las constantes de canvas del módulo generate_video."""
    gv.CANVAS_W = round(3840 * SCALE)   # 960
    gv.CANVAS_H = round(4320 * SCALE)   # 1080
    gv.TV_SPLIT = round(2160 * SCALE)   # 540


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Previsualización rápida del vídeo de escaparate (baja resolución)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-d", "--data",   default="data/products.json")
    parser.add_argument("-c", "--config", default="config.json")
    parser.add_argument("-o", "--output", default="output/preview_video.mp4")
    args = parser.parse_args()

    # Verificar FFmpeg
    import subprocess, os
    from pathlib import Path
    import shutil

    _EXTRA = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    ffmpeg = shutil.which("ffmpeg") or next(
        (str(Path(d) / "ffmpeg") for d in _EXTRA if (Path(d) / "ffmpeg").exists()), None
    )
    if not ffmpeg:
        print("  ❌  FFmpeg no encontrado. Instálalo con: brew install ffmpeg", file=sys.stderr)
        sys.exit(1)
    os.environ["PATH"] = os.pathsep.join(_EXTRA) + os.pathsep + os.environ.get("PATH", "")

    print("═" * 60)
    print("  Quick Preview — Escaparate (baja resolución)")
    print("═" * 60)

    # Parchear canvas ANTES de que se use en ninguna función
    patch_canvas()

    cfg      = gv.load_config(args.config)
    products = gv.load_products(args.data)

    if not products:
        print("  ❌  No hay productos en el archivo de datos.", file=sys.stderr)
        sys.exit(1)

    cfg_preview = scale_config(cfg)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    w, h = gv.CANVAS_W, gv.CANVAS_H
    print(f"  Resolución  : {w}×{h} px  (escala {int(SCALE*100)}% del original)")
    print(f"  Slides      : {len(products)}")
    print()

    gv.generate_video(products, cfg_preview, args.output)

    # Abrir automáticamente el vídeo generado
    subprocess.run(["open", args.output])


if __name__ == "__main__":
    main()
