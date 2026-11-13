"""Minimal Telegram Bot API helpers (no polling, everything is request/response)."""
from typing import Optional

import httpx

from . import config

TIMEOUT = 15


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{config.bot_token()}/{method}"


def configured() -> bool:
    return bool(config.bot_token() and config.channel_id())


def quiz_link(quiz_id: str) -> str:
    return f"{config.mini_app_link()}?startapp={quiz_id}"


def _check(r: httpx.Response) -> dict:
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram error"))
    return data["result"]


def send_message(text: str, button_text: str, url: str) -> dict:
    payload = {
        "chat_id": config.channel_id(),
        "text": text,
        "reply_markup": {"inline_keyboard": [[{"text": button_text, "url": url}]]},
    }
    return _check(httpx.post(_url("sendMessage"), json=payload, timeout=TIMEOUT))


def send_photo(png: bytes, caption: str, button_text: str, url: str) -> dict:
    import json

    data = {
        "chat_id": config.channel_id(),
        "caption": caption,
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": button_text, "url": url}]]}),
    }
    files = {"photo": ("winner.png", png, "image/png")}
    return _check(httpx.post(_url("sendPhoto"), data=data, files=files, timeout=30))


def download(url: str) -> Optional[bytes]:
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def profile_photo(user_id: int, fallback_url: Optional[str]) -> Optional[bytes]:
    """Best effort: Bot API profile photo first, then the photo_url Telegram gave the mini app."""
    try:
        photos = _check(httpx.get(_url("getUserProfilePhotos"), params={"user_id": user_id, "limit": 1}, timeout=TIMEOUT))
        if photos.get("total_count"):
            file_id = photos["photos"][0][-1]["file_id"]
            f = _check(httpx.get(_url("getFile"), params={"file_id": file_id}, timeout=TIMEOUT))
            img = download(f"https://api.telegram.org/file/bot{config.bot_token()}/{f['file_path']}")
            if img:
                return img
    except Exception:
        pass
    return download(fallback_url) if fallback_url else None
