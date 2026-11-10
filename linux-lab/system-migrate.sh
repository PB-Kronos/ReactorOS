#!/bin/sh
set -eu

# Signed updates call this as root after verifying the complete update archive.
test "$(id -u)" -eq 0
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# Debian Installer may leave its installation DVD enabled as an APT source.
# A ReactorOS installer disc has no Debian Release index, so that stale entry
# makes every later apt-get update fail even when network mirrors are healthy.
python3 - <<'PY'
from pathlib import Path
import re
import os

def is_network_uri(uri):
    return re.match(r'^(?:https?|ftp|mirror):', uri, re.I) is not None

apt = Path(os.environ.get('REACTOROS_APT_ROOT', '/etc/apt'))
paths = [apt / 'sources.list', *apt.glob('sources.list.d/*.list')]
for path in paths:
    if not path.is_file():
        continue
    original = path.read_text()
    updated = re.sub(
        r'(?im)^([ \t]*deb(?:-src)?[ \t]+(?:\[[^]]+\][ \t]+)?)(cdrom:)',
        r'# ReactorOS disabled installer media: \1\2', original,
    )
    if updated != original:
        path.write_text(updated)

# Debian 13 requires an explicit Signed-By for its archive mirrors. Older
# installer media sometimes leave unsigned entries in sources.list; normalize
# only official Debian network entries, preserving their suites and options.
debian_keyring = '/usr/share/keyrings/debian-archive-keyring.gpg'
for path in paths:
    if not path.is_file():
        continue
    original = path.read_text()
    updated_lines = []
    changed = False
    for line in original.splitlines():
        match = re.match(r'^([ \t]*deb(?:-src)?[ \t]+)(?:\[([^]]*)\][ \t]+)?(\S+)([ \t]+.*)$', line)
        if not match or not re.match(r'^https?://(?:deb\.debian\.org|security\.debian\.org)(?:/|$)', match.group(3), re.I):
            updated_lines.append(line)
            continue
        prefix, options, uri, tail = match.groups()
        option_list = (options or '').split()
        if not any(option.lower().startswith('signed-by=') for option in option_list):
            option_list.append('signed-by=' + debian_keyring)
            changed = True
        if 'non-free-firmware' not in tail.split('#', 1)[0].split():
            tail = tail.rstrip() + ' non-free-firmware'
            changed = True
        updated_lines.append(prefix + '[' + ' '.join(option_list) + '] ' + uri + tail)
    updated = '\n'.join(updated_lines) + ('\n' if original.endswith('\n') else '')
    if changed:
        path.write_text(updated)

for path in apt.glob('sources.list.d/*.sources'):
    original = path.read_text()
    stanzas = re.split(r'\n[ \t]*\n', original)
    changed = False
    for index, stanza in enumerate(stanzas):
        lines = stanza.splitlines()
        for line_index, line in enumerate(lines):
            if not re.match(r'^URIs:', line, re.I):
                continue
            uri_lines = [line_index]
            cursor = line_index + 1
            while cursor < len(lines) and re.match(r'^[ \t]+\S', lines[cursor]):
                uri_lines.append(cursor)
                cursor += 1
            uri_values = [lines[line_index].split(':', 1)[1]]
            uri_values.extend(lines[pos].strip() for pos in uri_lines[1:])
            uris = ' '.join(uri_values).split()
            if not any(uri.lower().startswith('cdrom:') for uri in uris):
                break
            remaining = [uri for uri in uris if not uri.lower().startswith('cdrom:')]
            if remaining:
                lines[line_index] = 'URIs: ' + ' '.join(remaining)
                for pos in reversed(uri_lines[1:]):
                    del lines[pos]
            else:
                enabled = next((pos for pos, value in enumerate(lines)
                                if re.match(r'^Enabled:', value, re.I)), None)
                if enabled is None:
                    lines.append('Enabled: no')
                else:
                    lines[enabled] = 'Enabled: no'
            stanzas[index] = '\n'.join(lines)
            changed = True
            break
    if changed:
        path.write_text('\n\n'.join(stanzas).rstrip() + '\n')

# Apply equivalent corrections to deb822 source files while leaving third-party
# repositories alone. Add the non-free firmware component needed by Wi-Fi.
for path in apt.glob('sources.list.d/*.sources'):
    original = path.read_text()
    stanzas = re.split(r'\n[ \t]*\n', original)
    changed = False
    for index, stanza in enumerate(stanzas):
        if re.search(r'(?mi)^Enabled:[ \t]*no[ \t]*$', stanza):
            continue
        uris_match = re.search(r'(?mi)^URIs:[ \t]*([^\n]*(?:\n[ \t]+[^\n]*)*)', stanza)
        if not uris_match or not re.search(r'https?://(?:deb\.debian\.org|security\.debian\.org)(?:/|$)', uris_match.group(1), re.I):
            continue
        updated = stanza
        if not re.search(r'(?mi)^Signed-By:', updated):
            updated += '\nSigned-By: ' + debian_keyring
        components = re.search(r'(?mi)^Components:[ \t]*(.*(?:\n[ \t]+.*)*)', updated)
        if components and 'non-free-firmware' not in components.group(1).split():
            updated = updated[:components.start(1)] + components.group(1).rstrip() + ' non-free-firmware' + updated[components.end(1):]
        if updated != stanza:
            stanzas[index] = updated
            changed = True
    if changed:
        path.write_text('\n\n'.join(stanzas).rstrip() + '\n')

# Some offline Debian installs have only the DVD listed in APT. If no active
# network mirror remains, provide Debian's official Trixie and security repos.
network_mirror = False
for path in [apt / 'sources.list', *apt.glob('sources.list.d/*.list')]:
    if not path.is_file():
        continue
    for line in path.read_text().splitlines():
        match = re.match(r'^[ \t]*deb(?:-src)?[ \t]+(?:\[[^]]+\][ \t]+)?(\S+)', line)
        if match and is_network_uri(match.group(1)):
            network_mirror = True
            break
for path in apt.glob('sources.list.d/*.sources'):
    for stanza in re.split(r'\n[ \t]*\n', path.read_text()):
        if re.search(r'(?mi)^Enabled:[ \t]*no[ \t]*$', stanza):
            continue
        match = re.search(r'(?mi)^URIs:[ \t]*([^\n]*(?:\n[ \t]+[^\n]*)*)', stanza)
        if match and any(is_network_uri(uri) for uri in match.group(1).split()):
            network_mirror = True
            break
if not network_mirror:
    source_file = apt / 'sources.list.d/reactoros-debian.sources'
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text('''Types: deb
URIs: https://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: https://security.debian.org/debian-security
Suites: trixie-security
Components: main non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
''')
PY
packages='dbus-user-session pipewire-audio pipewire-alsa pipewire-pulse wireplumber alsa-utils pulseaudio-utils pavucontrol network-manager network-manager-gnome wpasupplicant firmware-iwlwifi firmware-realtek firmware-atheros firmware-brcm80211 lxpolkit arandr x11-xserver-utils gnome-session gnome-shell gnome-control-center gnome-shell-extension-apps-menu gnome-shell-extension-dash-to-panel gnome-shell-extension-user-theme dconf-cli python3-gi python3-tk gir1.2-gtk-3.0 gir1.2-webkit2-4.1'
missing=''
for package in $packages; do
    if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
        missing="$missing $package"
    fi
done
if [ -n "$missing" ]; then
    printf 'ReactorOS migration: installing missing packages:%s\n' "$missing"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $missing
fi

# A previous interrupted/manual install can leave dpkg metadata present while
# the session launchers themselves are absent. Repair those critical binaries.
gnome_reinstall=''
if [ ! -x /usr/bin/gnome-session ]; then
    gnome_reinstall="$gnome_reinstall gnome-session-bin"
fi
if [ ! -x /usr/bin/gnome-shell ]; then
    gnome_reinstall="$gnome_reinstall gnome-shell"
fi
if [ -n "$gnome_reinstall" ]; then
    printf 'ReactorOS migration: repairing missing GNOME executables:%s\n' "$gnome_reinstall"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --reinstall --no-install-recommends $gnome_reinstall
fi
test -x /usr/bin/gnome-session || { echo 'GNOME session manager is still missing after migration.' >&2; exit 1; }
test -x /usr/bin/gnome-shell || { echo 'GNOME Shell is still missing after migration.' >&2; exit 1; }

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
nmcli radio wifi on >/dev/null 2>&1 || true

install -d -m 0755 /etc/dconf/profile /etc/dconf/db/reactoros.d \
    /etc/dconf/db/reactoros.d/locks \
    /usr/share/xsessions /usr/share/themes/ReactorOS95/gnome-shell \
    /usr/share/themes/ReactorOS95/gtk-3.0 /usr/share/themes/ReactorOS95/gtk-4.0 \
    /opt/reactoros/share/applications
printf '%s\n' 'user-db:reactoros' 'system-db:reactoros' > /etc/dconf/profile/reactoros
cat > /etc/dconf/db/reactoros.d/00-reactoros <<'EOF'
[org/gnome/shell]
enabled-extensions=['apps-menu@gnome-shell-extensions.gcampax.github.com','dash-to-panel@jderose9.github.com','user-theme@gnome-shell-extensions.gcampax.github.com']
disable-user-extensions=false

[org/gnome/mutter]
overlay-key=''

[org/gnome/shell/keybindings]
toggle-application-view=@as []
toggle-overview=@as []

[org/gnome/shell/extensions/apps-menu]
apps-menu-toggle-menu=['Super_L']

[org/gnome/shell/extensions/dash-to-panel]
panel-position='BOTTOM'
panel-size=34
show-activities-button=false
panel-element-positions='{"0":[{"element":"showAppsButton","visible":false,"position":"stackedTL"},{"element":"activitiesButton","visible":false,"position":"stackedTL"},{"element":"leftBox","visible":true,"position":"stackedTL"},{"element":"taskbar","visible":true,"position":"stackedTL"},{"element":"centerBox","visible":true,"position":"stackedBR"},{"element":"rightBox","visible":true,"position":"stackedBR"},{"element":"dateMenu","visible":true,"position":"stackedBR"},{"element":"systemMenu","visible":true,"position":"stackedBR"},{"element":"desktopButton","visible":true,"position":"stackedBR"}],"1":[{"element":"showAppsButton","visible":false,"position":"stackedTL"},{"element":"activitiesButton","visible":false,"position":"stackedTL"},{"element":"leftBox","visible":true,"position":"stackedTL"},{"element":"taskbar","visible":true,"position":"stackedTL"},{"element":"centerBox","visible":true,"position":"stackedBR"},{"element":"rightBox","visible":true,"position":"stackedBR"},{"element":"dateMenu","visible":true,"position":"stackedBR"},{"element":"systemMenu","visible":true,"position":"stackedBR"},{"element":"desktopButton","visible":true,"position":"stackedBR"}]}'

[org/gnome/shell/extensions/user-theme]
name='ReactorOS95'

[org/gnome/desktop/background]
picture-options='none'
color-shading-type='solid'
primary-color='#008080'
secondary-color='#008080'

[org/gnome/desktop/interface]
color-scheme='prefer-light'
icon-theme='Adwaita'
enable-hot-corners=false

[org/gnome/desktop/notifications]
show-banners=false
show-in-lock-screen=false
EOF
cat > /etc/dconf/db/reactoros.d/locks/00-reactoros <<'EOF'
/org/gnome/desktop/interface/enable-hot-corners
/org/gnome/desktop/notifications/show-banners
/org/gnome/desktop/notifications/show-in-lock-screen
/org/gnome/mutter/overlay-key
/org/gnome/shell/enabled-extensions
/org/gnome/shell/keybindings/toggle-application-view
/org/gnome/shell/keybindings/toggle-overview
/org/gnome/shell/extensions/apps-menu/apps-menu-toggle-menu
/org/gnome/shell/extensions/dash-to-panel/panel-element-positions
/org/gnome/shell/extensions/user-theme/name
EOF
install -m 0644 "$script_dir/reactoros.desktop" /usr/share/xsessions/reactoros.desktop
install -m 0644 "$script_dir/reactoros-gnome-shell.css" \
    /usr/share/themes/ReactorOS95/gnome-shell/gnome-shell.css
install -m 0644 "$script_dir/themes/ReactorOS95/gtk-3.0/gtk.css" \
    /usr/share/themes/ReactorOS95/gtk-3.0/gtk.css
install -m 0644 "$script_dir/themes/ReactorOS95/gtk-4.0/gtk.css" \
    /usr/share/themes/ReactorOS95/gtk-4.0/gtk.css
install -m 0755 "$script_dir/reactoros-update-from-session.sh" \
    /usr/local/sbin/reactoros-update-from-session
cp "$script_dir"/applications/*.desktop /opt/reactoros/share/applications/
apps_menu_source=/usr/share/gnome-shell/extensions/apps-menu@gnome-shell-extensions.gcampax.github.com
apps_menu_target=/opt/reactoros/share/gnome-shell/extensions/apps-menu@gnome-shell-extensions.gcampax.github.com
if [ -d "$apps_menu_source" ]; then
    install -d -m 0755 "$(dirname "$apps_menu_target")"
    rm -rf -- "$apps_menu_target"
    cp -a "$apps_menu_source" "$apps_menu_target"
    sed -i "s/text: _('Apps')/text: _('Start')/" "$apps_menu_target/extension.js"
    python3 "$script_dir/patch-apps-menu.py" "$apps_menu_target/extension.js"
fi
dconf update
