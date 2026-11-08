#!/bin/sh
set -eu
test "$(id -u)" -eq 0
test -f /opt/reactoros/kiosk-session.sh
media=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
test -f "$media/rbwr/dist/index.html"
apt-get update
apt-get install -y --no-install-recommends thunar mousepad ristretto xterm pipewire-audio wireplumber
target=/opt/reactoros
stage=$(mktemp -d "$target/.update.XXXXXXXX")
cp -r "$media/rbwr/dist" "$stage/"
cp "$media/kiosk.html" "$media/plant-tools.html" "$stage/dist/"
cp "$media/local_server.py" "$media/database_service.py" "$media/workstation_programs.py" "$media/workstation_access.py" "$target/"
cp "$media/manage-users.py" "$target/"
mv "$target/rbwr/dist" "$stage/previous"
if ! mv "$stage/dist" "$target/rbwr/dist"; then
    mv "$stage/previous" "$target/rbwr/dist"
    exit 1
fi
printf 'Update installed. Reboot to restart the kiosk session. Previous build: %s/previous\n' "$stage"
