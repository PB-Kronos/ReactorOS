#!/bin/sh
set -eu

test "$(id -u)" -eq 0 || { echo 'Run with sudo.' >&2; exit 1; }
command -v apt-get >/dev/null 2>&1 || { echo 'APT is required for package updates.' >&2; exit 1; }
exec 9>/run/lock/reactoros-update.lock
flock -n 9 || { echo 'Another ReactorOS update is already running.' >&2; exit 1; }
echo 'Refreshing Debian and ReactorOS package indexes.'
apt-get update
echo 'Installing the latest ReactorOS desktop package.'
DEBIAN_FRONTEND=noninteractive apt-get install -y --only-upgrade reactoros-desktop
echo 'ReactorOS package update completed.'
