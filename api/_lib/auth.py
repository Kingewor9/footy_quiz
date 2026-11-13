import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException

from . import config

MAX_AGE_SECONDS = 2 * 24 * 3600


def validate_init_data(init_data: str, token: str, max_age: int = MAX_AGE_SECONDS) -> dict:
    """Verify Telegram WebApp initData (HMAC-SHA256) and return the user dict."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received or not token:
        raise ValueError("missing hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        raise ValueError("bad signature")
    if time.time() - int(pairs.get("auth_date", "0")) > max_age:
        raise ValueError("expired")
    return json.loads(pairs["user"])


def _shape(u: dict) -> dict:
    name = " ".join(p for p in [u.get("first_name"), u.get("last_name")] if p) or u.get("username") or "Player"
    return {
        "id": int(u["id"]),
        "name": name,
        "username": u.get("username"),
        "photo_url": u.get("photo_url"),
        "is_admin": int(u["id"]) in config.admin_ids(),
    }


def current_user(
    authorization: Optional[str] = Header(None),
    x_dev_user: Optional[str] = Header(None),
) -> dict:
    if config.dev_mode() and x_dev_user:
        return _shape(json.loads(x_dev_user))
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(401, "Open this app from Telegram.")
    try:
        return _shape(validate_init_data(authorization[4:], config.bot_token()))
    except Exception:
        raise HTTPException(401, "Telegram login could not be verified. Reopen the app.")


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "Admins only.")
    return user
