#!/usr/bin/python3
"""Add ReactorOS per-user app filtering to its private GNOME Apps Menu copy."""
from pathlib import Path
import sys

extension = Path(sys.argv[1])
source = extension.read_text(encoding="utf-8")
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
extension.write_text(source, encoding="utf-8")
