#!/bin/sh
set -eu

# Signed updates call this as root after verifying the complete update archive.
test "$(id -u)" -eq 0
packages='pipewire-audio pipewire-pulse wireplumber pavucontrol network-manager network-manager-gnome wpasupplicant lxpolkit arandr x11-xserver-utils'
missing=''
for package in $packages; do
    if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
        missing="$missing $package"
    fi
done
if [ -n "$missing" ]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $missing
fi

install -d -m 0755 /etc/X11/xorg.conf.d /etc/NetworkManager/conf.d
cat > /etc/X11/xorg.conf.d/90-reactoros-touchpad.conf <<'EOF'
Section "InputClass"
    Identifier "ReactorOS touchpad defaults"
    MatchIsTouchpad "on"
    Driver "libinput"
    Option "Tapping" "on"
    Option "ScrollMethod" "twofinger"
EndSection
EOF
cat > /etc/NetworkManager/conf.d/10-reactoros-managed.conf <<'EOF'
[ifupdown]
managed=true
EOF
systemctl enable --now NetworkManager.service
