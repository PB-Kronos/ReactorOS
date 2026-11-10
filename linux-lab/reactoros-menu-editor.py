#!/usr/bin/python3
"""Per-account allowlist editor for the ReactorOS Start menu."""
import grp
import json
import os
import pwd
import tkinter as tk
from tkinter import messagebox, ttk

from workstation_access import DEFAULT_ROLES, MENU_APPS, ROLE_FILE, installed_menu_apps, read_policy


def account_has_sudo(user):
    try:
        gid = grp.getgrnam("sudo").gr_gid
        return gid in os.getgrouplist(user.pw_name, user.pw_gid)
    except KeyError:
        return False


def role_permissions(user, policy):
    sudo = account_has_sudo(user)
    roles = policy.get("users", {}).get(user.pw_name,
                                         ["admin" if sudo else "trainee"])
    permissions = set()
    for role in roles:
        permissions.update(DEFAULT_ROLES.get(role, policy.get("roles", {}).get(role, [])))
    if not sudo:
        permissions.difference_update({"users:manage", "terminal:execute"})
    return permissions


def save_policy(policy):
    import tempfile
    ROLE_FILE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=ROLE_FILE.parent, delete=False) as stream:
        json.dump(policy, stream, indent=2)
        stream.write("\n")
        os.fchmod(stream.fileno(), 0o644)
    os.replace(stream.name, ROLE_FILE)


def main():
    if os.geteuid() != 0 or not os.environ.get("SUDO_USER"):
        raise SystemExit("Open Start Menu Editor from ReactorOS Settings.")

    accounts = sorted((user for user in pwd.getpwall()
                       if 1000 <= user.pw_uid < 60000), key=lambda user: user.pw_name)
    root = tk.Tk()
    root.title("ReactorOS Start Menu Editor")
    root.geometry("800x560")
    root.configure(bg="#c0c0c0", padx=12, pady=12)
    root.option_add("*Background", "#c0c0c0")
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", background="white", fieldbackground="white",
                    foreground="black", rowheight=26, borderwidth=2, relief="sunken")
    style.map("Treeview", background=[("selected", "#000080")],
              foreground=[("selected", "white")])

    tk.Label(root, text="ReactorOS Start Menu Editor", font=("TkDefaultFont", 14, "bold"),
             bg="#c0c0c0").pack(anchor="w", pady=(0, 4))
    tk.Label(root, text="Choose a Debian account, then tick the apps shown in that account's Start menu.",
             bg="#c0c0c0").pack(anchor="w", pady=(0, 10))

    body = tk.Frame(root, bg="#c0c0c0")
    body.pack(fill="both", expand=True)
    left = tk.Frame(body, bg="#c0c0c0")
    left.pack(side="left", fill="y", padx=(0, 12))
    tk.Label(left, text="Debian users", bg="#c0c0c0").pack(anchor="w")
    user_list = tk.Listbox(left, exportselection=False, width=20, height=22,
                           bg="white", selectbackground="#000080", selectforeground="white")
    user_scroll = tk.Scrollbar(left, command=user_list.yview)
    user_list.configure(yscrollcommand=user_scroll.set)
    user_scroll.pack(side="right", fill="y")
    user_list.pack(side="left", fill="y")

    right = tk.Frame(body, bg="#c0c0c0")
    right.pack(side="left", fill="both", expand=True)
    search_var = tk.StringVar()
    tk.Label(right, text="Find an installed app", bg="#c0c0c0").pack(anchor="w")
    search = tk.Entry(right, textvariable=search_var, bg="white")
    search.pack(fill="x", pady=(2, 8))
    tree_frame = tk.Frame(right, bg="#c0c0c0")
    tree_frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(tree_frame, columns=("application", "access"), show="tree headings",
                        selectmode="browse")
    tree.heading("#0", text="In Start menu")
    tree.heading("application", text="Application")
    tree.heading("access", text="Access")
    tree.column("#0", width=105, stretch=False, anchor="center")
    tree.column("application", width=330, stretch=True)
    tree.column("access", width=190, stretch=True)
    tree_scroll = ttk.Scrollbar(tree_frame, command=tree.yview)
    tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    status = tk.Label(root, text="", anchor="w", bg="#c0c0c0")
    status.pack(fill="x", pady=(7, 0))

    policy = read_policy()
    visible_keys = set()
    entries = {}
    rows = {}
    chosen_user = [None]

    def refresh_entries(user):
        nonlocal policy
        policy = read_policy()
        permissions = role_permissions(user, policy)
        entries.clear()
        for key, (_permission, label, _desktop) in MENU_APPS.items():
            entries[key] = (label, _permission in permissions,
                            "ReactorOS app" if _permission in permissions else "Role permission needed")
        for identifier, (label, _path) in installed_menu_apps(user.pw_dir).items():
            entries["desktop:" + identifier] = (label, True, "Assigned app")

        configured = policy.get("visible_apps", {}).get(user.pw_name)
        if configured is None:
            visible_keys.clear()
            visible_keys.update(key for key, (_label, permitted, _access) in entries.items()
                                if key in MENU_APPS and permitted)
        else:
            visible_keys.clear()
            visible_keys.update(key for key in configured if key in entries and
                                (key not in MENU_APPS or entries[key][1]))
        status.configure(text=f"Editing {user.pw_name}. Role permissions still control ReactorOS app access.")
        render()

    def render(*_args):
        selected = str(tree.focus())
        tree.delete(*tree.get_children())
        rows.clear()
        query = search_var.get().strip().casefold()
        for key, (label, permitted, access) in sorted(entries.items(), key=lambda item: item[1][0].casefold()):
            if key in MENU_APPS and not permitted:
                access = "Role permission needed"
            elif key in visible_keys:
                access = "ReactorOS app" if key in MENU_APPS else "Assigned app"
            if query and query not in label.casefold() and query not in key.casefold():
                continue
            marker = "[x]" if key in visible_keys else "[ ]"
            row = tree.insert("", "end", iid=key, text=marker, values=(label, access))
            rows[key] = row
        if selected in rows:
            tree.focus(selected)
            tree.selection_set(selected)

    def toggle(_event=None):
        key = tree.focus()
        if not key or key not in entries:
            return
        if key in MENU_APPS and not entries[key][1]:
            messagebox.showinfo("ReactorOS Start Menu Editor",
                                "Assign the app's ReactorOS role permission in User Management first.",
                                parent=root)
            return
        if key in visible_keys:
            visible_keys.remove(key)
        else:
            visible_keys.add(key)
        render()
        tree.focus(key)
        tree.selection_set(key)

    def save():
        if chosen_user[0] is None:
            messagebox.showinfo("ReactorOS Start Menu Editor", "Choose a Debian user first.", parent=root)
            return
        policy = read_policy()
        policy.setdefault("visible_apps", {})[chosen_user[0].pw_name] = sorted(visible_keys)
        save_policy(policy)
        status.configure(text=f"Saved {chosen_user[0].pw_name}'s Start menu. Sign out and back in to apply it.")

    def reset_defaults():
        if chosen_user[0] is None:
            return
        permissions = role_permissions(chosen_user[0], read_policy())
        visible_keys.clear()
        visible_keys.update(key for key, (permission, _label, _desktop) in MENU_APPS.items()
                            if permission in permissions)
        render()

    def user_selected(_event=None):
        selection = user_list.curselection()
        if not selection:
            return
        chosen_user[0] = accounts[selection[0]]
        refresh_entries(chosen_user[0])

    for user in accounts:
        user_list.insert(tk.END, user.pw_name)
    user_list.bind("<<ListboxSelect>>", user_selected)
    tree.bind("<Button-1>", lambda event: (tree.identify_row(event.y) and tree.focus(tree.identify_row(event.y)), toggle()))
    tree.bind("<space>", toggle)
    search_var.trace_add("write", render)

    buttons = tk.Frame(root, bg="#c0c0c0")
    buttons.pack(fill="x", pady=(9, 0))
    tk.Button(buttons, text="ReactorOS defaults", command=reset_defaults).pack(side="left")
    tk.Button(buttons, text="Save menu", command=save).pack(side="right")
    if accounts:
        user_list.selection_set(0)
        user_selected()
    root.mainloop()


if __name__ == "__main__":
    main()
