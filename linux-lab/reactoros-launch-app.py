#!/usr/bin/python3
"""Permission-checked launcher for native utilities in the ReactorOS menu."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:18765"


def main():
    if len(sys.argv) != 2:
        return 2
    payload = json.dumps({"app": sys.argv[1]}).encode()
    request = Request(BASE + "/api/desktop/launch", data=payload, method="POST", headers={
        "Content-Type": "application/json", "Origin": BASE,
        "X-ReactorOS-Session": os.environ.get("REACTOROS_TERMINAL_TOKEN", ""),
    })
    try:
        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read())
        return 0 if result.get("started") else 1
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        detail = "ReactorOS could not open this program."
        if isinstance(error, HTTPError):
            try:
                detail = json.loads(error.read()).get("error", detail)
            except (ValueError, OSError):
                pass
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                       buttons=Gtk.ButtonsType.CLOSE,
                                       text="ReactorOS")
            dialog.format_secondary_text(detail)
            dialog.run()
            dialog.destroy()
        except ImportError:
            print(detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
