#!/bin/sh
# Headless screenshot, so you can look at your work.
#   devtools/shot.sh URL OUT.png [WIDTH] [HEIGHT] [dark|light]
# Example: devtools/shot.sh "http://127.0.0.1:18101/#sitrep" /tmp/da-sitrep.png 1280 1800 dark   (then Read the PNG)
# Phone width: 390 844. Tall heights capture the whole page.
URL="${1:?url}"; OUT="${2:?out.png}"; W="${3:-1280}"; H="${4:-1400}"; MODE="${5:-dark}"
FLAG=""
[ "$MODE" = "dark" ] && FLAG="--force-dark-mode --blink-settings=preferredColorScheme=0"
# shellcheck disable=SC2086
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars $FLAG \
  --window-size="$W,$H" --virtual-time-budget=7000 --screenshot="$OUT" "$URL" 2>/dev/null
ls -la "$OUT"
