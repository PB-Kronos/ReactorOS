#!/usr/bin/python3
"""Add ReactorOS per-user app filtering to its private GNOME Apps Menu copy."""
from pathlib import Path
import json
import sys

extension = Path(sys.argv[1])
source = extension.read_text(encoding="utf-8")
source = source.replace("text: _('Apps')", "text: _('Start')", 1)
metadata_path = extension.parent / "metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
metadata["uuid"] = "reactoros-apps-menu@reactoros.local"
metadata["name"] = "ReactorOS Start Menu"
metadata["description"] = "Per-user ReactorOS application menu"
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
marker = "if (app.get_app_info().should_show())"
replacement = "if (app.get_app_info().should_show() && reactorosAppIsAllowed(id))"
if replacement not in source:
    if marker not in source:
        raise SystemExit(f"Unsupported Apps Menu source: missing {marker!r}")
    source = source.replace(marker, replacement, 1)

helper_marker = "function reactorosAppIsAllowed(id)"
if helper_marker not in source:
    helper = """
// ReactorOS provides one explicit app allowlist for this kiosk session.
const reactorosAllowedAppIds = (() => {
    const glib = typeof GLib !== 'undefined' ? GLib : imports.gi.GLib;
    const path = glib.getenv('REACTOROS_APP_ALLOWLIST');
    if (!path)
        return null;
    try {
        const [ok, contents] = glib.file_get_contents(path);
        return ok ? new Set(new TextDecoder().decode(contents).split(/\\r?\\n/).filter(Boolean)) : new Set();
    } catch (e) {
        logError(e, 'Could not read ReactorOS app allowlist');
        return new Set();
    }
})();

function reactorosAppIsAllowed(id) {
    return reactorosAllowedAppIds === null || reactorosAllowedAppIds.has(id);
}

"""
    class_marker = "class ApplicationMenuItem"
    if class_marker not in source:
        raise SystemExit(f"Unsupported Apps Menu source: missing {class_marker!r}")
    source = source.replace(class_marker, helper + class_marker, 1)

# Start on the complete allowed app list, not the Favorites-only view. The
# latter made apps appear to vanish after users pinned another app to the dash.
favorites_view = "this._displayButtons(this._listApplications(null));"
all_apps_view = """const allApps = new Map();
        for (const categoryApps of Object.values(this.applicationsByCategory)) {
            for (const app of categoryApps) {
                if (app instanceof Shell.App)
                    allApps.set(app.get_id(), app);
            }
        }
        this._displayButtons([...allApps.values()]);"""
if all_apps_view not in source:
    if favorites_view not in source:
        raise SystemExit("Unsupported Apps Menu source: cannot find initial Favorites app list")
    source = source.replace(favorites_view, all_apps_view, 1)
extension.write_text(source, encoding="utf-8")
