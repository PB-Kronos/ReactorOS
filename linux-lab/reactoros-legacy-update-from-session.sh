#!/bin/sh
set -eu

test "$(id -u)" -eq 0 || { echo 'Run this helper as root.' >&2; exit 1; }
if [ -x /opt/reactoros/reactoros-update.sh ]; then
    install -m 0755 /opt/reactoros/reactoros-update.sh /usr/local/sbin/reactoros-update
fi
test -x /usr/local/sbin/reactoros-update || {
    echo 'The legacy signed updater is not installed.' >&2
    exit 1
}
exec /usr/local/sbin/reactoros-update
