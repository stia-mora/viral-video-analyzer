import hashlib
import hmac
import secrets
import time
import uuid
from fastapi import Depends, HTTPException, Request
from .store import connect


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def verify_password(password, stored):
    salt, expected = stored.split(":")
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    )
    return hmac.compare_digest(digest.hex(), expected)


def create_user(username, name, password, role="member"):
    user_id = uuid.uuid4().hex
    with connect() as con:
        con.execute(
            "INSERT INTO users(id,username,name,password,role,created) VALUES(?,?,?,?,?,?)",
            (user_id, username, name, hash_password(password), role, time.time()),
        )
    return user_id


def user(request: Request):
    token = request.cookies.get("pianxi_session", "")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connect() as con:
        row = con.execute(
            "SELECT u.id,u.username,u.name,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1",
            (digest, time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "请先登录")
    return dict(row)


def admin(current=Depends(user)):
    if current["role"] != "admin":
        raise HTTPException(403, "仅管理员可执行此操作")
    return current
