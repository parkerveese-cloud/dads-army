#!/bin/sh
# Start a throwaway local server with demo data.
#   devtools/run_local.sh PORT          start (stop with: devtools/stop_local.sh PORT)
# Set DADSARMY_INTEL_OFF=1 before calling to keep it offline (no live feeds).
PORT="${1:?port}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
D="$(mktemp -d /tmp/dadsarmy-dev.XXXXXX)"
echo "$D" > "/tmp/dadsarmy-dev-$PORT.dir"
(
  cd "$HERE/dadsarmy" || exit 1
  SSL_CERT_FILE=/etc/ssl/cert.pem DADSARMY_HOME="51.5074,-0.1278" DADSARMY_DATA="$D" DADSARMY_PORT="$PORT" \
    DADSARMY_HOST=127.0.0.1 nohup python3 server.py > "$D/server.log" 2>&1 &
  echo $! > "/tmp/dadsarmy-dev-$PORT.pid"
)
sleep 2
python3 "$HERE/devtools/seed_demo.py" "http://127.0.0.1:$PORT"
