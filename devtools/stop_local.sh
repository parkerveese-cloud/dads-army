#!/bin/sh
# Stop a server started by run_local.sh and remove its throwaway data folder.
PORT="${1:?port}"
PIDFILE="/tmp/dadsarmy-dev-$PORT.pid"
DIRFILE="/tmp/dadsarmy-dev-$PORT.dir"
[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
if [ -f "$DIRFILE" ]; then
  D="$(cat "$DIRFILE")"
  case "$D" in
    /tmp/dadsarmy-dev.??????) [ -d "$D" ] && rm -r "$D" ;;   # only ever our own mktemp folder
  esac
fi
rm -f "$PIDFILE" "$DIRFILE"
echo stopped
