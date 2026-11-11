#!/bin/sh
set -eu

test "$(id -u)" -eq 0 || { echo 'Run this helper through sudo systemd-run.' >&2; exit 1; }
session_id=${1:-}
method=${2:-auto}
case "$session_id" in
    ''|*[!0-9]*) echo 'Invalid logind session id.' >&2; exit 2 ;;
esac
case "$method" in
    auto|package|legacy) ;;
    *) echo 'Update method must be auto, package, or legacy.' >&2; exit 2 ;;
esac

exec 9>/run/lock/reactoros-update-launch.lock
flock -n 9 || { echo 'Another ReactorOS update is already starting.' >&2; exit 1; }
exec >/run/reactoros-update-result 2>&1
echo "ReactorOS $method update requested for login session $session_id."
if loginctl show-session "$session_id" --property=Id --value >/dev/null 2>&1; then
    echo "Signing out ReactorOS session $session_id through systemd-logind."
    loginctl terminate-session "$session_id"
fi

stopped=0
for attempt in $(seq 1 45); do
    if ! pgrep -f '^/bin/sh /opt/reactoros/kiosk-session.sh([[:space:]]|$)' >/dev/null; then
        stopped=1
        break
    fi
    sleep 1
done
if [ "$stopped" -ne 1 ]; then
    echo 'ReactorOS did not finish signing out; the update was not started.'
    exit 1
fi

if [ "$method" = auto ]; then
    if [ -s /etc/apt/sources.list.d/reactoros.sources ] && \
            [ -s /usr/share/keyrings/reactoros-archive-keyring.gpg ] && \
            dpkg-query -W -f='${db:Status-Status}' reactoros-desktop 2>/dev/null | grep -qx installed; then
        method=package
    else
        method=legacy
    fi
fi

case "$method" in
    package) exec /usr/lib/reactoros/package-update ;;
    legacy) exec /usr/lib/reactoros/legacy-update ;;
esac
