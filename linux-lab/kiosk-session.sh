#!/bin/sh
set -eu

state="${XDG_STATE_HOME:-$HOME/.local/state}/reactoros"
mkdir -p "$state/firefox"
if ! grep -Fqx 'user_pref("media.autoplay.default", 0);' "$state/firefox/user.js" 2>/dev/null; then
    printf '\nuser_pref("media.autoplay.default", 0);\n' >> "$state/firefox/user.js"
fi
cd /opt/reactoros
export REACTOROS_DATA_DIR="$state"
export REACTOROS_DEBIAN_SESSION=1
export REACTOROS_KIOSK_PID=$$
export REACTOROS_TERMINAL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DCONF_PROFILE=reactoros
export GNOME_SHELL_SESSION_MODE=gnome
export XDG_DATA_DIRS="/opt/reactoros/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="unix:$XDG_RUNTIME_DIR/pulse/native"
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && [ -S "$XDG_RUNTIME_DIR/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
fi

systemctl --user enable --now pipewire.socket pipewire-pulse.socket wireplumber.service \
    >/dev/null 2>&1 || printf '%s\n' 'ReactorOS: PipeWire user audio services did not start.' >&2
systemctl --user start pipewire.service pipewire-pulse.service >/dev/null 2>&1 || true

python3 -c '
import signal
from local_server import LocalServer
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit()))
server = LocalServer()
try:
    signal.pause()
finally:
    server.close()
' &
server=$!
session_manager=''
cleanup() {
    kill "$server" ${session_manager:+"$session_manager"} 2>/dev/null || true
    wait "$server" 2>/dev/null || true
    [ -z "$session_manager" ] || wait "$session_manager" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' USR1

ready=0
for attempt in $(seq 1 30); do
    if python3 -c 'from urllib.request import urlopen; urlopen("http://127.0.0.1:18765/api/operator", timeout=1)'; then
        ready=1
        break
    fi
    kill -0 "$server" || exit 1
    sleep 1
done
test "$ready" -eq 1
/usr/bin/gnome-session --session=gnome &
session_manager=$!
wait "$session_manager"
