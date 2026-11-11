#!/bin/sh
set -eu

version=${1:?Pass a release version such as v1.1.42}
output=${2:-release-out}
keyring=${3:-}
printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'
package_version=${version#v}
lab=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
root=$(dirname "$lab")
test -f "$root/rbwr/dist/index.html" || {
    echo 'Build rbwr/dist before creating the Debian package.' >&2
    exit 1
}
command -v dpkg-deb >/dev/null 2>&1 || {
    echo 'dpkg-deb is required (run this builder on Debian or Ubuntu).' >&2
    exit 1
}
mkdir -p "$output"
output=$(realpath "$output")
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT HUP INT TERM
package="$stage/package"
app="$package/opt/reactoros"
mkdir -p "$package/DEBIAN" "$app/rbwr" "$app/share/applications" \
    "$package/usr/share/xsessions" "$package/usr/share/themes/ReactorOS95/gnome-shell" \
    "$package/usr/share/themes/ReactorOS95/gtk-3.0" \
    "$package/usr/share/themes/ReactorOS95/gtk-4.0" \
    "$package/etc/dconf/profile" "$package/etc/dconf/db/reactoros.d" \
    "$package/etc/dconf/db/reactoros.d/locks" \
    "$package/etc/reactoros" \
    "$package/usr/local/sbin" "$package/usr/lib/reactoros"

cp "$root/local_server.py" "$root/database_service.py" "$root/workstation_programs.py" \
    "$root/workstation_access.py" "$lab/manage-users.py" "$lab/reactoros-menu-editor.py" \
    "$lab/reactoros-webapp.py" "$lab/reactoros-settings.py" "$lab/patch-apps-menu.py" \
    "$lab/reactoros-default-session.py" "$lab/reactoros-update-now.py" \
    "$lab/reactoros-update-autologin.py" "$lab/clear-update-autologin" \
    "$lab/reactoros-update-autologin-cleanup.service" \
    "$lab/reactoros-update-autologin-cleanup.timer" \
    "$lab/reactoros-update-from-session.sh" "$lab/kiosk-session.sh" \
    "$lab/reactoros-launch-app.py" "$lab/reactoros-gnome-shell.css" \
    "$lab/reactoros-legacy-update-from-session.sh" \
    "$lab/reactoros-package-update.sh" "$lab/system-migrate.sh" \
    "$lab/reactoros-update.sh" "$app/"
cp "$lab"/applications/*.desktop "$app/share/applications/"
cp -R "$root/rbwr/dist" "$app/rbwr/"
cp "$lab/kiosk.html" "$lab/plant-tools.html" "$app/rbwr/dist/"
cp "$lab/themes/ReactorOS95/gtk-3.0/gtk.css" \
    "$package/usr/share/themes/ReactorOS95/gtk-3.0/gtk.css"
cp "$lab/themes/ReactorOS95/gtk-4.0/gtk.css" \
    "$package/usr/share/themes/ReactorOS95/gtk-4.0/gtk.css"
cp "$lab/reactoros-gnome-shell.css" \
    "$package/usr/share/themes/ReactorOS95/gnome-shell/gnome-shell.css"
cp "$lab/reactoros.desktop" "$package/usr/share/xsessions/reactoros.desktop"
cp "$lab/dconf-profile" "$package/etc/dconf/profile/reactoros"
cp "$lab/dconf-defaults" "$package/etc/dconf/db/reactoros.d/00-reactoros"
cp "$lab/dconf-locks" "$package/etc/dconf/db/reactoros.d/locks/00-reactoros"
cp "$lab/release-signing.pub" "$package/etc/reactoros/update-public.pem"
printf '%s\n' 'PB-Kronos/ReactorOS' > "$package/etc/reactoros/update-repo"
cp "$lab/reactoros-update-from-session.sh" \
    "$package/usr/local/sbin/reactoros-update-from-session"
cp "$lab/reactoros-legacy-update-from-session.sh" \
    "$package/usr/lib/reactoros/legacy-update"
cp "$lab/reactoros-package-update.sh" "$package/usr/lib/reactoros/package-update"
cp "$lab/reactoros-update.sh" "$package/usr/lib/reactoros/legacy-updater"
install -m 0644 "$lab/reactoros-update-autologin.py" \
    "$package/usr/lib/reactoros/update-autologin.py"
install -m 0755 "$lab/clear-update-autologin" \
    "$package/usr/lib/reactoros/clear-update-autologin"
install -m 0644 "$lab/reactoros-update-autologin-cleanup.service" \
    "$package/usr/lib/systemd/system/reactoros-update-autologin-cleanup.service"
install -m 0644 "$lab/reactoros-update-autologin-cleanup.timer" \
    "$package/usr/lib/systemd/system/reactoros-update-autologin-cleanup.timer"

if [ -n "$keyring" ]; then
    test -s "$keyring" || { echo "APT keyring not found: $keyring" >&2; exit 1; }
    install -D -m 0644 "$keyring" \
        "$package/usr/share/keyrings/reactoros-archive-keyring.gpg"
    install -D -m 0644 "$lab/reactoros-apt.sources" \
        "$package/etc/apt/sources.list.d/reactoros.sources"
fi

sed "s/@VERSION@/$package_version/" "$lab/debian-control.in" \
    > "$package/DEBIAN/control"
printf '%s\n' '/etc/reactoros/update-public.pem' '/etc/reactoros/update-repo' \
    > "$package/DEBIAN/conffiles"
install -m 0755 "$lab/debian-postinst" "$package/DEBIAN/postinst"
install -m 0755 "$lab/debian-postrm" "$package/DEBIAN/postrm"
chmod 0755 "$app/kiosk-session.sh" "$app/system-migrate.sh" \
    "$app/reactoros-update.sh" "$app/reactoros-update-from-session.sh" \
    "$package/usr/local/sbin/reactoros-update-from-session" \
    "$package/usr/lib/reactoros/legacy-update" \
    "$package/usr/lib/reactoros/legacy-updater" \
    "$package/usr/lib/reactoros/package-update" \
    "$package/usr/lib/reactoros/clear-update-autologin"
printf '%s\n' "$version" > "$app/VERSION"

dpkg-deb --build --root-owner-group "$package" \
    "$output/reactoros-desktop_${package_version}_all.deb"
