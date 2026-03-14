#!/bin/zsh
# Doble clic para generar el preview HTML y abrirlo en el navegador

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  Preview — Escaparate Dual 4K"
echo "════════════════════════════════════"
echo ""

source .venv/bin/activate
python preview.py

afplay /System/Library/Sounds/Glass.aiff
sleep 1
osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
