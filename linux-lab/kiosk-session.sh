#!/bin/sh
set -eu

state="${XDG_STATE_HOME:-$HOME/.local/state}/reactoros"
mkdir -p "$state/firefox"
cd /opt/reactoros
export REACTOROS_DATA_DIR="$state"
export REACTOROS_DEBIAN_SESSION=1
python3 -c '
import signal
from local_server import LocalServer

def stop(*_):
    raise SystemExit

signal.signal(signal.SIGTERM, stop)
server = LocalServer()
try:
    signal.pause()
finally:
    server.close()
' &
server=$!
trap 'kill "$server" 2>/dev/null || true; wait "$server" || true' EXIT
openbox &
manager=$!
trap 'kill "$manager" "$server" 2>/dev/null || true; wait "$server" || true' EXIT

for attempt in $(seq 1 30); do
    if python3 -c 'from urllib.request import urlopen; urlopen("http://127.0.0.1:18765/api/operator", timeout=1)'; then
        firefox-esr --no-remote --profile "$state/firefox" --kiosk http://127.0.0.1:18765/kiosk.html
        exit
    fi
    kill -0 "$server" || exit 1
    sleep 1
done
exit 1
