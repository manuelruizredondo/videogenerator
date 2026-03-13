#!/bin/zsh
# Doble clic para generar el vídeo del escaparate

# Ir a la carpeta del proyecto (donde está este archivo)
cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  VideoGenerator — Clínica"
echo "════════════════════════════════════"
echo ""

# Activar entorno virtual
source .venv/bin/activate

# Generar vídeo
python generate_video.py

echo ""
echo "Pulsa cualquier tecla para cerrar..."
read -n 1
