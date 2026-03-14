#!/bin/zsh
# HIGH VIDEO — Genera el vídeo final en alta calidad

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

# Campanilla y cierre automático
afplay /System/Library/Sounds/Glass.aiff
sleep 1
osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
