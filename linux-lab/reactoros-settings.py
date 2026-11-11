#!/usr/bin/python3
"""Native Tk settings hub for ReactorOS workstation controls."""
import json
import os
import subprocess
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.request

BASE = "http://127.0.0.1:18765"
TOKEN = os.environ.get("REACTOROS_TERMINAL_TOKEN", "")
BG = "#c0c0c0"
BLUE = "#000080"


def state_log(message=None, exception=None):
    state = os.environ.get("REACTOROS_DATA_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "reactoros")
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "settings-launch.log"), "a", encoding="utf-8") as stream:
        if message:
            stream.write(message + "\n")
        if exception:
            stream.write("".join(traceback.format_exception(exception)) + "\n")


def request_json(path, payload=None, timeout=8):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers.update({
            "Content-Type": "application/json",
            "Origin": BASE,
            "X-ReactorOS-Session": TOKEN,
        })
    request = urllib.request.Request(BASE + path, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def launch(app):
    return request_json("/api/desktop/launch", {"app": app}, timeout=10)


class Settings:
    def __init__(self, root):
        self.root = root
        self.operator = request_json("/api/operator", timeout=4)
        self.permissions = set(self.operator.get("permissions", []))
        self._style()
        self._build()

    def _style(self):
        self.root.title("ReactorOS Settings")
        self.root.geometry("760x590")
        self.root.minsize(600, 430)
        self.root.configure(bg=BG, padx=10, pady=10)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground="black")
        style.configure("TNotebook", background=BG, borderwidth=2)
        style.configure("TNotebook.Tab", background=BG, padding=(12, 6), relief="raised")
        style.map("TNotebook.Tab", background=[("selected", BG)])
        style.configure("Treeview", background="white", fieldbackground="white")

    def _build(self):
        heading = tk.Frame(self.root, bg=BLUE, bd=2, relief="raised")
        heading.pack(fill="x", pady=(0, 10))
        tk.Label(heading, text="ReactorOS Settings", bg=BLUE, fg="white",
                 font=("TkDefaultFont", 13, "bold"), anchor="w", padx=8, pady=5).pack(fill="x")
        tk.Label(self.root, text=f"Signed in as {self.operator.get('name', 'unknown')}",
                 bg=BG, anchor="w").pack(fill="x", pady=(0, 8))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        devices = self._tab(notebook, "Devices")
        accounts = self._tab(notebook, "Accounts & Storage")
        software = self._tab(notebook, "Software")

        self._section(devices, "Sound", "Configure audio devices and volume.", "audio-settings")
        self._section(devices, "Network", "Manage Wi-Fi and wired connections.", "network")
        self._section(devices, "Displays", "Arrange monitors and change resolution.", "display-settings")
        self._action(devices, "More system settings", "Open GNOME Control Center",
                     lambda: self._open_control_center())

        if "users:manage" in self.permissions:
            self._action(accounts, "User Management", "Manage Debian accounts and ReactorOS roles.",
                         lambda: self._launch("users"))
            self._action(accounts, "Start Menu Editor", "Choose which applications each account can see and run.",
                         lambda: self._launch("menu-editor"))
        if "app:disk-management" in self.permissions:
            self._section(accounts, "Disk Management", "Inspect disks and partitions.", "disk-management")
        if not accounts.winfo_children():
            self._action(accounts, "No available controls",
                         "This account has no account or storage administration permission.", lambda: None)

        if self.operator.get("sudoGroup"):
            self._action(software, "Install latest update", "Install the latest signed ReactorOS update.",
                         lambda: self._launch("update"))
        self._action(software, "Check for updates", "Open the ReactorOS releases page.",
                     lambda: subprocess.Popen([
                         "firefox-esr", "--new-window",
                         "https://github.com/PB-Kronos/ReactorOS/releases/latest"],
                         start_new_session=True))

        tk.Button(self.root, text="Close", command=self.root.destroy, bg=BG,
                  relief="raised", bd=2, padx=16).pack(anchor="e", pady=(9, 0))

    @staticmethod
    def _tab(notebook, title):
        frame = tk.Frame(notebook, bg=BG, padx=12, pady=12)
        notebook.add(frame, text=title)
        return frame

    def _section(self, parent, title, detail, app):
        if f"app:{app}" not in self.permissions:
            return
        self._action(parent, title, detail, lambda: self._launch(app))

    def _action(self, parent, title, detail, callback):
        row = tk.Frame(parent, bg=BG, bd=1, relief="ridge", padx=10, pady=9)
        row.pack(fill="x", pady=(0, 8))
        text = tk.Frame(row, bg=BG)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=BG, font=("TkDefaultFont", 10, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(text, text=detail, bg=BG, anchor="w", justify="left", wraplength=470
                 ).pack(fill="x", pady=(3, 0))
        tk.Button(row, text="Open", command=lambda: self._safe(callback), bg=BG,
                  relief="raised", bd=2, padx=12).pack(side="right", padx=(10, 0))

    def _launch(self, app):
        launch(app)

    def _open_control_center(self):
        subprocess.Popen(["gnome-control-center"], start_new_session=True)

    def _safe(self, callback):
        try:
            callback()
        except Exception as error:
            state_log(exception=error)
            messagebox.showerror("ReactorOS Settings", str(error), parent=self.root)


def main():
    try:
        root = tk.Tk()
        Settings(root)
        state_log("Settings window constructed")
        root.mainloop()
    except Exception as error:
        state_log(exception=error)
        try:
            messagebox.showerror("ReactorOS Settings could not start", str(error))
        except tk.TclError:
            print(f"ReactorOS Settings could not start: {error}", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
