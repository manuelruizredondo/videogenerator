#!/bin/zsh
# HIGH VIDEO — Genera el vídeo final en alta calidad

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  VideoGenerator — Alta Calidad"
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

python generate_video.py
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
