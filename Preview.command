#!/bin/zsh
# Doble clic para generar el preview HTML y abrirlo en el navegador

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  Preview — Escaparate Dual 4K"
echo "════════════════════════════════════"
echo ""

source .venv/bin/activate
python preview.py

echo ""
echo "Pulsa cualquier tecla para cerrar..."
read -n 1
