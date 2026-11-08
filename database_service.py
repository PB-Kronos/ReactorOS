"""Local database worker. JSON lines over private stdin/stdout, no network."""
import json
import math
import os
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

DB = Path(os.environ.get("REACTOROS_DATA_DIR", Path(__file__).resolve().parent)) / "reactoros.sqlite3"

MODES = {"released", "saved", "persistent"}
SCENARIOS = ("cold", "reactor-ready", "turbine-synced", "grid-load", "offsite")


class LiveVariables:
    def __init__(self, db):
        self.db = db
        self.live = {}
        self.session = None
        self.applied = set()
        self.scenarios = {}
        db.execute("""CREATE TABLE IF NOT EXISTS live_variables (
            name TEXT PRIMARY KEY, mode TEXT NOT NULL, default_mode TEXT NOT NULL,
            kind TEXT NOT NULL, bounds TEXT, value TEXT, revision TEXT
        )""")
        db.row_factory = sqlite3.Row
        self.rows = {row["name"]: dict(row) for row in db.execute("SELECT * FROM live_variables")}

    def store(self, row):
        self.db.execute("""INSERT OR REPLACE INTO live_variables
            (name, mode, default_mode, kind, bounds, value, revision)
            VALUES (:name, :mode, :default_mode, :kind, :bounds, :value, :revision)""", row)

    def view(self):
        return [
            {**row, "bounds": json.loads(row["bounds"]) if row["bounds"] else None,
             "value": (json.loads(row["value"]) if row["value"] is not None
                       and (row["mode"] == "persistent" or row["revision"] not in self.applied
                            or name not in self.live) else self.live.get(name)),
             "live": name in self.live}
            for name, row in self.rows.items()
        ]

    def sync(self, request):
        if request["session"] != self.session:
            self.session = request["session"]
            self.applied.clear()
            self.live.clear()
        acknowledged = set(request.get("ack", []))
        self.applied.update(acknowledged)
        for command_id in acknowledged:
            self.scenarios.pop(command_id, None)
        operations = []
        holds = {}
        with self.db:
            for name, entry in request["variables"].items():
                value = entry["value"]
                self.live[name] = value
                row = self.rows.get(name)
                if row is None:
                    default = entry.get("default", "released")
                    kind = entry.get("kind", "readonly")
                    row = self.rows[name] = {
                        "name": name, "mode": default, "default_mode": default, "kind": kind,
                        "bounds": json.dumps(entry["choices"] if kind == "string" else entry["bounds"])
                        if "bounds" in entry or "choices" in entry else None,
                        "value": None, "revision": None,
                    }
                    self.store(row)
                mode, stored, revision = row["mode"], row["value"], row["revision"]
                if stored is None and revision and revision not in self.applied:
                    operations.append({"id": revision, "name": name, "reset": True})
                elif mode == "persistent" and stored is not None:
                    holds[name] = json.loads(stored)
                elif stored is not None and revision and revision not in self.applied:
                    operations.append({"id": revision, "name": name, "value": json.loads(stored)})
                elif mode == "released" and stored is not None:
                    row.update(value=None, revision=None)
                    self.store(row)
                elif mode in ("saved", "persistent") and value is not None:
                    encoded = json.dumps(value)
                    if encoded != stored:
                        row.update(value=encoded, revision=revision or uuid4().hex)
                        self.applied.add(row["revision"])
                        self.store(row)
                    if mode == "persistent":
                        holds[name] = value
                elif stored is None and revision:
                    row["revision"] = None
                    self.store(row)
        # Only active revisions need to remain in the acknowledgement set.
        self.applied.intersection_update(row["revision"] for row in self.rows.values())
        return {"holds": holds, "operations": operations, "scenarios": list(self.scenarios.values())}

    def edit(self, request):
        action = request["operation"]
        if action == "scenario":
            scenario = request.get("scenario")
            if scenario not in SCENARIOS:
                raise ValueError("Unknown scenario")
            if self.scenarios:
                raise ValueError("A scenario is already waiting for the control room")
            command_id = uuid4().hex
            self.scenarios[command_id] = {"id": command_id, "name": scenario}
            return
        row = self.rows.get(request.get("name"))
        if row is None or row["kind"] == "readonly":
            raise ValueError("Unknown or read-only variable")
        name = row["name"]
        updated = dict(row)
        if action == "delete":
            updated.update(value=None, revision=uuid4().hex)
        elif action in ("set", "mode"):
            mode = request.get("mode", row["mode"])
            if mode == "default":
                mode = row["default_mode"]
            if mode not in MODES:
                raise ValueError("Choose released, saved, persistent, or default")
            if "value" in request:
                value = request["value"]
            elif mode == "released":
                value = None
            else:
                value = self.live.get(name) if row["value"] is None or row["mode"] == "saved" else json.loads(row["value"])
                if value is None and row["value"] is not None:
                    value = json.loads(row["value"])
                if value is None:
                    raise ValueError("No current value. Supply a value or open the control room.")
            if value is not None or "value" in request:
                self.validate(row, value)
            updated.update(mode=mode, value=None if value is None else json.dumps(value),
                           revision=None if value is None else uuid4().hex)
        else:
            raise ValueError("Unknown database operation")
        with self.db:
            self.store(updated)
        self.rows[name] = updated

    @staticmethod
    def validate(row, value):
        if row["kind"] == "string" and isinstance(value, str) and value in json.loads(row["bounds"]):
            return
        if row["kind"] == "boolean" and type(value) is bool:
            return
        if row["kind"] == "number" and type(value) in (int, float) and -1e9 <= value <= 1e9 and math.isfinite(value):
            if row["bounds"]:
                low, high = json.loads(row["bounds"])
                if not low <= value <= high:
                    raise ValueError(f"Value must be between {low} and {high}")
            return
        raise ValueError(f'Expected a {row["kind"]} value')


def main():
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, message TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        variables = LiveVariables(db)
        db.commit()
        for line in sys.stdin:
            try:
                request = json.loads(line)
                action = request.get("action")
                if action == "record":
                    db.execute("INSERT INTO events(message) VALUES (?)", (request["message"],))
                    db.commit()
                    result = {"ok": True}
                elif action == "status":
                    result = {"ok": True, "service": "database"}
                elif action == "variables":
                    result = {"ok": True, "variables": variables.view(), "scenarios": SCENARIOS}
                elif action == "variable-sync":
                    result = {"ok": True, **variables.sync(request)}
                elif action == "variable-edit":
                    variables.edit(request)
                    result = {"ok": True}
                elif action == "stop":
                    print(json.dumps({"ok": True}), flush=True)
                    break
                else:
                    result = {"ok": False, "error": "Unknown action"}
            except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                result = {"ok": False, "error": str(exc)}
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
