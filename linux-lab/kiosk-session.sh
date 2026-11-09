#!/bin/sh
set -eu

state="${XDG_STATE_HOME:-$HOME/.local/state}/reactoros"
mkdir -p "$state/firefox"
# This profile only hosts the local workstation, whose alarms must be able to
# play even when a scenario is triggered from a different app window.
if ! grep -Fqx 'user_pref("media.autoplay.default", 0);' "$state/firefox/user.js" 2>/dev/null; then
    printf '\nuser_pref("media.autoplay.default", 0);\n' >> "$state/firefox/user.js"
fi
cd /opt/reactoros
export REACTOROS_DATA_DIR="$state"
export REACTOROS_DEBIAN_SESSION=1
export REACTOROS_KIOSK_PID=$$
# Bind audio clients to the session's PipeWire Pulse endpoint explicitly.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="unix:$XDG_RUNTIME_DIR/pulse/native"
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && [ -S "$XDG_RUNTIME_DIR/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
fi
systemctl --user enable --now pipewire.socket pipewire-pulse.socket wireplumber.service \
    >/dev/null 2>&1 || printf '%s\n' 'ReactorOS: PipeWire user audio services did not start.' >&2
systemctl --user start pipewire.service pipewire-pulse.service >/dev/null 2>&1 || true
if command -v pactl >/dev/null 2>&1; then
    for attempt in $(seq 1 12); do
        pactl info >/dev/null 2>&1 && break
        sleep 0.25
    done
fi
session=$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/reactoros-kiosk.XXXXXXXX")
trap 'rm -f "$session/start.html" "$session/openbox.xml" "$session/fullscreen-key" "$session/start-menu-key"; rmdir "$session"' EXIT
export REACTOROS_FULLSCREEN_KEY="$session/fullscreen-key"
export REACTOROS_START_MENU_KEY="$session/start-menu-key"
REACTOROS_TERMINAL_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
export REACTOROS_TERMINAL_TOKEN
printf '<script>location.replace("http://127.0.0.1:18765/kiosk.html#%s")</script>\n' \
    "$REACTOROS_TERMINAL_TOKEN" > "$session/start.html"
python3 - "$session/openbox.xml" "$REACTOROS_FULLSCREEN_KEY" "$REACTOROS_START_MENU_KEY" <<'PY'
import sys
import shlex
import xml.etree.ElementTree as ET

ns = "http://openbox.org/3.4/rc"
ET.register_namespace("", ns)
def tag(name):
    return f"{{{ns}}}{name}"

config = ET.parse("/etc/xdg/openbox/rc.xml")
keyboard = config.getroot().find(tag("keyboard"))
for binding in list(keyboard.findall(tag("keybind"))):
    if binding.get("key") not in ("A-Tab", "A-S-Tab"):
        keyboard.remove(binding)
for key in ("C-w", "C-S-w", "C-q", "C-n", "C-S-p", "C-t", "C-l", "C-o",
            "C-u", "C-s", "C-p", "C-j", "C-h", "C-b", "C-S-a", "C-S-o",
            "C-S-h", "C-S-i", "C-S-j", "C-S-k", "C-S-c",
            "F6", "F12",
            "A-F2", "A-F4", "A-d", "A-Left", "A-Right"):
    binding = ET.SubElement(keyboard, tag("keybind"), key=key)
    action = ET.SubElement(binding, tag("action"), name="Execute")
    ET.SubElement(action, tag("command")).text = "/bin/true"
binding = ET.SubElement(keyboard, tag("keybind"), key="F11")
action = ET.SubElement(binding, tag("action"), name="Execute")
ET.SubElement(action, tag("command")).text = "/usr/bin/touch " + shlex.quote(sys.argv[2])
binding = ET.SubElement(keyboard, tag("keybind"), key="W")
action = ET.SubElement(binding, tag("action"), name="Execute")
ET.SubElement(action, tag("command")).text = "/usr/bin/touch " + shlex.quote(sys.argv[3])
for context in config.findall(f".//{tag('context')}"):
    if context.get("name") in ("Root", "Desktop"):
        for binding in list(context):
            if any(action.get("name") == "ShowMenu" for action in binding):
                context.remove(binding)
config.write(sys.argv[1], encoding="utf-8", xml_declaration=True)
PY
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
cleanup() {
    kill "$server" ${manager:+"$manager"} ${polkit:+"$polkit"} ${browser:+"$browser"} 2>/dev/null || true
    if [ -n "${browser:-}" ]; then wait "$browser" || true; fi
    wait "$server" || true
    rm -f "$session/start.html" "$session/openbox.xml" "$session/fullscreen-key" "$session/start-menu-key"
    rmdir "$session"
}
trap cleanup EXIT
trap 'exit 0' USR1
xrandr --auto >/dev/null 2>&1 || true
openbox --config-file "$session/openbox.xml" &
manager=$!
lxpolkit >/dev/null 2>&1 &
polkit=$!

for attempt in $(seq 1 30); do
    if python3 -c 'from urllib.request import urlopen; urlopen("http://127.0.0.1:18765/api/operator", timeout=1)'; then
        firefox-esr --no-remote --profile "$state/firefox" --kiosk "file://$session/start.html" &
        browser=$!
        wait "$browser"
        exit
    fi
    kill -0 "$server" || exit 1
    sleep 1
done
exit 1
