"""Debian account to ReactorOS permission mapping."""
import json
import os
from pathlib import Path

from workstation_programs import PROGRAMS

ROLE_FILE = Path("/etc/reactoros/roles.json")
APP_PERMISSIONS = {f"app:{name}" for name in PROGRAMS} | {
    "app:files", "app:editor", "app:images", "app:browser", "app:disk-management",
    "app:live-variables", "app:events",
}
PERMISSIONS = APP_PERMISSIONS | {"database:edit", "users:manage", "terminal:execute"}
BASIC = {"app:greeting", "app:manual", "app:status-desk"}
DEFAULT_ROLES = {
    "trainee": BASIC,
    "operator": BASIC | {"app:reactor", "app:mainframe"},
    "technician": BASIC | {"app:files", "app:editor", "app:images", "app:events"},
    "supervisor": BASIC | {"app:reactor", "app:mainframe", "app:supervisor", "app:events"},
    "simulation-technician": APP_PERMISSIONS | {"database:edit"},
    "admin": PERMISSIONS,
}


def read_policy():
    try:
        return json.loads(ROLE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"roles": {}, "users": {}}


def debian_session():
    return os.environ.get("REACTOROS_DEBIAN_SESSION") == "1"


def current_access():
    import grp
    import pwd

    account = pwd.getpwuid(os.getuid())
    groups = set(os.getgrouplist(account.pw_name, account.pw_gid))
    try:
        sudo = grp.getgrnam("sudo").gr_gid in groups
    except KeyError:
        sudo = False
    try:
        policy = read_policy()
        roles = policy["users"].get(account.pw_name, ["admin" if sudo else "trainee"])
        permissions = set()
        for role in roles:
            permissions.update(DEFAULT_ROLES.get(role, policy["roles"].get(role, [])))
    except (OSError, ValueError, KeyError, TypeError):
        roles, permissions = [], set()
    if not sudo:
        permissions.difference_update({"users:manage", "terminal:execute"})
    return {"name": account.pw_name, "roles": roles, "sudoGroup": sudo,
            "permissions": sorted(permissions & PERMISSIONS)}


def permitted(permission):
    return not debian_session() or permission in current_access()["permissions"]
