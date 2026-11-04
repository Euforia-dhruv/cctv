"""Authentication: PBKDF2 hashes + opaque bearer tokens (stdlib only)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request

from . import db, utils

SESSION_DAYS = 30


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return f"{salt}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(calc.hex(), h)


def create_session(user_id: int) -> str:
    token = utils.new_token()
    expires = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + SESSION_DAYS * 86400))
    db.exec("INSERT INTO sessions(token, user_id, expires_at) VALUES (?,?,?)",
            (token, user_id, expires))
    return token


def user_from_token(token: str) -> dict | None:
    if not token:
        return None
    row = db.q1("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                    WHERE s.token = ? AND s.expires_at > datetime('now')""", (token,))
    return row


def require_user(request: Request) -> dict:
    token = request.headers.get("x-auth-token") or request.headers.get("authorization", "").removeprefix("Bearer ")
    user = user_from_token(token)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def optional_user(request: Request) -> dict | None:
    """Media endpoints: auth if present, otherwise anonymous (single-org prototype)."""
    token = request.headers.get("x-auth-token") or request.headers.get("authorization", "").removeprefix("Bearer ")
    return user_from_token(token)


def require_role(role: str):
    def dep(request: Request):
        user = require_user(request)
        if user["role"] != "admin" and (role == "admin" or user["role"] not in ("admin", "analyst", "reviewer")):
            raise HTTPException(403, "Insufficient role")
        return user
    return dep
