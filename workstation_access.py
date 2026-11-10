"""Debian account to ReactorOS permission mapping."""
import json
import os
from pathlib import Path

from workstation_programs import PROGRAMS

ROLE_FILE = Path("/etc/reactoros/roles.json")
APP_PERMISSIONS = {f"app:{name}" for name in PROGRAMS} | {
    "app:settings",
    "app:files", "app:editor", "app:images", "app:browser", "app:disk-management",
    "app:network", "app:audio-settings", "app:display-settings",
    "app:live-variables", "app:events",
}
PERMISSIONS = APP_PERMISSIONS | {"database:edit", "users:manage", "terminal:execute"}
BASIC = {"app:greeting", "app:manual", "app:status-desk", "app:settings", "app:network", "app:audio-settings", "app:display-settings"}
MENU_APPS = {
    "greeting": ("app:greeting", "Plant Operations Terminal", "reactoros-terminal.desktop"),
    "reactor": ("app:reactor", "RBWR Unit 2", "reactoros-rbwr.desktop"),
    "status-desk": ("app:status-desk", "Status Desk", "reactoros-status.desktop"),
    "supervisor": ("app:supervisor", "Plant Supervisor", "reactoros-supervisor.desktop"),
    "mainframe": ("app:mainframe", "RBWR Command Console", "reactoros-command.desktop"),
    "manual": ("app:manual", "Operator Manual", "reactoros-manual.desktop"),
    "live-variables": ("app:live-variables", "Plant Database", "reactoros-database.desktop"),
    "events": ("app:events", "Server Event Log", "reactoros-events.desktop"),
    "settings": ("app:settings", "ReactorOS Settings", "reactoros-settings.desktop"),
    "network": ("app:network", "Wi-Fi & Network", "reactoros-network.desktop"),
    "files": ("app:files", "File Explorer", "reactoros-files.desktop"),
    "editor": ("app:editor", "Text Editor", "reactoros-editor.desktop"),
    "images": ("app:images", "Image Viewer", "reactoros-images.desktop"),
    "browser": ("app:browser", "Internet Browser", "reactoros-browser.desktop"),
    "disk-management": ("app:disk-management", "Disk Management", "reactoros-disk-management.desktop"),
    "audio-settings": ("app:audio-settings", "Sound Settings", "reactoros-audio-settings.desktop"),
    "display-settings": ("app:display-settings", "Display Settings", "reactoros-display-settings.desktop"),
}
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
    policy = {"roles": {}, "users": {}, "visible_apps": {}}
    try:
        policy = read_policy()
        roles = policy["users"].get(account.pw_name, ["admin" if sudo else "trainee"])
        permissions = set()
        for role in roles:
            permissions.update(DEFAULT_ROLES.get(role, policy["roles"].get(role, [])))
    except (OSError, ValueError, KeyError, TypeError):
        policy = {"roles": {}, "users": {}, "visible_apps": {}}
        roles, permissions = [], set()
    if not sudo:
        permissions.difference_update({"users:manage", "terminal:execute"})
    allowed = permissions & PERMISSIONS
    visible_apps = policy.get("visible_apps", {}).get(account.pw_name)
    if visible_apps is None:
        visible_apps = [app for app, (permission, _label, _desktop) in MENU_APPS.items()
                        if permission in allowed]
    visible_apps = sorted(app for app in visible_apps
                          if app in MENU_APPS and MENU_APPS[app][0] in allowed)
    return {"name": account.pw_name, "roles": roles, "sudoGroup": sudo,
            "permissions": sorted(allowed), "visibleApps": visible_apps}


def permitted(permission):
    return not debian_session() or permission in current_access()["permissions"]
