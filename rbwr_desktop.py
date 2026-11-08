"""Desktop host for the local RBWR control room."""
import sys
import argparse
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".desktop-runtime"))
import webview
from workstation_programs import PROGRAMS

ORIGIN = "http://127.0.0.1:18765"
TITLES = {route: title for title, route in PROGRAMS.values()}
windows = {}


class StationWindows:
    def open_station(self, url):
        destination = urlsplit(url)
        if (destination.scheme, destination.netloc) != ("http", "127.0.0.1:18765"):
            return False
        if destination.path not in TITLES:
            return False
        launch(url)
        return True


def open_window(title, url):
    window = webview.create_window(title, url, js_api=StationWindows(),
                                   width=1320, height=900, min_size=(800, 550))
    window.events.loaded += lambda: window.evaluate_js("""
        window.open = (url) => {
            const target = new URL(url, location.href);
            if (target.origin !== location.origin) return null;
            window.pywebview.api.open_station(target.href);
            return { focus() {} };
        };
    """)
    return window


def launch(url):
    destination = urlsplit(url)
    key = url if "window=panel" in destination.query else destination.path
    if key in windows:
        window = windows[key]
        window.restore()
        if key == "/manual" and destination.query:
            window.load_url(url)
        return
    window = open_window("ReactorOS - " + TITLES[destination.path], url)
    windows[key] = window
    window.events.closed += lambda: windows.pop(key, None)


def listen():
    for line in sys.stdin:
        program = line.strip()
        if program == "cli":
            launch(ORIGIN + "/mainframe")
        elif program in PROGRAMS:
            launch(ORIGIN + PROGRAMS[program][1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("program", nargs="?", default="reactor", choices=PROGRAMS)
    parser.add_argument("--cli", action="store_true", help="Open the standalone command console")
    parser.add_argument("--launcher", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    launch(ORIGIN + ("/mainframe" if args.cli else PROGRAMS[args.program][1]))
    webview.start(listen if args.launcher else None, gui="edgechromium", private_mode=False,
                  storage_path=str(ROOT / ".rbwr-profile"))
