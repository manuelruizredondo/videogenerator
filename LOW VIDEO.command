#!/bin/zsh
# LOW VIDEO — Previsualización rápida en baja resolución

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  VideoGenerator — Baja Resolución"
echo "════════════════════════════════════"
echo ""

# Comprobar entorno virtual
if [[ ! -d ".venv" ]]; then
  echo "❌  No se encontró el entorno virtual .venv"
  echo "   Ejecuta primero: python3 -m venv .venv && pip install -r requirements.txt"
  echo ""
  read -n 1 -s -r -p "Pulsa cualquier tecla para cerrar..."
  exit 1
fi

source .venv/bin/activate

.venv/bin/python3 quick_preview_video.py
STATUS=$?

echo ""
if [[ $STATUS -eq 0 ]]; then
  afplay /System/Library/Sounds/Glass.aiff
  sleep 1
  osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
else
  echo "❌  Error al generar el vídeo (código $STATUS)."
  echo "   Revisa el mensaje de error anterior."
  echo ""
  read -n 1 -s -r -p "Pulsa cualquier tecla para cerrar..."
  echo ""
fi
