#!/bin/bash
# hud_update.sh <agent> <status> "<task>" <progress>
# Example: ./hud_update.sh neo working "Improving layout" 50
HUD_URL="${HUD_URL:-https://matrix-hud.onrender.com}"
curl -s -X POST "$HUD_URL/update" \
  -H 'Content-Type: application/json' \
  -d "{\"agent\":\"$1\",\"status\":\"$2\",\"task\":\"$3\",\"progress\":$4}" > /dev/null
echo "✅ HUD: $1 → $2 ($3)"
