#!/usr/bin/python3
"""One native settings hub for ReactorOS device, account and update controls."""
import json
import os
import subprocess
import urllib.request

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, Gtk

BASE = "http://127.0.0.1:18765"
TOKEN = os.environ.get("REACTOROS_TERMINAL_TOKEN", "")


def get_operator():
    with urllib.request.urlopen(BASE + "/api/operator", timeout=3) as response:
        return json.loads(response.read())


def launch(app):
    data = json.dumps({"app": app}).encode()
    request = urllib.request.Request(BASE + "/api/desktop/launch", data=data, method="POST", headers={
        "Content-Type": "application/json", "Origin": BASE,
        "X-ReactorOS-Session": TOKEN,
    })
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.loads(response.read())


class Settings(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.reactoros.Settings")
        self.operator = get_operator()
        self.permissions = set(self.operator.get("permissions", []))
        self._install_theme()

    def _install_theme(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
          window, notebook, notebook > header { background: #c0c0c0; color: #000; }
          headerbar { background: #000080; color: #fff; border: 2px outset #fff;
            border-radius: 0; min-height: 30px; }
          headerbar label { color: #fff; font-weight: bold; }
          button { color: #000; background: #c0c0c0; border: 2px outset #fff;
            border-radius: 0; }
          button:active { border-style: inset; }
          notebook > header tab { background: #c0c0c0; border: 2px outset #fff;
            border-radius: 0; padding: 5px 10px; }
          notebook > header tab:checked { border-style: inset; }
          separator { background: #808080; }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        window = Gtk.ApplicationWindow(application=self)
        window.set_title("ReactorOS Settings")
        window.set_default_size(720, 650)
        header = Gtk.HeaderBar(title="Settings")
        header.set_show_close_button(True)
        window.set_titlebar(header)
        notebook = Gtk.Notebook()
        notebook.set_border_width(10)
        window.add(notebook)

        device_controls = []
        for permission, title, detail, page in [
            ("app:audio-settings", "Sound", "Audio output, input, volume and applications", "sound"),
            ("app:network", "Network", "Wi-Fi and wired connections", "network"),
            ("app:display-settings", "Displays", "Arrange monitors and set resolutions", "display"),
        ]:
            if permission in self.permissions:
                device_controls.append((title, detail, lambda app=permission.split(":", 1)[1]: self._launch(app)))
        if "app:audio-settings" in self.permissions:
            device_controls.append(("System Sound Settings", "Open GNOME's full audio controls",
                                   lambda: self._open_settings("sound")))
            device_controls.append(("Restart audio services", "Restart this account's PipeWire services",
                                   self._restart_audio))
        device_controls.append(("More system settings", "Open GNOME Control Center",
                                lambda: self._open_settings("")))
        self._add_tab(notebook, "Devices", device_controls)
        account_controls = []
        if "users:manage" in self.permissions:
            account_controls.append(("User Management", "Accounts, groups and ReactorOS roles",
                                     lambda: self._launch("users")))
        if "app:disk-management" in self.permissions:
            account_controls.append(("Disk Management", "Inspect and manage disks and partitions",
                                     lambda: self._launch("disk-management")))
        self._add_tab(notebook, "Accounts & Storage", account_controls or [
            ("No available controls", "Your account has no user or disk management permission.", lambda: None),
        ])

        update_controls = []
        if self.operator.get("sudoGroup"):
            update_controls.append(("Install latest update", "Download and apply the latest signed system update",
                                    lambda: self._launch("update")))
        update_controls.append(("Check for updates", "Open the ReactorOS release page in the browser",
                                lambda: subprocess.Popen(["firefox-esr", "--new-window",
                                    "https://github.com/PB-Kronos/ReactorOS/releases/latest"],
                                    start_new_session=True)))
        self._add_tab(notebook, "Software", update_controls)
        window.show_all()

    def _add_tab(self, notebook, name, controls):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        for title, detail, callback in controls:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            description = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            label = Gtk.Label(label=title, xalign=0)
            label.get_style_context().add_class("title-4")
            text = Gtk.Label(label=detail, xalign=0)
            description.pack_start(label, False, False, 0)
            description.pack_start(text, False, False, 0)
            button = Gtk.Button(label="Open")
            button.connect("clicked", lambda _button, action=callback: self._safe(action))
            row.pack_start(description, True, True, 0)
            row.pack_end(button, False, False, 0)
            box.pack_start(row, False, False, 5)
            box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        notebook.append_page(box, Gtk.Label(label=name))

    def _open_settings(self, page):
        command = ["gnome-control-center"] + ([page] if page else [])
        subprocess.Popen(command, start_new_session=True)

    def _launch(self, app):
        launch(app)

    def _restart_audio(self):
        data = json.dumps({}).encode()
        request = urllib.request.Request(BASE + "/api/desktop/audio/restart", data=data, method="POST", headers={
            "Content-Type": "application/json", "Origin": BASE,
            "X-ReactorOS-Session": TOKEN,
        })
        with urllib.request.urlopen(request, timeout=15):
            pass

    def _safe(self, callback):
        try:
            callback()
        except Exception as error:
            dialog = Gtk.MessageDialog(transient_for=None, modal=True,
                message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                text="Could not open setting")
            dialog.format_secondary_text(str(error))
            dialog.run()
            dialog.destroy()


if __name__ == "__main__":
    try:
        raise SystemExit(Settings().run([]))
    except Exception as error:
        print("ReactorOS Settings:", error)
        raise SystemExit(1)
