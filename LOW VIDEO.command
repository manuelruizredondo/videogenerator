#!/bin/zsh
# LOW VIDEO — Previsualización rápida en baja resolución

cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo "  Quick Preview — Vídeo Escaparate"
echo "════════════════════════════════════"
echo ""

source .venv/bin/activate
python quick_preview_video.py

afplay /System/Library/Sounds/Glass.aiff
sleep 1
osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
