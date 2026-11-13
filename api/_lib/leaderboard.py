from datetime import datetime, timedelta, timezone
import math

from . import config


def now() -> datetime:
    return datetime.now(timezone.utc)


def day_key(dt: datetime) -> str:
    return dt.astimezone(config.app_tz()).strftime("%Y-%m-%d")


def next_reset(dt: datetime) -> datetime:
    local = dt.astimezone(config.app_tz())
    nxt = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.astimezone(timezone.utc)


def standings(attempts: list) -> list:
    """Sum every submitted attempt per user. Ties on points go to the lower total time."""
    agg = {}
    for a in sorted(attempts, key=lambda x: x["submitted_at"]):
        u = a["user"]
        row = agg.setdefault(
            a["user_id"],
            {"user_id": a["user_id"], "points": 0, "time_ms": 0, "first": a["submitted_at"]},
        )
        row.update(name=u["name"], username=u.get("username"), photo_url=u.get("photo_url"))
        row["points"] += a["points"]
        row["time_ms"] += math.ceil(a["time_ms"] / 1000) * 1000
    rows = sorted(agg.values(), key=lambda r: (-r["points"], r["time_ms"], r["first"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def board_for_day(db, key: str) -> list:
    """Standings for a day, with movement caused by the most recently played quiz.

    up/down = places gained/lost by the latest quiz, same = unchanged, new = first quiz of the day.
    """
    atts = list(db.attempts.find({"day_key": key, "submitted_at": {"$ne": None}}))
    rows = standings(atts)
    prev = {}
    if atts and len({a["quiz_id"] for a in atts}) > 1:
        latest = max(atts, key=lambda a: a["submitted_at"])["quiz_id"]
        prev = {r["user_id"]: r["rank"] for r in standings([a for a in atts if a["quiz_id"] != latest])}
    for r in rows:
        r.pop("first", None)
        if r["user_id"] not in prev:
            r["move"], r["delta"] = "new", 0
        else:
            d = prev[r["user_id"]] - r["rank"]
            r["move"] = "up" if d > 0 else "down" if d < 0 else "same"
            r["delta"] = abs(d)
    return rows
