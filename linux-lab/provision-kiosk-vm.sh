#!/bin/sh
set -eu

# Run from Debian Live inside the dedicated kiosk VM.
# The setup script attaches one new, empty virtual disk as /dev/sda.
disk=/dev/sda
target=/mnt/reactoros-system
media=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
test "$(id -u)" -eq 0
test "$(lsblk -dn -o TYPE "$disk")" = disk
test "$(blockdev --getsize64 "$disk")" -eq 5368709120
test "$(lsblk -nr -o NAME "$disk" | wc -l)" -eq 1
test -z "$(wipefs -n "$disk")"
test -f "$media/kiosk.html"

apt-get update
apt-get install -y --no-install-recommends debootstrap parted
parted -s "$disk" mklabel msdos mkpart primary ext4 1MiB 100% set 1 boot on
udevadm settle
mkfs.ext4 -L REACTOROS_VM "${disk}1"
mkdir -p "$target"
mount "${disk}1" "$target"
debootstrap --variant=minbase --include=ca-certificates trixie "$target" https://deb.debian.org/debian

for fs in dev proc sys; do
    mount --rbind "/$fs" "$target/$fs"
    mount --make-rslave "$target/$fs"
done
printf 'reactoros\n' > "$target/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 reactoros\n' > "$target/etc/hosts"
printf 'LABEL=REACTOROS_VM / ext4 defaults 0 1\n' > "$target/etc/fstab"
printf 'nameserver 10.0.2.3\n' > "$target/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$target/usr/sbin/policy-rc.d"
chmod +x "$target/usr/sbin/policy-rc.d"
chroot "$target" apt-get update
DEBIAN_FRONTEND=noninteractive chroot "$target" apt-get install -y --no-install-recommends \
    linux-image-amd64 grub-pc e2fsprogs systemd-sysv systemd-resolved dbus-user-session sudo iproute2 \
    lightdm lightdm-gtk-greeter xserver-xorg xserver-xorg-input-libinput xserver-xorg-video-vmware \
    openbox firefox-esr fonts-dejavu-core python3 python3-tk thunar mousepad ristretto xterm polkitd pkexec gparted \
    pipewire-audio wireplumber
rm "$target/usr/sbin/policy-rc.d"
mkdir -p "$target/opt/reactoros/rbwr" "$target/usr/share/xsessions" \
    "$target/etc/lightdm/lightdm.conf.d" "$target/etc/systemd/network"
cp "$media/local_server.py" "$media/database_service.py" "$media/workstation_programs.py" "$media/workstation_access.py" \
    "$media/kiosk-session.sh" "$target/opt/reactoros/"
cp -r "$media/rbwr/dist" "$target/opt/reactoros/rbwr/"
cp "$media/manage-users.py" "$target/opt/reactoros/"
cp "$media/kiosk.html" "$media/plant-tools.html" "$target/opt/reactoros/rbwr/dist/"
cp "$media/reactoros.desktop" "$target/usr/share/xsessions/"
cp "$media/lightdm-reactoros.conf" "$target/etc/lightdm/lightdm.conf.d/90-reactoros.conf"
mkdir -p "$target/etc/default/grub.d"
printf 'GRUB_TIMEOUT=0\nGRUB_CMDLINE_LINUX_DEFAULT="quiet"\n' > "$target/etc/default/grub.d/90-reactoros.cfg"
printf '[Match]\nName=en*\n\n[Network]\nDHCP=yes\n' > "$target/etc/systemd/network/10-vbox.network"
chroot "$target" useradd -m -g operator -s /bin/bash operator
printf 'operator:live\n' | chroot "$target" chpasswd
chroot "$target" usermod -aG sudo operator
chroot "$target" systemctl enable lightdm systemd-networkd systemd-resolved
chroot "$target" systemctl set-default graphical.target
chroot "$target" grub-install --target=i386-pc "$disk"
chroot "$target" update-grub
chroot "$target" apt-get clean
sync
printf '\nReactorOS installed. Shut down, boot from the virtual disk, and sign in as operator.\n'
