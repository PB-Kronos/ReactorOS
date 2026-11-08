"""Local database worker. JSON lines over private stdin/stdout, no network."""
import json
import os
import sqlite3
import sys
from pathlib import Path

DB = Path(os.environ.get("REACTOROS_DATA_DIR", Path(__file__).resolve().parent)) / "reactoros.sqlite3"


def main():
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, message TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
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
                elif action == "stop":
                    print(json.dumps({"ok": True}), flush=True)
                    break
                else:
                    result = {"ok": False, "error": "Unknown action"}
            except (ValueError, KeyError, sqlite3.Error) as exc:
                result = {"ok": False, "error": str(exc)}
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
