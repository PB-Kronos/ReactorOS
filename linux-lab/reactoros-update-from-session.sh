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

session_user=$(loginctl show-session "$session_id" --property=Name --value 2>/dev/null || true)
if [ -z "$session_user" ] || ! getent passwd "$session_user" >/dev/null 2>&1; then
    echo "Could not resolve the requesting account for session $session_id; automatic return login will be skipped."
    session_user=''
fi

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

update_status=0
case "$method" in
    package) /usr/lib/reactoros/package-update || update_status=$? ;;
    legacy) /usr/lib/reactoros/legacy-update || update_status=$? ;;
esac

other_graphical_session=0
for candidate in $(loginctl list-sessions --no-legend --no-pager 2>/dev/null | awk '{print $1}'); do
    [ "$candidate" = "$session_id" ] && continue
    candidate_class=$(loginctl show-session "$candidate" --property=Class --value 2>/dev/null || true)
    candidate_seat=$(loginctl show-session "$candidate" --property=Seat --value 2>/dev/null || true)
    candidate_active=$(loginctl show-session "$candidate" --property=Active --value 2>/dev/null || true)
    candidate_type=$(loginctl show-session "$candidate" --property=Type --value 2>/dev/null || true)
    if [ "$candidate_class" = user ] && [ -n "$candidate_seat" ] && \
            [ "$candidate_active" = yes ] && \
            { [ "$candidate_type" = x11 ] || [ "$candidate_type" = wayland ]; }; then
        other_graphical_session=1
        break
    fi
done

if [ "$other_graphical_session" -eq 1 ]; then
    echo 'Another graphical user session is active; leaving it untouched. Automatic return login is skipped.'
elif [ -n "$session_user" ] && [ -x /usr/lib/reactoros/clear-update-autologin ] && \
        [ -f /usr/lib/reactoros/update-autologin.py ]; then
    echo "Preparing one-time automatic return login for $session_user."
    if /usr/bin/python3 /usr/lib/reactoros/update-autologin.py prepare "$session_user"; then
        systemctl enable --now reactoros-update-autologin-cleanup.timer || \
            echo 'Could not arm automatic return-login cleanup; the account login hook remains available.'
        if systemctl restart display-manager.service; then
            echo "Display manager restarted for the one-time return login to $session_user."
        else
            echo 'Could not restart the display manager; return to the sign-in screen and log in manually.'
        fi
    else
        echo 'Automatic return login could not be configured; return to the sign-in screen and log in manually.'
    fi
fi

exit "$update_status"
