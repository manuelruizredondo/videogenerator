#!/bin/zsh
# Bajar de Sheets.command
# Descarga la configuración desde Google Sheets y actualiza config.json + products.json

cd "$(dirname "$0")"

echo ""
echo "══════════════════════════════════════════════════"
echo "   VideoGenerator — Bajar desde Google Sheets"
echo "══════════════════════════════════════════════════"
echo ""

# Activar entorno virtual
if [[ ! -d ".venv" ]]; then
  echo "❌  No se encontró el entorno virtual .venv"
  echo "   Ejecuta primero: python3 -m venv .venv && pip install -r requirements.txt"
  echo ""
  read -n 1 -s -r -p "Pulsa cualquier tecla para cerrar..."
  exit 1
fi

source .venv/bin/activate

python sync_from_sheets.py
STATUS=$?

echo ""
if [[ $STATUS -eq 0 ]]; then
  echo "✔  Descarga completada. Ya puedes generar el vídeo."
else
  echo "✖  La descarga ha fallado (código $STATUS)."
  echo "   Revisa el mensaje de error anterior."
fi

afplay /System/Library/Sounds/Glass.aiff
sleep 3
osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
