"""Interactive Debian and ReactorOS account administration, run through sudo."""
import grp
import json
import os
import pwd
import re
import subprocess
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


if __name__ == "__main__":
    manage()
