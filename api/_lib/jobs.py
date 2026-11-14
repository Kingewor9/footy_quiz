"""Work triggered by the /api/cron/tick endpoint: publish scheduled quizzes, announce winners."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config, telegram
from .leaderboard import board_for_day, day_key, now
from .winner_card import build_card, fmt_time


def publish_quiz(db, quiz: dict) -> dict:
    """Mark a quiz live and post the channel notification. Returns {notified, error}."""
    notified, error = False, None
    expires_hours = quiz.get("expires_hours", 24)
    if telegram.configured() and config.mini_app_link():
        try:
            total = sum(q["points"] for q in quiz["questions"])
            n = len(quiz["questions"])
            title = quiz.get("title", "").strip()

            text = (
                f"<b>New Quiz Available</b>\n\n"
                f"<b>Title:</b> {title}\n"
                f"<b>Total questions:</b> {n}\n"
                f"<b>Total points:</b> {total} pts\n"
                f"<b>Expires:</b> {expires_hours} hours\n\n"
                f"Hit the <b>Play Now</b> button below to start!"
            )
            button_label = "Play now"
            msg = telegram.send_quiz_notification(
                caption=text,
                button_text=button_label,
                url=telegram.quiz_link(quiz["_id"]),
                image_url=config.quiz_notification_image_url(),
            )
            notified = True
            db.quizzes.update_one({"_id": quiz["_id"]}, {"$set": {"channel_message_id": msg["message_id"]}})
        except Exception as e:  # keep the quiz live even if the post fails
            error = str(e)
    else:
        error = "BOT_TOKEN, CHANNEL_ID or MINI_APP_LINK is not set, so no channel post was made."
    posted = now()
    expires_at = posted + timedelta(hours=expires_hours)
    db.quizzes.update_one(
        {"_id": quiz["_id"]},
        {
            "$set": {
                "status": "live",
                "posted_at": posted,
                "expires_at": expires_at,
                "expires_hours": expires_hours,
                "notified": notified,
                "notify_error": error,
            }
        },
    )
    return {"notified": notified, "error": error}


def publish_due(db) -> int:
    count = 0
    current_time = now()

    # 1. Recover any quizzes stuck in "publishing" for more than 3 minutes
    stuck_time = current_time - timedelta(minutes=3)
    db.quizzes.update_many(
        {
            "status": "publishing",
            "$or": [
                {"publishing_started_at": {"$lte": stuck_time}},
                {"scheduled_at": {"$lte": stuck_time}},
                {"created_at": {"$lte": stuck_time}},
            ],
        },
        {"$set": {"status": "scheduled"}},
    )

    # 2. Find any scheduled quizzes that are due
    for q in list(db.quizzes.find({"status": "scheduled"})):
        sched = q.get("scheduled_at")
        if sched is None:
            continue
        if isinstance(sched, str):
            try:
                sched = datetime.fromisoformat(sched.replace("Z", "+00:00"))
            except Exception:
                continue
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)

        if sched <= current_time:
            claimed = db.quizzes.find_one_and_update(
                {"_id": q["_id"], "status": "scheduled"},
                {"$set": {"status": "publishing", "publishing_started_at": current_time}},
            )
            if claimed:
                publish_quiz(db, claimed)
                count += 1
    return count


def announce_winners(db, force_day: Optional[str] = None) -> list:
    """Post a winner card for finished days or a specified day."""
    done = []
    today = now()
    days = [force_day] if force_day else [day_key(today - timedelta(days=back)) for back in range(1, 4)]

    for key in days:
        if not key:
            continue
        if not force_day and db.winners.find_one({"_id": key, "status": "sent"}):
            continue
        rows = board_for_day(db, key)
        if not rows or not telegram.configured():
            continue
        db.winners.update_one(
            {"_id": key}, {"$setOnInsert": {"status": "pending", "lock_until": datetime(1970, 1, 1, tzinfo=timezone.utc), "attempts": 0}}, upsert=True
        )
        claim = db.winners.find_one_and_update(
            {"_id": key, "status": "pending", "attempts": {"$lt": 5}, "lock_until": {"$lt": now()}},
            {"$set": {"lock_until": now() + timedelta(minutes=3)}, "$inc": {"attempts": 1}},
        )
        if not claim and not force_day:
            continue
        try:
            w = rows[0]
            photo = telegram.profile_photo(w["user_id"], w.get("photo_url"))
            label = datetime.strptime(key, "%Y-%m-%d").strftime("%A, %d %B %Y")
            png = build_card(w["name"], w["points"], w["time_ms"], label, photo, config.env("CHANNEL_HANDLE"))
            medals = ["2nd", "3rd"]
            runners = "".join(f"\n{medals[i]}: {r['name']} ({r['points']} pts)" for i, r in enumerate(rows[1:3]))
            caption = (
                f"Quiz champion for {label}\n\n"
                f"{w['name']} won with {w['points']} points in {fmt_time(w['time_ms'])}.{runners}\n\n"
                f"A fresh leaderboard is open now. Come and take the top spot."
            )
            telegram.send_photo(png, caption, "Play today's quiz", config.mini_app_link() or "https://t.me")
            db.winners.update_one({"_id": key}, {"$set": {"status": "sent", "winner_id": w["user_id"], "sent_at": now(), "last_error": None}})
            done.append(key)
        except Exception as e:
            db.winners.update_one({"_id": key}, {"$set": {"last_error": str(e)}})
    return done
