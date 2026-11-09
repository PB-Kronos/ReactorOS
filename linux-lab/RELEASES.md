# ReactorOS releases and USB

Push the source to a GitHub repository with publicly downloadable release
assets. The current updater downloads public assets without a GitHub token.
VM disks, build output, local databases and signing keys are excluded by
`.gitignore`. Review `git status` before the initial push.

## Set up release signing once

On a trusted machine with OpenSSL, create a release key and public key:

```sh
umask 077
openssl genpkey -algorithm ED25519 -out release-private.pem
openssl pkey -in release-private.pem -pubout -out release-public.pem
```

Store the private PEM in the GitHub Actions secret `REACTOROS_RELEASE_KEY`.
Keep an offline backup. Deliver the public PEM to each machine over a trusted
path. The updater verifies the downloaded archive with that pinned key.

Each push to `main` builds, signs and publishes a software update as a GitHub
Release (`v1.1.N`). Installed systems can fetch it with the updater. This does
not rebuild an installed ISO automatically. To build a new USB ISO, run the
**Build ReactorOS USB image** workflow manually from GitHub Actions; it attaches
the ISO and SHA-256 file to the latest update release. No ISO is built for each
commit or update batch.

## Set up an existing Debian install

For the VirtualBox kiosk, attach the updater setup disc from Windows with
`./linux-lab/Attach-Updater-Setup.ps1 -PublicKey ./release-public.pem`.
In the guest, sign out of the kiosk and run this from the Debian admin console
to configure the updater and apply the latest published release:

```sh
sudo mkdir -p /mnt/reactoros-updater &&
  sudo mount -o ro /dev/sr1 /mnt/reactoros-updater &&
  sudo sh /mnt/reactoros-updater/install-updater.sh https://github.com/PB-Kronos/ReactorOS &&
  sudo /usr/local/sbin/reactoros-update
```

The disc installs the updater, pins the public key, and saves the repo URL.
After setup, use `sudo /usr/local/sbin/reactoros-update` while signed out of
the kiosk to apply a newer signed release.

For a manual setup without the disc, use the steps below.

From a Debian admin console, install the updater from trusted source media,
with the kiosk signed out. Substitute your actual GitHub owner and repo.

```sh
sudo apt-get install curl ca-certificates openssl xterm
sudo install -d -m 0755 /etc/reactoros
sudo install -m 0644 release-public.pem /etc/reactoros/update-public.pem
printf '%s\n' 'OWNER/REPO' | sudo tee /etc/reactoros/update-repo
sudo install -m 0755 reactoros-update.sh /usr/local/sbin/reactoros-update
sudo reactoros-update
```

Run `sudo reactoros-update` to request a newer release. It keeps the previous
application directory at `/opt/reactoros.previous` and retains the installed
Debian accounts, role configuration and per-user data. OS packages still
follow Debian's update path.

For opt-in daily updates, install the timer and service from the same trusted
source and enable the timer:

```sh
sudo install -m 0644 reactoros-update.service reactoros-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reactoros-update.timer
```

Scheduled runs skip active kiosk sessions and retry at the next scheduled
check. A kiosk that stays signed in needs a maintenance sign-out or a manual
update. Check results with `journalctl -u reactoros-update.service`.

## Build and write a USB

Open the latest GitHub Release and download `ReactorOS-amd64.iso` plus its
SHA-256 file from the release assets. Compare the hash with PowerShell
`Get-FileHash .\ReactorOS-amd64.iso -Algorithm SHA256`.

On Windows, use an image writer such as Rufus and choose DD image mode if it
asks. Select the actual USB device by size and name. Writing the image
overwrites that drive. Reboot, choose the USB in the PC's boot menu, and
select **Live system (amd64)**. Debian creates the `reactor` account and
opens the LightDM sign-in screen. Sign in as `reactor` with the initial
password `live` to start the ReactorOS kiosk. Use **Start → Sign Out**
to return to LightDM.

If the normal entry fails while initializing graphics, try **Live system
(amd64 fail-safe mode)**. This entry uses the same account and persistence
settings and disables kernel graphics modesetting. If the machine still
lands at a text console, sign in there and collect the graphics and display
manager errors with `sudo journalctl -b -k -g 'amdgpu|radeon|firmware'`
and `sudo journalctl -b -u lightdm --no-pager -n 40`.

A live image without a persistence volume forgets installed updates and user
changes after reboot. ReactorOS is configured to use Debian Live's full-root
overlay when a persistence volume is present. For persistence, use Linux to create an ext4 partition labelled
`REACTOROS_DATA` in the free space after the written image, or on a second USB
drive or internal drive connected before boot. Format only the intended data partition.
At the root of that partition, create `persistence.conf` containing `/ union`
on a single line. This saves changes to the live system, including accounts,
roles, home folders, databases, downloaded files and installed application
updates. Debian merges the writable overlay at boot; the system does not need
to copy folders into the read-only image first. Any changes made without the
labelled and configured partition attached remain temporary.

The boot entry searches for the `REACTOROS_DATA` label on attached storage,
including USB and internal drives. Keep one matching partition attached to
avoid ambiguity. The volume must be Linux-readable (ext4 is recommended),
and must contain the exact `/ union` line in `persistence.conf` at its root.

Verify persistence by creating a test file in your home folder, rebooting
with the same persistence volume attached, and checking the file is still
there. The live image is an amd64 build, and its firmware compatibility still
needs testing on the target PC.
