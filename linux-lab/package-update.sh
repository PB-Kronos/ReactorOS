#!/bin/sh
set -eu
version=${1:?Pass a release version such as v1.1.42}
printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'
lab=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
root=$(dirname "$lab")
test -f "$root/rbwr/dist/index.html"
output=${2:-"$root/release-out"}
mkdir -p "$output"
output=$(realpath "$output")
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/rbwr" "$stage/share/applications" "$stage/themes"
cp "$root/local_server.py" "$root/database_service.py" "$root/workstation_programs.py" \
    "$root/workstation_access.py" "$lab/manage-users.py" "$lab/reactoros-menu-editor.py" \
    "$lab/reactoros-webapp.py" \
    "$lab/reactoros-settings.py" "$lab/patch-apps-menu.py" "$lab/reactoros.desktop" "$lab/reactoros-gnome-shell.css" \
    "$lab/reactoros-update-from-session.sh" "$lab/kiosk-session.sh" \
    "$lab/system-migrate.sh" "$lab/reactoros-update.sh" "$lab/reactoros-launch-app.py" "$stage/"
mkdir -p "$stage/applications"
cp "$lab"/applications/*.desktop "$stage/applications/"
cp "$lab"/applications/*.desktop "$stage/share/applications/"
cp -r "$lab/themes/ReactorOS95" "$stage/themes/"
chmod 0755 "$stage/system-migrate.sh" "$stage/reactoros-update.sh"
cp -r "$root/rbwr/dist" "$stage/rbwr/"
cp "$lab/kiosk.html" "$lab/plant-tools.html" "$stage/rbwr/dist/"
printf '%s\n' "$version" > "$stage/VERSION"
chmod 0755 "$stage"
tar -czf "$output/reactoros-update.tar.gz" -C "$stage" .
