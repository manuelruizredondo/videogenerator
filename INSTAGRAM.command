#!/bin/zsh
# INSTAGRAM — Genera vídeos independientes 1080×1920 para Reels/Stories

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  Instagram — 1080 × 1920 px"
echo "════════════════════════════════════"
echo ""

if [[ ! -d ".venv" ]]; then
  echo "❌  No se encontró el entorno virtual .venv"
  echo "   Ejecuta primero: python3 -m venv .venv && pip install -r requirements.txt"
  echo ""
  read -n 1 -s -r -p "Pulsa cualquier tecla para cerrar..."
  exit 1
fi

source .venv/bin/activate

python generate_instagram.py
STATUS=$?

echo ""
if [[ $STATUS -eq 0 ]]; then
  afplay /System/Library/Sounds/Glass.aiff
  sleep 1
  osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
else
  echo "❌  Error al generar los vídeos (código $STATUS)."
  echo "   Revisa el mensaje de error anterior."
  echo ""
  read -n 1 -s -r -p "Pulsa cualquier tecla para cerrar..."
  echo ""
fi
