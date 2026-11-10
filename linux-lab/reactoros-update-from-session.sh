#!/bin/sh
set -eu

test "$(id -u)" -eq 0 || { echo 'Run this helper through sudo systemd-run.' >&2; exit 1; }
session_id=${1:-}
case "$session_id" in
    ''|*[!0-9]*) echo 'Invalid logind session id.' >&2; exit 2 ;;
esac

exec 9>/run/lock/reactoros-update-launch.lock
flock -n 9 || { echo 'Another update is already running.' >&2; exit 1; }
exec >/run/reactoros-update-result 2>&1
echo "Update requested for login session $session_id."
if ! loginctl show-session "$session_id" --property=Id --value >/dev/null 2>&1; then
    echo "Login session $session_id no longer exists; continuing if the kiosk is stopped."
else
    echo "Logging out session $session_id through systemd-logind."
    loginctl terminate-session "$session_id"
fi

stopped=0
for attempt in $(seq 1 30); do
    if ! pgrep -f '^/bin/sh /opt/reactoros/kiosk-session.sh([[:space:]]|$)' >/dev/null; then
        stopped=1
        break
    fi
    sleep 1
done
if [ "$stopped" -ne 1 ]; then
    echo 'ReactorOS session did not stop within 30 seconds; update was not started.'
    exit 1
fi

if [ -x /opt/reactoros/reactoros-update.sh ]; then
    install -m 0755 /opt/reactoros/reactoros-update.sh /usr/local/sbin/reactoros-update
fi
if [ -x /opt/reactoros/system-migrate.sh ]; then
    /opt/reactoros/system-migrate.sh
fi
exec /usr/local/sbin/reactoros-update
