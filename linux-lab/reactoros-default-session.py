#!/usr/bin/python3
"""Set ReactorOS as each Debian account's initial desktop session once."""
from pathlib import Path
import os
import pwd
import sys
import tempfile

ACCOUNTS = Path("/var/lib/AccountsService/users")
MARKER = Path("/var/lib/reactoros-session-default-configured")


def set_session(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    updated = []
    in_user = False
    user_section_seen = False
    session_written = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_user and not session_written:
                updated.append("XSession=reactoros")
                session_written = True
            in_user = stripped == "[User]"
            user_section_seen = user_section_seen or in_user
            updated.append(line)
        elif in_user and stripped.startswith("XSession="):
            updated.append("XSession=reactoros")
            session_written = True
        else:
            updated.append(line)
    if in_user and not session_written:
        updated.append("XSession=reactoros")
        session_written = True
    if not user_section_seen:
        if updated and updated[-1] != "":
            updated.append("")
        updated.extend(("[User]", "XSession=reactoros"))
    content = "\n".join(updated).rstrip() + "\n"
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
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


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run this session setup as root.")
    if MARKER.exists():
        return
    users = [user for user in pwd.getpwall()
             if 1000 <= user.pw_uid < 60000 and user.pw_shell not in ("/usr/sbin/nologin", "/bin/false")]
    if not users:
        return
    for user in users:
        set_session(ACCOUNTS / user.pw_name)
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("ReactorOS selected as initial desktop session.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
