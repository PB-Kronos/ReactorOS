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

boot_args='boot=live components username=reactor noautologin persistence persistence-label=REACTOROS_DATA module_blacklist=pcspkr'
lb config --distribution trixie --architectures amd64 --binary-images iso-hybrid \
    --debian-installer live --apt-recommends false --cache false \
    --archive-areas 'main non-free-firmware' --firmware-chroot false --firmware-binary false \
    --bootappend-live "$boot_args" --bootappend-live-failsafe "$boot_args nomodeset"

mkdir -p config/package-lists config/hooks/normal
printf '%s\n' live-boot live-config live-config-systemd user-setup systemd-sysv sudo \
    gdm3 xserver-xorg xserver-xorg-input-libinput xserver-xorg-video-all \
    firmware-amd-graphics libgl1-mesa-dri polkitd pkexec gparted \
    dbus-user-session gnome-session gnome-shell gnome-control-center \
    gnome-shell-extension-apps-menu gnome-shell-extension-dash-to-panel gnome-shell-extension-user-theme \
    dconf-cli python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
    firefox-esr fonts-dejavu-core python3 python3-tk iproute2 procps \
    thunar mousepad ristretto xterm pipewire-audio pipewire-alsa pipewire-pulse wireplumber alsa-utils pulseaudio-utils \
    network-manager network-manager-gnome wpasupplicant pavucontrol arandr x11-xserver-utils lxpolkit \
    debian-installer-launcher \
    curl ca-certificates openssl \
    > config/package-lists/reactoros.list.chroot
cat > config/hooks/normal/050-reactoros-dconf.hook.chroot <<'EOF'
#!/bin/sh
set -eu
dconf update
EOF
chmod 0755 config/hooks/normal/050-reactoros-dconf.hook.chroot

overlay=config/includes.chroot
app="$overlay/opt/reactoros"
mkdir -p "$app/rbwr" "$app/share/applications" "$overlay/usr/share/xsessions" \
    "$overlay/etc/dconf/profile" "$overlay/etc/dconf/db/reactoros.d" \
    "$overlay/usr/share/themes/ReactorOS95/gnome-shell" "$overlay/usr/local/sbin"
mkdir -p "$overlay/etc/X11/xorg.conf.d" "$overlay/etc/NetworkManager/conf.d"
cat > "$overlay/etc/X11/xorg.conf.d/90-reactoros-touchpad.conf" <<'EOF'
Section "InputClass"
    Identifier "ReactorOS touchpad defaults"
    MatchIsTouchpad "on"
    Driver "libinput"
    Option "Tapping" "on"
    Option "ScrollMethod" "twofinger"
EndSection
EOF
cat > "$overlay/etc/NetworkManager/conf.d/10-reactoros-managed.conf" <<'EOF'
[ifupdown]
managed=true
EOF
printf '%s\n' "$version" > "$app/VERSION"
install -m 0755 "$lab/reactoros-update.sh" "$overlay/usr/local/sbin/reactoros-update"
install -D -m 0644 "$lab/release-signing.pub" "$overlay/etc/reactoros/update-public.pem"
printf '%s\n' 'PB-Kronos/ReactorOS' > "$overlay/etc/reactoros/update-repo"
cp "$root/local_server.py" "$root/database_service.py" "$root/workstation_programs.py" "$root/workstation_access.py" "$app/"
cp -r "$root/rbwr/dist" "$app/rbwr/"
cp "$lab/manage-users.py" "$lab/reactoros-webapp.py" "$lab/reactoros-settings.py" "$app/"
cp -r "$lab/applications" "$app/share/"
install -m 0755 "$lab/system-migrate.sh" "$app/system-migrate.sh"
install -m 0755 "$lab/reactoros-update-from-session.sh" \
    "$overlay/usr/local/sbin/reactoros-update-from-session"
install -m 0755 "$lab/reactoros-update.sh" "$app/reactoros-update.sh"
cp "$lab/kiosk.html" "$lab/plant-tools.html" "$app/rbwr/dist/"
cp "$lab/kiosk-session.sh" "$app/"
cp "$lab/reactoros.desktop" "$overlay/usr/share/xsessions/"
install -m 0644 "$lab/reactoros-gnome-shell.css" \
    "$overlay/usr/share/themes/ReactorOS95/gnome-shell/gnome-shell.css"
printf '%s\n' 'user-db:reactoros' 'system-db:reactoros' > "$overlay/etc/dconf/profile/reactoros"
cat > "$overlay/etc/dconf/db/reactoros.d/00-reactoros" <<'EOF'
[org/gnome/shell]
enabled-extensions=['apps-menu@gnome-shell-extensions.gcampax.github.com','dash-to-panel@jderose9.github.com','user-theme@gnome-shell-extensions.gcampax.github.com']
disable-user-extensions=false

[org/gnome/shell/extensions/dash-to-panel]
panel-position='BOTTOM'
panel-size=34

[org/gnome/shell/extensions/user-theme]
name='ReactorOS95'

[org/gnome/desktop/background]
picture-options='none'
color-shading-type='solid'
primary-color='#008080'
secondary-color='#008080'

[org/gnome/desktop/interface]
color-scheme='prefer-light'
gtk-theme='Adwaita'
icon-theme='Adwaita'
EOF

lb build
mv live-image-amd64.hybrid.iso ReactorOS-amd64.iso
sha256sum ReactorOS-amd64.iso > ReactorOS-amd64.iso.sha256
