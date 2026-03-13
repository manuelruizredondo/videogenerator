#!/bin/zsh
# Doble clic para generar una previsualización rápida del vídeo (baja resolución)

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  Quick Preview — Vídeo Escaparate"
echo "════════════════════════════════════"
echo ""

source .venv/bin/activate
python quick_preview_video.py

echo ""
echo "Pulsa cualquier tecla para cerrar..."
read -n 1
