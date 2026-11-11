#!/usr/bin/python3
"""Remove the old ReactorOS migration that overrode each account's session."""
from pathlib import Path
import os
import pwd
import tempfile

ACCOUNTS = Path("/var/lib/AccountsService/users")
MARKER = Path("/var/lib/reactoros-session-default-configured")


def remove_reactoros_session(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False

    updated = []
    in_user = False
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_user = stripped.lower() == "[user]"
            updated.append(line)
            continue
        if in_user and stripped.lower().startswith("xsession=") and \
                stripped.split("=", 1)[1].strip().lower() == "reactoros":
            changed = True
            continue
        updated.append(line)

    if not changed:
        return False
    content = "\n".join(updated).rstrip() + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".reactoros-session-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return True


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run this session repair as root.")
    for account in pwd.getpwall():
        if 1000 <= account.pw_uid < 60000:
            remove_reactoros_session(ACCOUNTS / account.pw_name)

    # Old releases enabled a boot service that repeated the override. Keep its
    # guard marker so a stale copy of that service cannot force ReactorOS back.
    MARKER.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    MARKER.write_text("ReactorOS no longer overrides the selected desktop session.\n",
                      encoding="utf-8")


if __name__ == "__main__":
    main()
