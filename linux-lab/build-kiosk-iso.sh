#!/bin/sh
set -eu

# Run as root on Debian, with an empty native Linux build directory.
if [ "$#" -ne 3 ] || [ "$(id -u)" -ne 0 ]; then
    printf 'Usage: sudo sh build-kiosk-iso.sh PROJECT_ROOT EMPTY_BUILD_DIR VERSION\n' >&2
    exit 2
fi
root=$(realpath "$1")
lab="$root/linux-lab"
version=$3
printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'
test -f "$root/rbwr/dist/index.html"
mkdir -p "$2"
cd "$2"
if [ -n "$(ls -A)" ]; then
    printf 'Use an empty build directory.\n' >&2
    exit 2
fi

boot_args='boot=live components username=reactor noautologin persistence persistence-label=REACTOROS_DATA'
lb config --distribution trixie --architectures amd64 --binary-images iso-hybrid \
    --debian-installer none --apt-recommends false --cache false \
    --archive-areas 'main non-free-firmware' --firmware-chroot false --firmware-binary false \
    --bootappend-live "$boot_args" --bootappend-live-failsafe "$boot_args nomodeset"

mkdir -p config/package-lists
printf '%s\n' live-boot live-config live-config-systemd user-setup systemd-sysv sudo \
    lightdm lightdm-gtk-greeter xserver-xorg xserver-xorg-input-libinput xserver-xorg-video-all \
    firmware-amd-graphics libgl1-mesa-dri polkitd pkexec gparted \
    dbus-x11 openbox firefox-esr fonts-dejavu-core python3 python3-tk iproute2 procps \
    thunar mousepad ristretto xterm pipewire-audio wireplumber curl ca-certificates openssl \
    > config/package-lists/reactoros.list.chroot

overlay=config/includes.chroot
app="$overlay/opt/reactoros"
mkdir -p "$app/rbwr" "$overlay/usr/share/xsessions" "$overlay/etc/lightdm/lightdm.conf.d" "$overlay/usr/local/sbin"
printf '%s\n' "$version" > "$app/VERSION"
install -m 0755 "$lab/reactoros-update.sh" "$overlay/usr/local/sbin/reactoros-update"
install -D -m 0644 "$lab/release-signing.pub" "$overlay/etc/reactoros/update-public.pem"
printf '%s\n' 'PB-Kronos/ReactorOS' > "$overlay/etc/reactoros/update-repo"
cp "$root/local_server.py" "$root/database_service.py" "$root/workstation_programs.py" "$root/workstation_access.py" "$app/"
cp -r "$root/rbwr/dist" "$app/rbwr/"
cp "$lab/manage-users.py" "$app/"
cp "$lab/kiosk.html" "$lab/plant-tools.html" "$app/rbwr/dist/"
cp "$lab/kiosk-session.sh" "$app/"
cp "$lab/reactoros.desktop" "$overlay/usr/share/xsessions/"
cp "$lab/lightdm-reactoros.conf" "$overlay/etc/lightdm/lightdm.conf.d/90-reactoros.conf"

lb build
mv live-image-amd64.hybrid.iso ReactorOS-amd64.iso
sha256sum ReactorOS-amd64.iso > ReactorOS-amd64.iso.sha256
