#!/usr/bin/env bash
# Dads Army installer for Raspberry Pi OS (or any Debian-style Linux with systemd).
#
#   bash install.sh
#
# Run it as your normal user from the folder you copied onto the Pi.
# It installs to ~/dadsarmy and starts automatically on boot.
# Run it again any time to update: your data is kept.
#
# Options (set before the command):
#   DADSARMY_PORT=8081 bash install.sh    use a different port (default 8080)
#   DADSARMY_DIR=/srv/dadsarmy bash install.sh   install somewhere else
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${DADSARMY_DIR:-$HOME/dadsarmy}"
PORT="${DADSARMY_PORT:-8080}"
SERVICE=dadsarmy
RUN_AS="$(id -un)"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "Run this as your normal user, not with sudo. It asks for your password when it needs it."
# The app lives in dadsarmy/ in the repository, or next to this script in an installed copy.
APP="$SRC/dadsarmy"
[ -f "$APP/server.py" ] || APP="$SRC"
[ -f "$APP/server.py" ] && [ -d "$APP/static" ] || die "Run this from the Dads Army folder (dadsarmy/server.py should be next to install.sh)."
case "$DEST" in *" "*) die "The install folder can't contain spaces: $DEST" ;; esac
command -v python3 >/dev/null 2>&1 || die "python3 isn't installed. Install it with: sudo apt install -y python3"
python3 -c 'import sys, sqlite3; sys.exit(0 if sys.version_info >= (3, 7) else 1)' \
  || die "Dads Army needs Python 3.7 or newer. Update with: sudo apt update && sudo apt install -y python3"
command -v systemctl >/dev/null 2>&1 || die "systemd wasn't found. You can still run it by hand: python3 server.py"
PYTHON="$(command -v python3)"

say "Installing Dads Army to $DEST"
mkdir -p "$DEST/data/backups"
if [ "$SRC" != "$DEST" ]; then
  rm -rf "$DEST/static" "$DEST/places"
  cp -R "$APP/static" "$DEST/static"
  if [ -d "$APP/places" ]; then cp -R "$APP/places" "$DEST/places"; fi
  cp "$APP/server.py" "$DEST/server.py"
  for f in install.sh README.md; do
    if [ -f "$SRC/$f" ]; then cp "$SRC/$f" "$DEST/$f"; fi
  done
fi
# In case the files picked up Windows line endings on the way over.
sed -i 's/\r$//' "$DEST/server.py" "$DEST/install.sh" 2>/dev/null || true

say "Setting up the '$SERVICE' service so it starts on boot (sudo needed)"
sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<EOF
[Unit]
Description=Dads Army - home front stores tracker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_AS
WorkingDirectory=$DEST
Environment=DADSARMY_PORT=$PORT
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON $DEST/server.py
Restart=always
RestartSec=5
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null 2>&1
sudo systemctl restart "$SERVICE"

say "Checking it's running"
ok=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if "$PYTHON" -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$PORT/api/health', timeout=2)" 2>/dev/null; then
    ok=1; break
  fi
  sleep 1
done
if [ -z "$ok" ]; then
  echo
  sudo journalctl -u "$SERVICE" -n 20 --no-pager || true
  die "It didn't start. If the port is taken, try: DADSARMY_PORT=8081 bash install.sh"
fi

echo
say "Dads Army is up and running."
echo
echo "  On your phone (connected to the home Wi-Fi), open:"
echo "     http://$(hostname).local:$PORT"
MAIN_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v ':' | grep -v '^$' | head -n 1 || true)"
if [ -n "$MAIN_IP" ]; then echo "  or http://$MAIN_IP:$PORT"; fi
echo
echo "  Then use 'Add to Home Screen' to give it an app icon."
echo
echo "  Your data:     $DEST/data/dadsarmy.db"
echo "  Daily backups: $DEST/data/backups"
echo "  Live log:      sudo journalctl -u $SERVICE -f"
echo "  Restart:       sudo systemctl restart $SERVICE"
