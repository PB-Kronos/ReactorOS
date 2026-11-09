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

apt = Path('/etc/apt')
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
PY
packages='pipewire-audio pipewire-alsa pipewire-pulse wireplumber alsa-utils pavucontrol network-manager network-manager-gnome wpasupplicant lxpolkit arandr x11-xserver-utils'
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
