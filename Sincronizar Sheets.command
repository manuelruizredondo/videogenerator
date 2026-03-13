#!/bin/zsh
# Sincronizar Sheets.command
# Descarga la configuración desde Google Sheets y actualiza config.json + products.json

cd "$(dirname "$0")"

echo ""
echo "══════════════════════════════════════════════════"
echo "   VideoGenerator — Sincronizar desde Google Sheets"
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
  echo "✔  Sincronización completada. Ya puedes generar el vídeo."
else
  echo "✖  La sincronización ha fallado (código $STATUS)."
  echo "   Revisa el mensaje de error anterior."
fi

echo ""
read -n 1 -s -r -p "Pulsa cualquier tecla para cerrar..."
echo ""
