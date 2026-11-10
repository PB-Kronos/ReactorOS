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
export REACTOROS_SESSION_ID="${XDG_SESSION_ID:-}"
export REACTOROS_TERMINAL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DCONF_PROFILE=reactoros
export GNOME_SHELL_SESSION_MODE=gnome
reactoros_system_data_dirs="${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export XDG_DATA_DIRS="/opt/reactoros/share:$reactoros_system_data_dirs"
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
' >"$state/local-server.log" 2>&1 &
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
# Build an ephemeral menu overlay for this ReactorOS session only. It hides
# ReactorOS launchers the signed-in user cannot see without touching the
# account's normal GNOME/KDE desktop files or menu settings.
menu_data="$XDG_RUNTIME_DIR/reactoros-menu-data"
menu_apps="$menu_data/applications"
install -d -m 0700 "$menu_apps"
python3 - "$menu_apps" <<'PY'
import sys
from pathlib import Path
from workstation_access import MENU_APPS, current_access

directory = Path(sys.argv[1])
visible = set(current_access().get("visibleApps", []))
for app, (_permission, _label, desktop_id) in MENU_APPS.items():
    override = directory / desktop_id
    if app in visible:
        override.unlink(missing_ok=True)
    else:
        override.write_text("[Desktop Entry]\nType=Application\nHidden=true\nNoDisplay=true\n",
                            encoding="utf-8")
PY
export XDG_DATA_DIRS="$menu_data:/opt/reactoros/share:$reactoros_system_data_dirs"
if [ ! -x /usr/bin/gnome-session ] || [ ! -x /usr/bin/gnome-shell ]; then
    printf '%s\n' 'GNOME session packages are missing; see the signed update result and rerun system migration.' \
        > "$state/session-start-error.log"
    exit 127
fi
if /usr/bin/gnome-session --session=gnome >"$state/gnome-session.log" 2>&1; then
    exit 0
else
    result=$?
    printf 'GNOME session exited with status %s; see %s/gnome-session.log\n' "$result" "$state" \
        > "$state/session-start-error.log"
    exit "$result"
fi
