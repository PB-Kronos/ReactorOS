#!/usr/bin/python3
"""Manage the one-time login handoff after a ReactorOS desktop update."""
import configparser
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

STATE_DIR = Path("/var/lib/reactoros/update-autologin")
STATE_FILE = STATE_DIR / "state.json"
BACKUP_FILE = STATE_DIR / "display-manager.conf.backup"
RUNTIME_USER = Path("/run/reactoros-update-autologin-user")
SUDOERS_FILE = Path("/etc/sudoers.d/reactoros-update-autologin")
HELPER = "/usr/lib/reactoros/clear-update-autologin"
TIMER = "reactoros-update-autologin-cleanup.timer"


def require_root():
    if os.geteuid() != 0:
        raise RuntimeError("This helper must run as root.")


def display_manager_config():
    result = subprocess.run(
        ["systemctl", "show", "display-manager.service", "--property=FragmentPath", "--value"],
        capture_output=True, text=True, check=False,
    )
    unit = Path(result.stdout.strip()).name.lower()
    if result.returncode or not unit:
        raise RuntimeError("Could not identify the active display manager.")
    if "gdm" in unit:
        return "gdm", Path("/run/gdm/custom.conf")
    if "lightdm" in unit:
        return "lightdm", Path("/etc/lightdm/lightdm.conf.d/99-reactoros-update-autologin.conf")
    raise RuntimeError(f"Automatic return login is not configured for {unit}.")


def prepare(username):
    require_root()
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username):
        raise RuntimeError("Invalid account name for automatic return login.")
    account = pwd.getpwnam(username)
    if account.pw_uid < 1000 or account.pw_uid == 65534:
        raise RuntimeError("Automatic return login is limited to regular user accounts.")
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STATE_FILE.exists():
        clear(timeout=True)
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

    manager, config_path = display_manager_config()
    config_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    original_exists = config_path.is_file()
    if original_exists:
        shutil.copy2(config_path, BACKUP_FILE)
    else:
        BACKUP_FILE.unlink(missing_ok=True)

    if manager == "gdm":
        parser = configparser.RawConfigParser(interpolation=None)
        parser.optionxform = str
        if original_exists:
            parser.read(config_path)
        if not parser.has_section("daemon"):
            parser.add_section("daemon")
        parser.set("daemon", "AutomaticLoginEnable", "true")
        parser.set("daemon", "AutomaticLogin", username)
        with config_path.open("w", encoding="utf-8") as stream:
            parser.write(stream)
    else:
        config_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        config_path.write_text(
            "[Seat:*]\nautologin-user=" + username + "\nautologin-user-timeout=0\n",
            encoding="utf-8",
        )
        config_path.chmod(0o644)

    state = {
        "username": username,
        "manager": manager,
        "config": str(config_path),
        "original_exists": original_exists,
        "uid": account.pw_uid,
    }
    STATE_FILE.write_text(json.dumps(state) + "\n", encoding="utf-8")
    STATE_FILE.chmod(0o600)
    RUNTIME_USER.write_text(username + "\n", encoding="utf-8")
    RUNTIME_USER.chmod(0o644)
    SUDOERS_FILE.write_text(
        f"{username} ALL=(root) NOPASSWD: {HELPER} \"\"\n", encoding="utf-8",
    )
    SUDOERS_FILE.chmod(0o440)
    check = subprocess.run(["visudo", "-cf", str(SUDOERS_FILE)], capture_output=True, text=True)
    if check.returncode:
        clear(timeout=True)
        raise RuntimeError("Could not safely configure one-time return-login cleanup: " +
                           (check.stderr.strip() or check.stdout.strip()))


def clear(timeout=False):
    require_root()
    if not STATE_FILE.is_file():
        SUDOERS_FILE.unlink(missing_ok=True)
        RUNTIME_USER.unlink(missing_ok=True)
        subprocess.run(["systemctl", "disable", "--now", TIMER],
                       capture_output=True, check=False)
        if STATE_DIR.is_dir():
            BACKUP_FILE.unlink(missing_ok=True)
            STATE_DIR.rmdir()
        return
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not timeout:
        caller_uid = int(os.environ.get("SUDO_UID", "-1"))
        if caller_uid != state.get("uid"):
            raise RuntimeError("Only the account that requested the update can clear this handoff.")

    config_path = Path(state["config"])
    if BACKUP_FILE.is_file():
        config_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.copy2(BACKUP_FILE, config_path)
    elif not state.get("original_exists"):
        config_path.unlink(missing_ok=True)
    else:
        raise RuntimeError("The saved display-manager backup is missing; automatic login was left unchanged.")
    STATE_FILE.unlink(missing_ok=True)
    BACKUP_FILE.unlink(missing_ok=True)
    RUNTIME_USER.unlink(missing_ok=True)
    SUDOERS_FILE.unlink(missing_ok=True)
    subprocess.run(["systemctl", "disable", "--now", TIMER],
                   capture_output=True, check=False)
    STATE_DIR.rmdir()


def main(argv):
    try:
        if len(argv) == 3 and argv[1] == "prepare":
            prepare(argv[2])
        elif len(argv) == 2 and argv[1] == "clear":
            clear()
        elif len(argv) == 2 and argv[1] == "timeout":
            clear(timeout=True)
        else:
            print("Usage: reactoros-update-autologin.py prepare USER | clear | timeout", file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ReactorOS return-login setup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
