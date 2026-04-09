#!/bin/zsh
# Subir a Sheets.command
# Sube los productos de products.json local → Google Sheets

cd "$(dirname "$0")"

echo ""
echo "══════════════════════════════════════════════════"
echo "   VideoGenerator — Subir productos a Google Sheets"
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

.venv/bin/python3 sync_from_sheets.py --push
STATUS=$?

echo ""
if [[ $STATUS -eq 0 ]]; then
  echo "✔  Productos subidos correctamente a Google Sheets."
else
  echo "✖  La subida ha fallado (código $STATUS)."
  echo "   Revisa el mensaje de error anterior."
fi

afplay /System/Library/Sounds/Glass.aiff
sleep 3
osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
