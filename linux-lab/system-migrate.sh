#!/bin/sh
set -eu

# Signed updates call this as root after verifying the complete update archive.
test "$(id -u)" -eq 0
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

Types: deb
URIs: https://security.debian.org/debian-security
Suites: trixie-security
Components: main non-free-firmware
''')
PY
packages='dbus-user-session pipewire-audio pipewire-alsa pipewire-pulse wireplumber alsa-utils pavucontrol network-manager network-manager-gnome wpasupplicant lxpolkit arandr x11-xserver-utils'
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
