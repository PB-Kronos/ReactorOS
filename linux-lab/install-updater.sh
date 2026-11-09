#!/bin/sh
set -eu

repo=${1:-}
repo=${repo#https://github.com/}
repo=${repo%/}
repo=${repo%.git}
if [ "$#" -ne 1 ] || ! printf '%s\n' "$repo" | grep -Eq '^[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$'; then
    echo 'Usage: sudo sh install-updater.sh https://github.com/OWNER/REPO' >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo 'Run this installer with sudo.' >&2
    exit 1
fi
media=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if ! openssl pkey -pubin -in "$media/update-public.pem" -noout; then
    echo 'The setup disc needs a valid release signing public key.' >&2
    exit 1
fi
command -v curl >/dev/null || { echo 'Install curl with sudo apt-get install curl ca-certificates.' >&2; exit 1; }
test -f /opt/reactoros/kiosk-session.sh || { echo 'Install the ReactorOS kiosk first.' >&2; exit 1; }

# Older kiosk installs may lack the native terminal or the audio service.
if ! command -v xterm >/dev/null || ! command -v wireplumber >/dev/null || ! command -v pipewire-pulse >/dev/null || ! python3 -c 'import tkinter' 2>/dev/null; then
    apt-get update
    apt-get install -y --no-install-recommends xterm pipewire-audio wireplumber python3-tk
fi

install -d -m 0755 /etc/reactoros
install -m 0644 "$media/update-public.pem" /etc/reactoros/update-public.pem
install -m 0755 "$media/reactoros-update.sh" /usr/local/sbin/reactoros-update
printf '%s\n' "$repo" > /etc/reactoros/update-repo
echo "Updater configured for $repo. To apply a signed release, sign out of the kiosk and run sudo /usr/local/sbin/reactoros-update."
