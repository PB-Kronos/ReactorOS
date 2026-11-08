"""ReactorOS desktop prototype and local RBWR launcher."""
import argparse
import subprocess
import sys
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox
from local_server import LocalServer
from workstation_programs import PROGRAMS

TEAL = "#008080"
GREY = "#c0c0c0"
NAVY = "#000080"
FONT = "MS Sans Serif"


class ReactorOS(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ReactorOS")
        self.geometry("1100x720")
        self.minsize(720, 480)
        self.configure(bg=TEAL)
        self.local_server = None
        self.rbwr_process = None
        self.start_menu = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.desktop()

    def desktop(self):
        desktop = tk.Frame(self, bg=TEAL)
        desktop.pack(fill="both", expand=True)
        tk.Button(desktop, text="🖥\nRBWR Unit 2", command=self.open_rbwr,
                  bg=TEAL, fg="white", activebackground=NAVY,
                  activeforeground="white", relief="flat", bd=0,
                  font=(FONT, 10), width=14, pady=8).place(x=20, y=22)
        tk.Label(desktop, text="ReactorOS", bg=TEAL, fg="#a9d6d2",
                 font=(FONT, 26, "bold")).place(relx=.5, rely=.46, anchor="center")
        taskbar = tk.Frame(self, bg=GREY, bd=2, relief="raised", height=36)
        taskbar.pack(side="bottom", fill="x")
        taskbar.pack_propagate(False)
        tk.Button(taskbar, text="■  Start", font=(FONT, 10, "bold"), bg=GREY,
                  relief="raised", bd=2, command=self.toggle_start).pack(side="left", padx=2, pady=2)
        self.task_status = tk.Label(taskbar, text="ReactorOS Desktop", bg=GREY,
                                    anchor="w", relief="sunken", bd=1, width=25, font=(FONT, 9))
        self.task_status.pack(side="left", padx=4, pady=3, fill="y")
        self.clock = tk.Label(taskbar, bg=GREY, relief="sunken", bd=1, width=10, font=(FONT, 9))
        self.clock.pack(side="right", padx=3, pady=3, fill="y")
        self.update_clock()

    def update_clock(self):
        self.clock.config(text=time.strftime("%H:%M"))
        self.after(1000, self.update_clock)

    def toggle_start(self):
        if self.start_menu is not None:
            self.start_menu.destroy()
            self.start_menu = None
            return
        self.start_menu = tk.Frame(self, bg=GREY, bd=2, relief="raised")
        self.start_menu.place(x=2, rely=1.0, y=-37, anchor="sw")
        tk.Label(self.start_menu, text="ReactorOS", bg=NAVY, fg="white",
                 font=(FONT, 12, "bold"), width=13, height=7).pack(side="left", fill="y")
        items = tk.Frame(self.start_menu, bg=GREY)
        items.pack(side="left", fill="both", expand=True)
        entries = [(title, lambda key=key: self.open_rbwr(key)) for key, (title, _) in PROGRAMS.items()]
        entries += [("RBWR Command Console", lambda: self.open_rbwr("cli")),
                    ("About ReactorOS", self.about), ("Shut Down...", self.on_close)]
        for title, action in entries:
            tk.Button(items, text=title, anchor="w", width=27, bg=GREY,
                      relief="flat", font=(FONT, 10), padx=10, pady=7, command=action).pack(fill="x")

    def about(self):
        messagebox.showinfo("About ReactorOS", "ReactorOS desktop\n\nRBWR runs in a dedicated local control-room window.")

    def open_rbwr(self, program="reactor"):
        if self.start_menu is not None:
            self.start_menu.destroy()
            self.start_menu = None
        try:
            if self.rbwr_process and self.rbwr_process.poll() is None:
                try:
                    self.rbwr_process.stdin.write(program + "\n")
                    self.rbwr_process.stdin.flush()
                    return
                except BrokenPipeError:
                    self.rbwr_process.wait(timeout=2)
            root = Path(__file__).resolve().parent
            if not (root / ".desktop-runtime" / "webview").is_dir():
                raise RuntimeError("Desktop runtime missing. Run Setup-RBWR.cmd first.")
            if self.local_server is None:
                self.local_server = LocalServer()
            self.local_server.record(f"Workstation program opened: {program}")
            args = ["--cli"] if program == "cli" else [program]
            with (root / "rbwr-desktop.log").open("w", encoding="utf-8") as log:
                self.rbwr_process = subprocess.Popen(
                    [sys.executable, str(root / "rbwr_desktop.py"), "--launcher", *args],
                    cwd=root, stdin=subprocess.PIPE, text=True, stdout=log, stderr=log)
            self.task_status.config(text="RBWR Programs")
            self.after(1000, self.watch_rbwr)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            messagebox.showerror("Could not start RBWR Unit 2", str(exc), parent=self)

    def watch_rbwr(self):
        result = self.rbwr_process.poll()
        if result is None:
            self.after(1000, self.watch_rbwr)
            return
        self.task_status.config(text="ReactorOS Desktop")
        if result:
            messagebox.showerror("RBWR Unit 2", "The program stopped unexpectedly. See rbwr-desktop.log.", parent=self)

    def on_close(self):
        if messagebox.askokcancel("Shut Down ReactorOS", "Shut down ReactorOS and its local server?", parent=self):
            if self.rbwr_process and self.rbwr_process.poll() is None:
                self.rbwr_process.terminate()
                self.rbwr_process.wait(timeout=5)
            if self.local_server:
                self.local_server.close()
            self.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true", help="Start RBWR in command-console mode")
    args = parser.parse_args()
    desktop = ReactorOS()
    if args.cli:
        desktop.after_idle(lambda: desktop.open_rbwr("cli"))
    desktop.mainloop()
