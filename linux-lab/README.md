# ReactorOS Linux lab

GitHub release and bootable USB instructions are in [Releases and USB](RELEASES.md).

For an existing Debian desktop, install ReactorOS as a separate session from
the signed Debian package. See [Install ReactorOS on Debian](PACKAGE.md).
This is the recommended way to use ReactorOS without replacing the Linux
distribution; the bootable image remains available for USB installation.

**ReactorOS Kiosk Lab** is the separate persistent VM for testing the
Windows 95-style workstation. Its VirtualBox configuration and virtual
disk live under `linux-lab/ReactorOS Kiosk Lab`. For installed systems, the
ReactorOS desktop is a separately selectable GDM session built on GNOME Shell.
It uses a dedicated dconf profile, application directory and Win95-style GTK
and Shell themes, so the user's regular GNOME and KDE sessions keep their own
settings and menus. Its single categorized Start menu opens with the Super
key; GNOME Overview shortcuts and hot corners are disabled only in this
session. OS notification banners are quieted only in ReactorOS. Pick
**ReactorOS Desktop** from GDM's session selector at sign-in. Mutter manages
native movable windows and multi-monitor placement; the RBWR program opens
maximized by default. The lab account is `operator` with the initial lab
password `live`.
The desktop reads the real Debian username from the local server.
The Settings updater asks systemd-logind to sign out only the active ReactorOS
session, then runs the signed update as a detached system service. It works
with GDM and LightDM without stopping the display manager for other users.
The session writes startup diagnostics to
`~/.local/state/reactoros/gnome-session.log` and
`~/.local/state/reactoros/local-server.log` if a desktop session fails to start.
From a text console, `sudo /opt/reactoros/system-migrate.sh` repairs system
packages even if the installed app version is already current. The updater
also refreshes its CLI copy from the installed app before the next update.

For an existing kiosk VM, run `Attach-Kiosk-Update.ps1` on the Windows
host after building RBWR. In the VM, switch to a Debian console with
`Ctrl+Alt+F2`, sign in, and run:

```sh
sudo mkdir -p /mnt/reactoros-update
sudo mount -o ro /dev/sr1 /mnt/reactoros-update
sudo sh /mnt/reactoros-update/update-kiosk.sh
sudo reboot
```

The Settings window contains the device controls, account management,
disk management, and software update actions. Wi-Fi, sound, and display
controls are also available from the Start menu for accounts with permission.
Its audio section reports whether PipeWire is responding
and whether output devices are visible, and can restart the current user's
PipeWire services. Sound Settings opens the mixer for choosing the correct
output device, port, and volume. The update installs PipeWire's ALSA bridge
and ALSA diagnostic tools as well as the audio services. It installs Debian's
systemd-integrated user D-Bus session so PipeWire's per-user services can be
controlled from the kiosk session. The kiosk explicitly starts the Pulse
endpoint before launching the mixer and reports a startup error instead of
leaving the mixer stuck while it waits for a missing server.
It also disables the stale installer-DVD entry in APT and adds official Debian
Trixie network mirrors when an offline install has no usable mirror configured.
It also adds a read-only view of recent SQLite server events and three
simulation overrides under Live Variables. The kiosk's command console
uses the Debian identity with the simulator's existing supervisor access.

**User Manager** opens from Start for an account that has both the
`users:manage` permission and Debian sudo membership. Authenticate with
your own Debian password. It lists accounts, creates Debian users, resets
passwords, assigns one or more built-in or custom ReactorOS roles, and
manages the actual Debian sudo group. Role permissions are additive.
The Start Menu Editor has a per-account app allowlist. Checking an app both
shows it in that user's ReactorOS Start menu and grants its ReactorOS launch
permission; unchecking it hides and blocks that app. Non-app privileges such
as user administration and database editing remain role-based. Menu overrides
are applied only in the ReactorOS session, leaving ordinary GNOME and KDE
menus unchanged.
Unassigned accounts start as trainee, or admin if they already belong to
Debian's sudo group. Reload the kiosk or sign in again to refresh Start.

ReactorOS permissions govern the workstation menu and local endpoints.
Debian controls OS access. The File Explorer permission governs the
ReactorOS launcher and does not change filesystem permissions.

The kiosk VM uses a dynamically allocated disk capped at 5 GiB. Keep the
VM powered off when copying its folder. The build recipe
`build-kiosk-iso.sh` creates the separate ReactorOS USB image. It includes
both a live desktop and Debian Installer. Choose the installer entry to place
the full workstation on a writable disk or a second USB drive; the installed
system keeps files and package changes on that drive and supports signed
application and system-package updates.

Press the Windows/Super key to open the ReactorOS Start menu. The Start menu
includes **Disk Management** (GParted) for accounts with the
`app:disk-management` permission. Debian asks for authorization before
GParted performs privileged disk operations.

**ReactorOS Linux Lab** boots Debian Live Standard in VirtualBox. The VM has
no hard disk. Its second virtual DVD contains the built ReactorOS workstation,
the Python server, and the SQLite worker. Changes inside the guest are
temporary and disappear on reboot.

At the Debian shell, mount the tools disc and start the server:

```sh
sudo mkdir -p /mnt/reactoros
sudo mount -o ro /dev/sr1 /mnt/reactoros
sh /mnt/reactoros/start-linux.sh
```

The script copies the files into a writable temporary directory. Press
Ctrl+C to stop the server and database worker. In another guest console,
check the running stack and the guest itself:

```sh
python3 -c 'from urllib.request import urlopen; print(urlopen("http://127.0.0.1:18765/api/status").read().decode())'
uname -a
ip -brief address
systemctl --failed
```

The standard image boots to a console. To test the native ReactorOS GNOME
session, choose **ReactorOS Desktop** on the GDM sign-in screen. The ordinary
GNOME and KDE sessions remain independently selectable. Firefox is retained
as the Internet application; ReactorOS programs open in movable native GTK
windows with the simulation content hosted locally. Keep real Linux
administration in the guest shell. The simulator terminal currently accepts
plant commands only.

To recreate the VM, place the verified Debian 13.7.0 amd64 standard live ISO
in this directory and run `Setup-Linux-Lab.ps1` from PowerShell. The VM's
tools disc references the current workstation build on the host.
