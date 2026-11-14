import html
import json
import logging
import re
from typing import Optional

import httpx

from . import config

logger = logging.getLogger(__name__)

TIMEOUT = 15


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{config.bot_token()}/{method}"


def configured() -> bool:
    return bool(config.bot_token() and config.channel_id())


def get_chat(chat: str) -> dict:
    return _check(httpx.get(_url("getChat"), params={"chat_id": chat}, timeout=TIMEOUT))


def get_me() -> dict:
    return _check(httpx.get(_url("getMe"), timeout=TIMEOUT))


def get_chat_member(chat_id: str, user_id: int) -> dict:
    return _check(httpx.get(
        _url("getChatMember"),
        params={"chat_id": chat_id, "user_id": user_id},
        timeout=TIMEOUT,
    ))


def file_bytes(file_id: str) -> Optional[tuple[bytes, str]]:
    file_info = _check(httpx.get(_url("getFile"), params={"file_id": file_id}, timeout=TIMEOUT))
    response = httpx.get(
        f"https://api.telegram.org/file/bot{config.bot_token()}/{file_info['file_path']}",
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    valid, mime = is_image_bytes(response.content)
    return (response.content, mime) if valid else None


def verify_channel_access(chat_id: str, user_id: int) -> dict:
    """Confirm the user administers this channel and the bot can publish to it."""
    chat = get_chat(chat_id)
    if chat.get("type") != "channel":
        raise ValueError("That username does not belong to a Telegram channel.")
    bot = get_me()
    bot_member = get_chat_member(chat_id, int(bot["id"]))
    if bot_member.get("status") not in ("administrator", "creator") or (
        bot_member.get("status") == "administrator" and not bot_member.get("can_post_messages", False)
    ):
        raise ValueError("Make the bot an administrator with permission to post messages, then try again.")
    user_member = get_chat_member(chat_id, user_id)
    if user_member.get("status") not in ("administrator", "creator"):
        raise ValueError("You must be an administrator of this channel to connect it.")
    return chat


def quiz_link(quiz_id: str) -> str:
    return f"{config.mini_app_link()}?startapp={quiz_id}"


def watermark_html() -> str:
    app_url = config.mini_app_link() or "https://t.me"
    return f'<a href="{html.escape(app_url, quote=True)}">Powered By Footy Quiz</a>'


def _check(r: httpx.Response) -> dict:
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram error"))
    return data["result"]


def is_image_bytes(data: bytes) -> tuple[bool, str]:
    if not data or len(data) < 4:
        return False, ""
    if data.startswith(b"\xff\xd8\xff"):
        return True, "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True, "image/png"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return True, "image/webp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return True, "image/gif"
    return False, ""


def extract_direct_image_url(html_str: str) -> Optional[str]:
    """Finds direct image URLs in OpenGraph / Twitter / HTML tags (e.g. on ibb.co viewer pages)."""
    # 1. OpenGraph tag: <meta property="og:image" content="..." />
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html_str, re.IGNORECASE)
    if m:
        return m.group(1).replace("&amp;", "&")

    # 2. Twitter image tag: <meta name="twitter:image" content="..." />
    m = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']', html_str, re.IGNORECASE)
    if m:
        return m.group(1).replace("&amp;", "&")

    # 3. Direct ImgBB image tag: <img ... src="(https://i.ibb.co/[^"]+)"
    m = re.search(r'<img[^>]+src=["\'](https://i\.ibb\.co/[^"\']+)["\']', html_str, re.IGNORECASE)
    if m:
        return m.group(1).replace("&amp;", "&")

    # 4. link rel="image_src"
    m = re.search(r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
    if m:
        return m.group(1).replace("&amp;", "&")

    return None


def fetch_image_bytes(url: str) -> Optional[tuple[bytes, str]]:
    """Download image bytes, extracting the real image link from viewer pages (like ibb.co) if needed."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, headers=headers)
        if r.status_code != 200:
            return None

        is_img, mime = is_image_bytes(r.content)
        if is_img:
            return r.content, mime

        # If it returned HTML (e.g. ibb.co viewer page), extract the direct image link
        try:
            direct_url = extract_direct_image_url(r.text)
            if direct_url and direct_url != url:
                r2 = httpx.get(direct_url, timeout=TIMEOUT, follow_redirects=True, headers=headers)
                if r2.status_code == 200:
                    is_img2, mime2 = is_image_bytes(r2.content)
                    if is_img2:
                        return r2.content, mime2
        except Exception as e:
            logger.debug("Failed parsing HTML for direct image: %s", e)

        return None
    except Exception as e:
        logger.debug("Failed fetching image bytes: %s", e)
        return None


def send_message(text: str, button_text: str, url: str, parse_mode: str = "HTML", chat_id: Optional[str] = None) -> dict:
    payload = {
        "chat_id": chat_id or config.channel_id(),
        "text": text,
        "parse_mode": parse_mode,
        "reply_markup": {"inline_keyboard": [[{"text": button_text, "url": url}]]},
    }
    return _check(httpx.post(_url("sendMessage"), json=payload, timeout=TIMEOUT))


def send_photo_url(photo_url: str, caption: str, button_text: str, url: str, parse_mode: str = "HTML", chat_id: Optional[str] = None) -> dict:
    payload = {
        "chat_id": chat_id or config.channel_id(),
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode,
        "reply_markup": {"inline_keyboard": [[{"text": button_text, "url": url}]]},
    }
    return _check(httpx.post(_url("sendPhoto"), json=payload, timeout=TIMEOUT))


def send_photo(png: bytes, caption: str, button_text: str, url: str, parse_mode: str = "HTML", chat_id: Optional[str] = None) -> dict:
    data = {
        "chat_id": chat_id or config.channel_id(),
        "caption": caption,
        "parse_mode": parse_mode,
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": button_text, "url": url}]]}),
    }
    files = {"photo": ("winner.png", png, "image/png")}
    return _check(httpx.post(_url("sendPhoto"), data=data, files=files, timeout=30))


def send_quiz_notification(caption: str, button_text: str, url: str, image_url: Optional[str] = None, chat_id: Optional[str] = None) -> dict:
    img = (image_url or config.quiz_notification_image_url()).strip()
    if img:
        # 1. Try downloading real image bytes (handles ibb.co viewer pages and direct URLs)
        img_data = fetch_image_bytes(img)
        if img_data:
            raw_bytes, mime = img_data
            ext = "jpg" if "jpeg" in mime else mime.split("/")[-1]
            try:
                data = {
                    "chat_id": chat_id or config.channel_id(),
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps({"inline_keyboard": [[{"text": button_text, "url": url}]]}),
                }
                files = {"photo": (f"quiz_notification.{ext}", raw_bytes, mime)}
                return _check(httpx.post(_url("sendPhoto"), data=data, files=files, timeout=30))
            except Exception as e:
                logger.warning("Telegram sendPhoto with downloaded bytes failed: %s", e)

        # 2. Try passing image URL directly to Telegram
        try:
            return send_photo_url(img, caption, button_text, url, parse_mode="HTML", chat_id=chat_id)
        except Exception as e:
            logger.warning("Telegram sendPhoto with URL failed: %s", e)

    # 3. Fallback to rich text message
    return send_message(caption, button_text, url, parse_mode="HTML", chat_id=chat_id)


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
