"""Interactive Debian and ReactorOS account administration, run through sudo."""
import grp
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile

from workstation_access import DEFAULT_ROLES, PERMISSIONS, ROLE_FILE, read_policy


def save(policy):
    ROLE_FILE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=ROLE_FILE.parent, delete=False) as file:
        json.dump(policy, file, indent=2)
        file.write("\n")
        os.fchmod(file.fileno(), 0o644)
    os.replace(file.name, ROLE_FILE)


def select_account():
    name = input("Debian username: ").strip()
    account = pwd.getpwnam(name)
    if account.pw_uid < 1000 or account.pw_uid >= 60000:
        raise ValueError("Choose a regular Debian account.")
    return account


def manage():
    if os.geteuid() != 0:
        raise SystemExit("Run User Manager through Debian sudo.")
    while True:
        print("\nReactorOS User Manager")
        print("1 List users and roles   2 Add Debian user   3 Assign roles")
        print("4 Create/edit custom role   5 Grant/revoke Debian sudo   6 Set password   Q Exit")
        try:
            choice = input("> ").strip().lower()
            policy = read_policy()
            roles = DEFAULT_ROLES | policy["roles"]
            if choice == "q":
                return
            if choice == "1":
                sudo_group = grp.getgrnam("sudo").gr_gid
                for user in pwd.getpwall():
                    if 1000 <= user.pw_uid < 60000:
                        sudo = sudo_group in os.getgrouplist(user.pw_name, user.pw_gid)
                        assigned = policy["users"].get(user.pw_name, ["admin" if sudo else "trainee"])
                        print(f"{user.pw_name}: {', '.join(assigned)} | Debian sudo: {'yes' if sudo else 'no'}")
                for name, permissions in roles.items():
                    print(f"{name}: {', '.join(sorted(permissions))}")
            elif choice == "2":
                name = input("New Debian username: ").strip()
                if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", name):
                    raise ValueError("Use a lowercase Debian username.")
                subprocess.run(["adduser", name], check=True)
            elif choice == "3":
                account = select_account()
                print("Available: " + ", ".join(sorted(roles)))
                assigned = sorted(set(input("Roles, separated by spaces: ").split()))
                if not assigned or set(assigned) - roles.keys():
                    raise ValueError("Enter one or more valid roles.")
                if account.pw_name == os.environ.get("SUDO_USER") and not any(
                    "users:manage" in roles[role] for role in assigned
                ):
                    raise ValueError("Keep user management access on your own account.")
                policy["users"][account.pw_name] = assigned
                save(policy)
            elif choice == "4":
                name = input("Custom role name: ").strip()
                if name in DEFAULT_ROLES or not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", name):
                    raise ValueError("Use a custom lowercase role name.")
                print("Permissions: " + ", ".join(sorted(PERMISSIONS)))
                selected = sorted(set(input("Permissions, separated by spaces: ").split()))
                if set(selected) - PERMISSIONS:
                    raise ValueError("Unknown permission.")
                policy["roles"][name] = selected
                save(policy)
            elif choice == "5":
                account = select_account()
                action = input("Grant or revoke sudo [grant/revoke]: ").strip()
                if action == "grant":
                    subprocess.run(["adduser", account.pw_name, "sudo"], check=True)
                elif action == "revoke" and account.pw_name != os.environ.get("SUDO_USER"):
                    subprocess.run(["deluser", account.pw_name, "sudo"], check=True)
                else:
                    raise ValueError("Choose grant or revoke. You cannot revoke your own sudo.")
            elif choice == "6":
                subprocess.run(["passwd", select_account().pw_name], check=True)
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
            print(f"User Manager: {error}")
        except (EOFError, KeyboardInterrupt):
            return


def manage_gui():
    if os.geteuid() != 0:
        raise SystemExit("Run User Manager through Debian sudo.")
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog
    except ImportError:
        raise SystemExit("User Manager needs Tk. Run sudo apt-get install python3-tk.")

    root = tk.Tk()
    root.title("ReactorOS User Manager")
    root.configure(bg="#c0c0c0", padx=12, pady=12)
    root.option_add("*Background", "#c0c0c0")
    root.option_add("*Listbox.background", "white")
    actor = os.environ.get("SUDO_USER")

    def listbox(parent, label, mode=tk.BROWSE):
        tk.Label(parent, text=label).pack(anchor="w")
        box = tk.Listbox(parent, selectmode=mode, exportselection=False, height=14, width=30)
        scroll = tk.Scrollbar(parent, command=box.yview)
        box.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        box.pack(side="left", fill="both", expand=True)
        return box

    def selected(box):
        return [box.get(index) for index in box.curselection()]

    def fill(box, values, choices=()):
        box.delete(0, tk.END)
        for index, value in enumerate(values):
            box.insert(tk.END, value)
            if value in choices:
                box.selection_set(index)

    def account():
        names = selected(users)
        if not names:
            raise ValueError("Select a user first.")
        return pwd.getpwnam(names[0])

    def has_sudo(user):
        return grp.getgrnam("sudo").gr_gid in os.getgrouplist(user.pw_name, user.pw_gid)

    def assigned(user, policy):
        return policy["users"].get(user.pw_name, ["admin" if has_sudo(user) else "trainee"])

    def refresh_roles():
        policy = read_policy()
        names = selected(users)
        if names:
            user = account()
            sudo_value.set(has_sudo(user))
            fill(roles, sorted(DEFAULT_ROLES | policy["roles"]), assigned(user, policy))
        else:
            sudo_value.set(False)
            fill(roles, sorted(DEFAULT_ROLES | policy["roles"]))

    def refresh_users(name=None):
        fill(users, sorted(u.pw_name for u in pwd.getpwall() if 1000 <= u.pw_uid < 60000), [name])
        refresh_roles()

    def password():
        value = simpledialog.askstring("Password", "New password", show="*", parent=root)
        if value is None:
            return None
        repeat = simpledialog.askstring("Password", "Repeat the password", show="*", parent=root)
        if repeat is None:
            return None
        if not value or value != repeat or any(char in value for char in "\r\n\0"):
            raise ValueError("Enter a matching, nonempty password.")
        return value

    def set_password(name, value):
        subprocess.run(["/usr/sbin/chpasswd"], input=f"{name}:{value}\n", text=True, check=True)

    def add_user():
        name = simpledialog.askstring("New user", "Debian username", parent=root)
        if name is None:
            return
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", name):
            raise ValueError("Use a lowercase Debian username.")
        value = password()
        if value is None:
            return
        subprocess.run(["/usr/sbin/useradd", "-m", "-g", "users", "-s", "/bin/bash", name], check=True)
        set_password(name, value)
        refresh_users(name)

    def change_password():
        name = account().pw_name
        value = password()
        if value is not None:
            set_password(name, value)

    def save_user():
        user = account()
        names = selected(roles)
        policy = read_policy()
        available = DEFAULT_ROLES | policy["roles"]
        if not names or set(names) - available.keys():
            raise ValueError("Select at least one valid role.")
        if user.pw_name == actor and (not sudo_value.get() or
                not any("users:manage" in available[name] for name in names)):
            raise ValueError("Keep sudo and user management access on your own account.")
        if sudo_value.get() != has_sudo(user):
            if not messagebox.askyesno("Debian sudo", "Change this account's Debian administrator access?", parent=root):
                return
            if sudo_value.get():
                subprocess.run(["/usr/sbin/usermod", "-aG", "sudo", user.pw_name], check=True)
            else:
                subprocess.run(["/usr/bin/gpasswd", "-d", user.pw_name, "sudo"], check=True)
        policy["users"][user.pw_name] = names
        save(policy)
        refresh_roles()
        messagebox.showinfo("User Manager", "Account settings saved. Sign in again to refresh access.", parent=root)

    def edit_role():
        choices = selected(roles)
        initial = choices[0] if len(choices) == 1 and choices[0] not in DEFAULT_ROLES else ""
        name = simpledialog.askstring("Custom role", "New or existing custom role name", initialvalue=initial, parent=root)
        if name is None:
            return
        if name in DEFAULT_ROLES or not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", name):
            raise ValueError("Use a custom lowercase role name.")
        window = tk.Toplevel(root)
        window.title("Permissions for " + name)
        window.transient(root)
        window.grab_set()
        panel = tk.Frame(window, padx=10, pady=10)
        panel.pack(fill="both", expand=True)
        permissions = listbox(panel, "Select permissions", tk.MULTIPLE)
        fill(permissions, sorted(PERMISSIONS), read_policy()["roles"].get(name, []))

        def save_role():
            policy = read_policy()
            policy["roles"][name] = selected(permissions)
            if actor:
                available = DEFAULT_ROLES | policy["roles"]
                if not any("users:manage" in available.get(role, ()) for role in assigned(pwd.getpwnam(actor), policy)):
                    raise ValueError("Keep user management access on your own account.")
            save(policy)
            window.destroy()
            refresh_roles()

        tk.Button(window, text="Save role", command=guard(save_role)).pack(pady=5)

    def guard(action):
        def run():
            try:
                action()
            except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
                messagebox.showerror("User Manager", str(error), parent=root)
        return run

    panels = tk.Frame(root)
    panels.pack(fill="both", expand=True)
    user_panel = tk.Frame(panels)
    user_panel.pack(side="left", padx=(0, 10), fill="both", expand=True)
    role_panel = tk.Frame(panels)
    role_panel.pack(side="left", fill="both", expand=True)
    users = listbox(user_panel, "Debian accounts")
    roles = listbox(role_panel, "Assigned ReactorOS roles", tk.MULTIPLE)
    users.bind("<<ListboxSelect>>", lambda _event: refresh_roles())
    sudo_value = tk.BooleanVar()
    tk.Checkbutton(root, text="Debian administrator (sudo)", variable=sudo_value).pack(anchor="w", pady=8)
    buttons = tk.Frame(root)
    buttons.pack(fill="x")
    for title, action in (("Add user", add_user), ("Set password", change_password),
                          ("Save user", save_user), ("Custom roles…", edit_role)):
        tk.Button(buttons, text=title, command=guard(action)).pack(side="left", padx=3)
    refresh_users(actor)
    root.mainloop()


if __name__ == "__main__":
    manage_gui() if sys.argv[1:] == ["--gui"] else manage()
