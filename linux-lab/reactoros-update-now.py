#!/usr/bin/python3
"""Standalone update chooser; signs out ReactorOS before installing anything."""
import json
import os
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:18765"
TOKEN = os.environ.get("REACTOROS_TERMINAL_TOKEN", "")
BG = "#c0c0c0"
BLUE = "#000080"


def operator_info():
    request = Request(BASE + "/api/operator", headers={
        "X-ReactorOS-Session": TOKEN,
        "Origin": BASE,
    })
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def installed_package():
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${db:Status-Status}", "reactoros-desktop"],
            capture_output=True, text=True, timeout=4, check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "installed"
    except (OSError, subprocess.TimeoutExpired):
        return False


class UpdateManager:
    def __init__(self, root):
        self.root = root
        self.operator = operator_info()
        self.package_ready = (
            installed_package()
            and Path("/etc/apt/sources.list.d/reactoros.sources").is_file()
            and Path("/usr/share/keyrings/reactoros-archive-keyring.gpg").is_file()
        )
        self.legacy_ready = all(Path(path).is_file() for path in (
            "/etc/reactoros/update-repo", "/etc/reactoros/update-public.pem",
        )) and any(Path(path).is_file() for path in (
            "/usr/lib/reactoros/legacy-updater", "/usr/local/sbin/reactoros-update",
        ))
        self.available = []
        if self.package_ready:
            self.available.append("package")
        if self.legacy_ready:
            self.available.append("legacy")
        self.method = tk.StringVar(value="package" if self.package_ready else
                                   ("legacy" if self.legacy_ready else ""))
        self._style()
        self._build()

    def _style(self):
        self.root.title("ReactorOS Update")
        self.root.geometry("540x360")
        self.root.resizable(False, False)
        self.root.configure(bg=BG, padx=12, pady=12)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground="black")
        style.configure("TRadiobutton", background=BG, foreground="black")

    def _build(self):
        heading = tk.Frame(self.root, bg=BLUE, bd=2, relief="raised")
        heading.pack(fill="x", pady=(0, 12))
        tk.Label(heading, text="ReactorOS Update", bg=BLUE, fg="white",
                 font=("TkDefaultFont", 13, "bold"), anchor="w", padx=8, pady=5).pack(fill="x")
        if (not self.operator.get("sudoGroup") or
                "app:update" not in self.operator.get("permissions", [])):
            self._message("Updates require sudo membership and the ReactorOS update permission.")
            self._buttons(enabled=False)
            return

        tk.Label(self.root, text="Choose how ReactorOS should update.",
                 bg=BG, anchor="w").pack(fill="x", pady=(0, 10))
        if self.package_ready and self.legacy_ready:
            tk.Radiobutton(self.root, text="Debian APT packages (recommended)",
                           variable=self.method, value="package", bg=BG,
                           activebackground=BG, anchor="w").pack(fill="x", pady=3)
            tk.Label(self.root, text="Updates ReactorOS with apt-get update and apt-get install.",
                     bg=BG, anchor="w", wraplength=500).pack(fill="x", padx=(24, 0), pady=(0, 8))
            tk.Radiobutton(self.root, text="Signed legacy updater (recovery)",
                           variable=self.method, value="legacy", bg=BG,
                           activebackground=BG, anchor="w").pack(fill="x", pady=3)
            tk.Label(self.root, text="Uses the previous signed release archive updater.",
                     bg=BG, anchor="w", wraplength=500).pack(fill="x", padx=(24, 0), pady=(0, 8))
        elif self.package_ready:
            self._message("APT package updates are ready. Debian and ReactorOS package indexes will be refreshed.")
        elif self.legacy_ready:
            self.method.set("legacy")
            self._message("The signed legacy updater is available. Install the ReactorOS Debian package to switch to APT updates.")
        else:
            self._message("No updater is configured. Install the ReactorOS Debian package, or configure the signed legacy updater.")

        self._buttons(enabled=bool(self.available))

    def _message(self, message):
        tk.Label(self.root, text=message, bg=BG, anchor="w", justify="left",
                 wraplength=500).pack(fill="x", pady=(4, 12))

    def _buttons(self, enabled):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(side="bottom", fill="x", pady=(12, 0))
        tk.Button(bar, text="Sign out and update", command=self.start,
                  state=(tk.NORMAL if enabled else tk.DISABLED),
                  relief="raised", bd=2, padx=10).pack(side="right", padx=(6, 0))
        tk.Button(bar, text="Close", command=self.root.destroy,
                  relief="raised", bd=2, padx=14).pack(side="right")

    def start(self):
        session_id = os.environ.get("REACTOROS_SESSION_ID", "")
        method = self.method.get()
        if not session_id.isdecimal() or method not in self.available:
            messagebox.showerror("ReactorOS Update", "The desktop session or selected update method is unavailable.",
                                 parent=self.root)
            return
        if not messagebox.askyesno(
                "Sign out and update",
                "ReactorOS will sign out this desktop session, install the update, then return to the sign-in screen. Continue?",
                parent=self.root):
            return
        helper = "/usr/local/sbin/reactoros-update-from-session"
        command = ["xterm", "-hold", "-T", "ReactorOS Update", "-e", "sudo",
                   "/usr/bin/systemd-run", "--unit=reactoros-kiosk-update", "--collect",
                   helper, session_id, method]
        try:
            subprocess.Popen(command, start_new_session=True)
        except OSError as error:
            messagebox.showerror("ReactorOS Update", f"Could not start the updater: {error}",
                                 parent=self.root)
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        UpdateManager(root)
    except Exception as error:
        root.withdraw()
        messagebox.showerror("ReactorOS Update", str(error), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
