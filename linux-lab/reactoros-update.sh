#!/bin/sh
set -eu
case "${1:-}" in
    ''|--scheduled) ;;
    *) echo 'Usage: reactoros-update [--scheduled]' >&2; exit 2 ;;
esac
test "$(id -u)" -eq 0 || { echo 'Run with sudo.' >&2; exit 1; }
app=/opt/reactoros
test -f "$app/kiosk-session.sh"
config=/etc/reactoros
repo=$(cat "$config/update-repo")
printf '%s\n' "$repo" | grep -Eq '^[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$'
test -s "$config/update-public.pem"
exec 9>/run/lock/reactoros-update.lock
flock -n 9 || { echo 'Another update is already running.' >&2; exit 1; }
require_idle() {
    if pgrep -f '^/bin/sh /opt/reactoros/kiosk-session.sh([[:space:]]|$)' >/dev/null; then
        if [ "${1:-}" = "--scheduled" ]; then
            echo 'Update deferred while the kiosk is running.'
            exit 0
        fi
        echo 'Sign out of the kiosk before updating.' >&2
        exit 1
    fi
}
require_idle "$@"

stage=$(mktemp -d /opt/.reactoros-update.XXXXXXXX)
trap 'rm -rf -- "$stage"' EXIT
url="https://github.com/$repo/releases/latest/download"
for asset in reactoros-update.tar.gz reactoros-update.tar.gz.sig; do
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --max-time 180 --max-filesize 250000000 "$url/$asset" -o "$stage/$asset"
done
openssl pkeyutl -verify -pubin -inkey "$config/update-public.pem" -rawin \
    -in "$stage/reactoros-update.tar.gz" -sigfile "$stage/reactoros-update.tar.gz.sig"

mkdir "$stage/app"
tar -xzf "$stage/reactoros-update.tar.gz" --no-same-owner --no-same-permissions -C "$stage/app"
version=$(cat "$stage/app/VERSION")
printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'
current=$(cat "$app/VERSION" 2>/dev/null || echo v0.0.0)
if [ "$version" = "$current" ] || [ "$(printf '%s\n%s\n' "$current" "$version" | sort -V | tail -1)" != "$version" ]; then
    echo "Installed version $current is already current or newer."
    exit 0
fi
test -f "$stage/app/rbwr/dist/index.html"
test -f "$stage/app/kiosk-session.sh"
python3 -m py_compile "$stage/app/"*.py
require_idle "$@"
backup=/opt/reactoros.previous
if [ -e "$backup" ]; then
    mv -T -- "$backup" "$stage/older"
fi
mv -T -- "$app" "$backup"
if ! mv -T -- "$stage/app" "$app"; then
    mv -T -- "$backup" "$app"
    exit 1
fi
echo "Installed ReactorOS $version. Sign in again to start the updated kiosk."
