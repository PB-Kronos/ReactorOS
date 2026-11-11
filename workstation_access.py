"""Debian account to ReactorOS permission mapping."""
import json
import os
import configparser
from pathlib import Path

from workstation_programs import PROGRAMS

ROLE_FILE = Path("/etc/reactoros/roles.json")
APP_PERMISSIONS = {f"app:{name}" for name in PROGRAMS} | {
    "app:settings",
    "app:files", "app:editor", "app:images", "app:browser", "app:disk-management",
    "app:network", "app:audio-settings", "app:display-settings",
    "app:live-variables", "app:events",
    "app:update",
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
    "menu-editor": ("users:manage", "Start Menu Editor", "reactoros-menu-editor.desktop"),
    "settings": ("app:settings", "ReactorOS Settings", "reactoros-settings.desktop"),
    "update": ("app:update", "ReactorOS Update", "reactoros-update.desktop"),
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


def desktop_id(path, applications_dir):
    """Return the freedesktop menu ID for an applications-directory entry."""
    return "-".join(path.relative_to(applications_dir).parts)


def installed_menu_apps(user_home=None):
    """Discover installable desktop entries for the per-user Start menu editor."""
    roots = []
    if user_home:
        roots.append(Path(user_home) / ".local/share/applications")
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    roots.append(data_home / "applications")
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    roots.extend(Path(item) / "applications" for item in data_dirs.split(":") if item)
    roots.extend((Path("/opt/reactoros/share/applications"),
                  Path("/usr/local/share/applications"), Path("/usr/share/applications")))

    core_ids = {desktop for _permission, _label, desktop in MENU_APPS.values()}
    found = {}
    seen_roots = set()
    for applications_dir in roots:
        try:
            applications_dir = applications_dir.resolve()
        except OSError:
            continue
        if applications_dir in seen_roots or not applications_dir.is_dir():
            continue
        seen_roots.add(applications_dir)
        for path in sorted(applications_dir.rglob("*.desktop")):
            identifier = desktop_id(path, applications_dir)
            if identifier in found or identifier in core_ids:
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                with path.open(encoding="utf-8", errors="replace") as stream:
                    parser.read_file(stream)
                entry = parser["Desktop Entry"]
                if (entry.get("Type", "Application") != "Application" or
                        entry.getboolean("Hidden", fallback=False) or
                        entry.getboolean("NoDisplay", fallback=False)):
                    continue
                label = entry.get("Name", "").strip()
            except (OSError, KeyError, configparser.Error, ValueError):
                continue
            if label:
                found[identifier] = (label, path)
    return found


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
    if sudo:
        # Sudo accounts can administer ReactorOS account and menu policy even
        # when their explicitly selected ReactorOS role is more restrictive.
        permissions.update({"users:manage", "terminal:execute", "app:update"})
    else:
        permissions.difference_update({"users:manage", "terminal:execute"})
    allowed = permissions & PERMISSIONS
    configured_apps = policy.get("visible_apps", {}).get(account.pw_name)
    if configured_apps is None:
        configured_apps = [app for app, (permission, _label, _desktop) in MENU_APPS.items()
                           if permission in allowed]
    else:
        # Once an account has an explicit app allowlist, unchecked apps lose
        # their app permission even if the assigned role would normally grant it.
        allowed.difference_update(APP_PERMISSIONS)
    visible_apps = set()
    for app in configured_apps:
        if app in MENU_APPS:
            permission = MENU_APPS[app][0]
            # Checking a ReactorOS application in the editor grants both its
            # launch permission and its Start menu visibility.
            if permission.startswith("app:"):
                allowed.add(permission)
                visible_apps.add(app)
            elif permission in allowed:
                visible_apps.add(app)
    visible_apps.update(
        app for app in configured_apps
        if (isinstance(app, str) and app.startswith("desktop:") and
            app.endswith(".desktop") and "/" not in app[8:] and "\\" not in app[8:])
    )
    # Keep the policy editor available to administrators so they can recover
    # from accidentally removing Settings or their own app launchers.
    if "users:manage" in allowed:
        visible_apps.add("menu-editor")
    allowed.intersection_update(PERMISSIONS)
    visible_apps = sorted(visible_apps)
    return {"name": account.pw_name, "roles": roles, "sudoGroup": sudo,
            "permissions": sorted(allowed), "visibleApps": visible_apps}


def permitted(permission):
    return not debian_session() or permission in current_access()["permissions"]
