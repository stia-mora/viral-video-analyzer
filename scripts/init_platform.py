"""Initialize the first team administrator without a network-exposed setup route."""

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import store, security, config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="admin")
    parser.add_argument("--name", default="管理员")
    args = parser.parse_args()
    store.init()
    with store.connect() as con:
        exists = con.execute("SELECT id FROM users LIMIT 1").fetchone()
    if exists:
        print("Team already initialized. Existing users preserved.")
        return
    password = secrets.token_urlsafe(15)
    security.create_user(args.username, args.name, password, "admin")
    path = config.DATA / "first-login.txt"
    path.write_text(
        f"片析团队工作台\n地址：http://localhost:8765\n账号：{args.username}\n初始密码：{password}\n请登录后在设置中修改密码。\n",
        encoding="utf-8",
    )
    import os, subprocess

    if os.name == "nt":
        import getpass

        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                getpass.getuser() + ":(F)",
                "SYSTEM:(F)",
            ],
            capture_output=True,
            check=True,
        )
    else:
        path.chmod(0o600)
    print("First administrator created. Credentials saved in " + str(path))


if __name__ == "__main__":
    main()
