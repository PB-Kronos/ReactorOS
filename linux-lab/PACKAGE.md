# Install ReactorOS on an existing Debian desktop

ReactorOS can be installed as a separate desktop session on an existing
Debian 13 system. The package installs the ReactorOS applications, RBWR
simulator, Win95 theme, Start menu and update tools. It leaves the current
display manager, default session and ordinary GNOME/KDE settings alone. At the
sign-in screen, choose **ReactorOS Desktop** to use it.

## Install once

Download the latest `reactoros-desktop_*_all.deb` from the
[ReactorOS releases](https://github.com/PB-Kronos/ReactorOS/releases/latest)
and install it with APT:

```sh
sudo apt install ./reactoros-desktop_1.1.N_all.deb
```

APT installs the desktop dependencies and configures the signed ReactorOS
package repository. The file name's version will change with each release.
Sign out, choose **ReactorOS Desktop** from the session menu, then sign in.

This package targets Debian 13 (Trixie) amd64. It can also work on Debian-based
systems whose GNOME Shell and library package versions match Trixie's; it is
not an AUR, Fedora, or universal Linux package.

## Update

The ReactorOS Settings window and Start menu both include **ReactorOS Update**.
It selects APT package updates by default, signs out only the ReactorOS
desktop, installs the package, and returns to the sign-in screen. If both
updaters are configured, the Update Manager also offers the signed legacy
archive updater as a recovery choice.

From a terminal, update ReactorOS alone with:

```sh
sudo apt update
sudo apt install --only-upgrade reactoros-desktop
```

`sudo apt update && sudo apt upgrade` also updates Debian's other installed
packages. APT verifies ReactorOS repository metadata with the archive key
bundled in the package.

## Local package build

After building `rbwr/dist`, build a `.deb` on Debian or Ubuntu with:

```sh
sh linux-lab/build-deb.sh v1.1.42 release-out
```

The release workflow builds the package and signed APT repository on each
source update. Repository signing uses the private key in the GitHub Actions
secret `REACTOROS_APT_SIGNING_KEY`; its public key is
`linux-lab/reactoros-archive-keyring.asc`. The local Windows account also has
a DPAPI-protected recovery copy at
`%APPDATA%\ReactorOS\secrets\reactoros-apt-key.dpapi`.
The archive key fingerprint is `8AA5 5A2F DBF0 B3AB 9CA7 B974 662B D5F9 0AF0 2E84`.
