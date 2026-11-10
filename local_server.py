"""Loopback-only host for the imported RBWR application and local event log."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import hmac
import importlib.util
import math
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from workstation_programs import PROGRAMS
from database_service import DB
from urllib.parse import urlsplit, parse_qs
from workstation_access import current_access, debian_session, permitted

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "rbwr" / "dist"
DESKTOP_APPS = {
    "files": ["thunar"],
    "editor": ["mousepad"],
    "images": ["ristretto"],
    "browser": ["firefox-esr", "--no-remote"],
    "disk-management": ["/usr/sbin/gparted"],
    "network": ["gnome-control-center", "wifi"],
    "audio-settings": ["pavucontrol"],
    # Mutter owns display layout in the native GNOME session (including Wayland).
    "display-settings": ["gnome-control-center", "display"],
}
UPDATER = Path("/usr/local/sbin/reactoros-update")
UPDATE_RESULT = Path("/run/reactoros-update-result")


def updater_configured():
    return UPDATER.is_file() and all(
        (Path("/etc/reactoros") / name).is_file()
        for name in ("update-repo", "update-public.pem")
    )

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def kiosk_request(self, origin, require_origin=True):
        token = os.environ.get("REACTOROS_TERMINAL_TOKEN", "")
        supplied = self.headers.get("X-ReactorOS-Session", "")
        allowed = (origin,) if require_origin else (None, origin)
        return (debian_session() and self.headers.get("Host") == origin.removeprefix("http://")
                and self.headers.get("Origin") in allowed
                and bool(token) and hmac.compare_digest(token.encode(), supplied.encode()))

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != origin.removeprefix("http://") or self.headers.get("Origin") not in (None, origin):
            return self.send_json({"error": "Local clients only"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            limit = 262144 if self.path == "/api/plant/sync" else 4096
            if not 0 < size <= limit or self.headers.get_content_type() != "application/json":
                raise ValueError
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            return self.send_json({"error": "Invalid JSON request"}, 400)
        if self.path == "/api/database/variables":
            if not self.kiosk_request(origin) or not permitted("app:live-variables") or not permitted("database:edit"):
                return self.send_json({"error": "Permission denied"}, 403)
            with self.server.plant_lock:
                if data.get("operation") == "scenario" and time.monotonic() - self.server.plant_seen > 5:
                    return self.send_json({"error": "Open the RBWR control room before loading a scenario"}, 503)
                try:
                    return self.send_json(self.server.database_request({**data, "action": "variable-edit"}), 202)
                except ValueError as exc:
                    return self.send_json({"error": str(exc)}, 400)
                except (RuntimeError, OSError):
                    return self.send_json({"error": "Database service unavailable"}, 503)
        if self.path == "/api/desktop/sign-out":
            if not self.kiosk_request(origin):
                return self.send_json({"error": "Permission denied"}, 403)
            try:
                pid = int(os.environ.get("REACTOROS_KIOSK_PID", "0"))
                if pid <= 1 or pid != os.getppid():
                    raise ValueError
                os.kill(pid, signal.SIGUSR1)
            except (ValueError, OSError):
                return self.send_json({"error": "Kiosk session unavailable"}, 503)
            return self.send_json({"signingOut": True}, 202)
        if self.path == "/api/desktop/terminal":
            if not self.kiosk_request(origin) or not permitted("terminal:execute"):
                return self.send_json({"error": "Debian terminal access denied"}, 403)
            command = data.get("command")
            if not isinstance(command, str) or not command.strip() or "\0" in command:
                return self.send_json({"error": "Enter a Debian command"}, 400)
            try:
                subprocess.Popen(
                    ["xterm", "-hold", "-T", "ReactorOS Debian Terminal", "-e", "/bin/sh", "-c", command],
                    cwd=Path.home(), start_new_session=True,
                )
            except FileNotFoundError:
                return self.send_json({"error": "Debian terminal needs xterm. Install it with sudo apt-get install xterm."}, 503)
            except OSError as exc:
                return self.send_json({"error": str(exc)}, 503)
            return self.send_json({"started": "terminal"}, 202)
        if self.path == "/api/desktop/audio/restart":
            if not self.kiosk_request(origin) or not permitted("app:audio-settings"):
                return self.send_json({"error": "Permission denied"}, 403)
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "restart", "pipewire.service",
                     "pipewire-pulse.service", "wireplumber.service"],
                    capture_output=True, text=True, timeout=12,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return self.send_json({"error": f"Could not restart audio services: {exc}"}, 503)
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                return self.send_json({"error": detail or "PipeWire restart failed."}, 503)
            return self.send_json({"restarted": True}, 200)
        if self.path == "/api/desktop/launch" and debian_session():
            app = data.get("app")
            if not isinstance(app, str) or app not in (*DESKTOP_APPS, "users", "users-cli", "menu-editor", "update"):
                return self.send_json({"error": "Unknown desktop application"}, 400)
            privileged = app in ("users", "users-cli", "menu-editor", "update")
            allowed = (current_access()["sudoGroup"] if app == "update" else
                       permitted("users:manage" if privileged else f"app:{app}"))
            if not allowed or (privileged and not self.kiosk_request(origin)):
                return self.send_json({"error": "Permission denied"}, 403)
            if app == "update":
                if not updater_configured():
                    return self.send_json({"error": "Set up the signed updater before updating."}, 409)
                session_id = os.environ.get("REACTOROS_SESSION_ID", "")
                if not session_id.isdecimal():
                    return self.send_json({
                        "error": "This login session cannot be identified for automatic sign-out. "
                                 "Switch to a text console and run the updater there."
                    }, 409)
                command = ["xterm", "-hold", "-T", "ReactorOS Update", "-e", "sudo",
                           "/usr/bin/systemd-run", "--unit=reactoros-kiosk-update", "--collect",
                           "/usr/local/sbin/reactoros-update-from-session", session_id]
            elif app == "menu-editor":
                command = ["xterm", "-T", "ReactorOS Start Menu Editor", "-e", "sudo",
                           "--preserve-env=DISPLAY,XAUTHORITY", "/usr/bin/python3",
                           str(ROOT / "reactoros-menu-editor.py")]
            elif privileged:
                command = ["xterm", "-T", "ReactorOS User Manager", "-e", "sudo",
                           "--preserve-env=DISPLAY,XAUTHORITY", "/usr/bin/python3", str(ROOT / "manage-users.py")]
                if app == "users":
                    if importlib.util.find_spec("tkinter") is None:
                        return self.send_json({"error": "Install the GUI dependency with sudo apt-get install python3-tk."}, 503)
                    command.append("--gui")
            else:
                command = DESKTOP_APPS[app].copy()
                if app == "audio-settings":
                    try:
                        start = subprocess.run(
                            ["systemctl", "--user", "start", "pipewire.socket",
                             "pipewire-pulse.socket", "pipewire.service",
                             "pipewire-pulse.service", "wireplumber.service"],
                            capture_output=True, text=True, timeout=8,
                        )
                        if start.returncode:
                            detail = (start.stderr or start.stdout).strip()
                            return self.send_json({
                                "error": "PipeWire could not start in this user session. " + detail
                            }, 503)
                        probe = subprocess.run(["pactl", "info"], capture_output=True,
                                               text=True, timeout=4)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        return self.send_json({"error": f"Audio service is not ready: {exc}"}, 503)
                    if probe.returncode:
                        detail = (probe.stderr or probe.stdout).strip()
                        return self.send_json({
                            "error": "PipeWire Pulse endpoint is not responding. " + detail
                        }, 503)
                if app == "disk-management" and not Path(command[0]).is_file():
                    return self.send_json({
                        "error": "GParted is not installed. Install the Debian package with sudo apt-get install gparted."
                    }, 503)
            if app == "browser":
                profile = DB.parent / "internet"
                profile.mkdir(exist_ok=True)
                command.extend(["--profile", str(profile), "about:blank"])
            try:
                env = os.environ.copy()
                # Apply the ReactorOS GTK theme only to apps launched by this
                # session. GNOME Control Center and the rest of GNOME keep
                # their own toolkit theme so upstream layouts remain intact.
                if app in {"files", "editor", "images", "audio-settings"}:
                    env["GTK_THEME"] = "ReactorOS95"
                subprocess.Popen(command, cwd=Path.home(), start_new_session=True, env=env)
            except OSError as exc:
                return self.send_json({"error": str(exc)}, 503)
            return self.send_json({"started": app}, 202)
        with self.server.plant_lock:
            if self.path == "/api/plant/override":
                if not permitted("app:live-variables") or not permitted("database:edit"):
                    return self.send_json({"error": "Permission denied"}, 403)
                variable, value = data.get("variable"), data.get("value")
                if variable not in ("reactor.temp", "reactor.pressure", "reactor.aprm") or type(value) not in (float, int) or not -1e6 <= value <= 1e6 or not math.isfinite(value):
                    return self.send_json({"error": "Invalid override"}, 400)
                if time.monotonic() - self.server.plant_seen > 5:
                    return self.send_json({"error": "Control room offline"}, 503)
                if len(self.server.plant_overrides) >= 32:
                    return self.send_json({"error": "Control room queue full"}, 503)
                self.server.plant_overrides.append(f"{variable} set {value:.12f}")
                return self.send_json({"queued": True}, 202)
            if self.path == "/api/plant/sync":
                if not permitted("app:reactor"):
                    return self.send_json({"error": "Permission denied"}, 403)
                previous = self.server.plant_state or {}
                record = getattr(self.server, "record_event", None)
                if record:
                    if data.get("scramPressed") and not previous.get("scramPressed"):
                        record("RBWR reported a SCRAM")
                    if bool(data.get("isRunning")) != bool(previous.get("isRunning")):
                        record("RBWR running" if data.get("isRunning") else "RBWR stopped")
                self.server.plant_state = {key: value for key, value in data.items() if key != "catalog"}
                self.server.plant_seen = time.monotonic()
                pending = self.server.plant_trip
                self.server.plant_trip = False
                overrides = self.server.plant_overrides
                self.server.plant_overrides = []
                response = {"scram": pending, "overrides": overrides}
                catalog = data.get("catalog")
                if self.kiosk_request(origin) and isinstance(catalog, dict):
                    try:
                        response["database"] = self.server.database_request({**catalog, "action": "variable-sync"})
                    except (ValueError, RuntimeError, OSError):
                        pass
                return self.send_json(response)
            if self.path == "/api/plant/command" and data == {"command": "scram"}:
                if not permitted("app:mainframe"):
                    return self.send_json({"error": "Permission denied"}, 403)
                if time.monotonic() - self.server.plant_seen > 5:
                    return self.send_json({"error": "Control room offline"}, 503)
                self.server.plant_trip = True
                return self.send_json({"queued": True}, 202)
        self.send_json({"error": "Unknown plant request"}, 404)

    def do_GET(self):
        if self.path == "/api/desktop/audio" and debian_session():
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.kiosk_request(origin, require_origin=False) or not permitted("app:audio-settings"):
                return self.send_json({"error": "Permission denied"}, 403)
            try:
                info = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=4)
                sinks = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True,
                                      text=True, timeout=4)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return self.send_json({"error": f"Audio service is unavailable: {exc}"}, 503)
            if info.returncode:
                detail = (info.stderr or info.stdout).strip()
                return self.send_json({"summary": "No PulseAudio-compatible audio server is responding. " + detail})
            fields = {}
            for line in info.stdout.splitlines():
                key, separator, value = line.partition(":")
                if separator and key.strip() in ("Server Name", "Default Sink", "Default Source"):
                    fields[key.strip()] = value.strip()
            sink_names = [line.split("\t", 2)[1] for line in sinks.stdout.splitlines() if "\t" in line]
            server = fields.get("Server Name", "Audio server connected")
            default_sink = fields.get("Default Sink", "none")
            if sink_names:
                summary = f"{server} · Default output: {default_sink} · {len(sink_names)} output device(s) detected."
            else:
                summary = f"{server} · No output devices detected; check ALSA hardware and profile selection."
            return self.send_json({"summary": summary, "sinks": sink_names, "defaultSink": default_sink})
        if self.path == "/api/desktop/update" and debian_session():
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.kiosk_request(origin, require_origin=False):
                return self.send_json({"error": "Permission denied"}, 403)
            version = ROOT / "VERSION"
            return self.send_json({
                "version": version.read_text().strip() if version.is_file() else "Live image",
                "configured": updater_configured(),
                "result": UPDATE_RESULT.read_text(errors="replace")[-3000:] if UPDATE_RESULT.is_file() else "",
            })
        if self.path == "/api/desktop/fullscreen-key":
            origin = f"http://127.0.0.1:{self.server.server_port}"
            key_file = os.environ.get("REACTOROS_FULLSCREEN_KEY")
            if not key_file or not self.kiosk_request(origin, require_origin=False):
                return self.send_json({"error": "Kiosk fullscreen key unavailable"}, 403)
            try:
                sequence = str(Path(key_file).stat().st_mtime_ns)
            except FileNotFoundError:
                sequence = "0"
            return self.send_json({"sequence": sequence})
        if self.path == "/api/desktop/start-menu-key":
            origin = f"http://127.0.0.1:{self.server.server_port}"
            key_file = os.environ.get("REACTOROS_START_MENU_KEY")
            if not key_file or not self.kiosk_request(origin, require_origin=False):
                return self.send_json({"error": "Kiosk Start key unavailable"}, 403)
            try:
                sequence = str(Path(key_file).stat().st_mtime_ns)
            except FileNotFoundError:
                sequence = "0"
            return self.send_json({"sequence": sequence})
        if self.path == "/api/database/variables":
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.kiosk_request(origin, require_origin=False) or not permitted("app:live-variables"):
                return self.send_json({"error": "Permission denied"}, 403)
            with self.server.plant_lock:
                try:
                    result = self.server.database_request({"action": "variables"})
                    result["canEdit"] = permitted("database:edit")
                    result["online"] = time.monotonic() - self.server.plant_seen <= 5
                    return self.send_json(result)
                except (RuntimeError, OSError, ValueError):
                    return self.send_json({"error": "Database service unavailable"}, 503)
        if self.path == "/api/operator" and debian_session():
            return self.send_json(current_access())
        if self.path == "/api/events":
            if not permitted("app:events"):
                return self.send_json({"error": "Permission denied"}, 403)
            try:
                with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute("SELECT id, created_at, message FROM events ORDER BY id DESC LIMIT 100")
                    return self.send_json({"events": [dict(row) for row in rows]})
            except sqlite3.Error:
                return self.send_json({"error": "Event database unavailable"}, 503)
        if self.path == "/api/plant":
            if not any(permitted(f"app:{app}") for app in ("live-variables", "reactor", "mainframe", "status-desk", "supervisor")):
                return self.send_json({"error": "Permission denied"}, 403)
            with self.server.plant_lock:
                online = time.monotonic() - self.server.plant_seen <= 5
                return self.send_json({"online": online, "state": self.server.plant_state if online else None})
        if self.path == "/api/status":
            data = json.dumps({"status": "online", "database": "sqlite", "simulator": "RBWR Unit 2"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            url = urlsplit(self.path)
            program = next((name for name, (_, route) in PROGRAMS.items() if route == url.path), None)
            if url.path == "/plant-tools.html":
                tool = parse_qs(url.query).get("tool", ["database"])[0]
                permission = "app:events" if tool == "server" else "app:live-variables"
                if not permitted(permission):
                    return self.send_json({"error": "Permission denied"}, 403)
            if program:
                if not permitted(f"app:{program}"):
                    return self.send_json({"error": "Permission denied"}, 403)
                self.path = "/index.html"
            super().do_GET()

    def log_message(self, format, *args):
        pass

class LocalServer:
    def __init__(self):
        if not (DIST / "index.html").is_file():
            raise RuntimeError("RBWR build missing; run npm run build in the rbwr folder")
        # A stable origin is required for the simulator's browser localStorage.
        self.server = ThreadingHTTPServer(("127.0.0.1", 18765), Handler)
        init_plant_bridge(self.server)
        self.server.database_request = self.database_request
        try:
            self.database = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "database_service.py")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.database_lock = threading.Lock()
            self.database_request({"action": "status"})
            self.server.record_event = self.record
        except Exception:
            self.server.server_close()
            raise
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.record("Local server started")

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def record(self, message):
        self.database_request({"action": "record", "message": message})

    def database_request(self, request):
        with self.database_lock:
            self.database.stdin.write(json.dumps(request) + "\n")
            self.database.stdin.flush()
            line = self.database.stdout.readline()
            if not line:
                raise RuntimeError("Database service stopped unexpectedly")
            result = json.loads(line)
            if not result.get("ok"):
                raise ValueError(result.get("error", "Database error"))
            return result

    def close(self):
        self.record("Local server stopped")
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.database_request({"action": "stop"})
        self.database.wait(timeout=5)
        self.database.stdin.close()
        self.database.stdout.close()


def init_plant_bridge(server):
    server.plant_lock = threading.Lock()
    server.plant_seen = float("-inf")
    server.plant_state = None
    server.plant_trip = False
    server.plant_overrides = []
