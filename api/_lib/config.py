import os
from zoneinfo import ZoneInfo


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def bot_token() -> str:
    return env("BOT_TOKEN")


def channel_id() -> str:
    return env("CHANNEL_ID")  # e.g. @footyriddles or -100123456789


def mini_app_link() -> str:
    return env("MINI_APP_LINK").rstrip("/")  # e.g. https://t.me/MyQuizBot/play


def admin_ids() -> set[int]:
    out = set()
    for part in env("ADMIN_IDS").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def dev_mode() -> bool:
    return env("DEV_MODE") == "1"


def app_tz() -> ZoneInfo:
    return ZoneInfo(env("APP_TZ", "UTC"))


def cron_secret() -> str:
    return env("CRON_SECRET")


def quiz_notification_image_url() -> str:
    return env("QUIZ_NOTIFICATION_IMAGE_URL", "https://ibb.co/B5RgyFsH")
