#!/usr/bin/python3
"""Native, movable ReactorOS program windows backed by WebKitGTK."""
import json
import os
import subprocess
import sys
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gio, Gdk, Gtk, WebKit2

BASE = "http://127.0.0.1:18765"
TOKEN = os.environ.get("REACTOROS_TERMINAL_TOKEN", "")
PROGRAMS = {
    "/": ("Plant Operations Terminal", "app:greeting"),
    "/reactor": ("RBWR Unit 2", "app:reactor"),
    "/status-desk": ("Status Desk", "app:status-desk"),
    "/supervisor": ("Plant Supervisor", "app:supervisor"),
    "/mainframe": ("Advanced Operator Terminal", "app:mainframe"),
    "/manual": ("Operator Manual", "app:manual"),
    "/plant-tools.html?tool=database": ("Plant Database", "app:live-variables"),
    "/plant-tools.html?tool=server": ("Server Event Log", "app:events"),
}


def canonical_route(address):
    parsed = urlsplit(address)
    path = parsed.path or "/"
    return path + ("?" + parsed.query if path == "/plant-tools.html" and parsed.query else "")


def operator_info():
    with urlopen(BASE + "/api/operator", timeout=3) as response:
        return json.loads(response.read())


class ReactorOSApps(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.reactoros.NativeApps",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.windows = []
        self.identity = operator_info()
        self.permissions = set(self.identity.get("permissions", []))
        self.web_context = WebKit2.WebContext.get_default()
        self._install_theme()

    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        route = args[1] if len(args) > 1 else "/"
        self.open_program(route)
        return 0

    def _install_theme(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
          headerbar.reactoros-titlebar { background-color: #000080; color: white;
            border: 2px solid #fff; border-bottom-color: #404040; min-height: 30px; }
          headerbar.reactoros-titlebar label { color: white; font-weight: bold; }
          headerbar.reactoros-titlebar button { color: #000; background: #c0c0c0;
            border: 2px outset #fff; border-radius: 0; min-width: 24px; min-height: 22px; }
          headerbar.reactoros-titlebar button:active { border-style: inset; }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(transient_for=None, modal=True,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE, text="ReactorOS")
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def open_program(self, address, related=None):
        route = canonical_route(address)
        descriptor = PROGRAMS.get(route)
        if descriptor is None:
            self._show_error("This ReactorOS program is not registered.")
            return None
        title, permission = descriptor
        if permission not in self.permissions:
            self._show_error("Your Debian account does not have permission to launch " + title + ".")
            return None
        window = Gtk.ApplicationWindow(application=self)
        window.set_title(title)
        window.set_default_size(1440 if route == "/reactor" else 1180,
                                900 if route == "/reactor" else 760)
        if route == "/reactor":
            window.maximize()
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.get_style_context().add_class("reactoros-titlebar")
        label = Gtk.Label(label=title)
        header.set_custom_title(label)
        for icon, action in (("window-minimize-symbolic", window.iconify),
                             ("window-maximize-symbolic", lambda: self._toggle_maximize(window)),
                             ("window-close-symbolic", window.close)):
            button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            button.connect("clicked", lambda _button, fn=action: fn())
            header.pack_end(button)
            if icon == "window-maximize-symbolic":
                window.connect("window-state-event", self._update_maximize_icon, button)
        window.set_titlebar(header)
        window.connect("key-press-event", self._handle_window_key)

        view = self._new_view(window, related)
        window.add(view)
        window.show_all()
        window.present()
        self.windows.append(window)
        window.connect("destroy", lambda item: self._forget_window(item))
        view.load_uri(BASE + route + ("#" + TOKEN if TOKEN else ""))
        return view

    def _new_view(self, window, related=None):
        view = (WebKit2.WebView.new_with_related_view(related) if related else
                WebKit2.WebView.new_with_context(self.web_context))
        manager = view.get_user_content_manager()
        name = json.dumps(self.identity.get("name", ""))
        perms = json.dumps(sorted(self.permissions))
        token = json.dumps(TOKEN)
        script = f"""
          try {{
            sessionStorage.setItem('reactoros-terminal-token', {token});
            sessionStorage.setItem('reactoros-debian-operator', {name});
            sessionStorage.setItem('reactoros-permissions', {perms});
            localStorage.setItem('unit2-operator-name', {name});
          }} catch (error) {{ console.error('ReactorOS session setup failed', error); }}
        """
        manager.add_script(WebKit2.UserScript.new(
            script, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START, None, None))
        view.connect("create", self._create_popup)
        view.connect("decide-policy", self._handle_navigation)
        return view

    def _create_popup(self, parent, _action):
        new_window = Gtk.ApplicationWindow(application=self)
        new_window.set_default_size(1180, 760)
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.get_style_context().add_class("reactoros-titlebar")
        header.set_title("ReactorOS Program")
        new_window.set_titlebar(header)
        new_window.connect("key-press-event", self._handle_window_key)
        view = self._new_view(new_window, parent)
        new_window.add(view)
        new_window.show_all()
        new_window.present()
        self.windows.append(new_window)
        new_window.connect("destroy", lambda item: self._forget_window(item))
        return view

    @staticmethod
    def _toggle_maximize(window):
        if window.is_maximized():
            window.unmaximize()
        else:
            window.maximize()

    @staticmethod
    def _update_maximize_icon(window, event, button):
        maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)
        icon = "window-restore-symbolic" if maximized else "window-maximize-symbolic"
        button.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
        return False

    def _handle_window_key(self, window, event):
        if event.keyval == Gdk.KEY_F11:
            if window.get_window() and window.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
                window.unfullscreen()
            else:
                window.fullscreen()
            return True
        return False

    def _handle_navigation(self, view, decision, decision_type):
        if decision_type != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        parsed = urlsplit(uri)
        if parsed.scheme in ("http", "https") and parsed.hostname != "127.0.0.1":
            subprocess.Popen(["firefox-esr", "--new-window", uri], start_new_session=True)
            decision.ignore()
            return True
        return False

    def _forget_window(self, window):
        if window in self.windows:
            self.windows.remove(window)
        if not self.windows:
            self.quit()


if __name__ == "__main__":
    try:
        application = ReactorOSApps()
    except (OSError, URLError, ValueError) as error:
        print("ReactorOS native applications could not connect to the local service:", error,
              file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(application.run(sys.argv))
