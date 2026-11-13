"""Work triggered by the /api/cron/tick endpoint: publish scheduled quizzes, announce winners."""
from datetime import datetime, timedelta, timezone

from . import config, telegram
from .leaderboard import board_for_day, day_key, now
from .winner_card import build_card, fmt_time


def publish_quiz(db, quiz: dict) -> dict:
    """Mark a quiz live and post the channel notification. Returns {notified, error}."""
    notified, error = False, None
    if telegram.configured() and config.mini_app_link():
        try:
            total = sum(q["points"] for q in quiz["questions"])
            n = len(quiz["questions"])
            max_seconds = quiz.get("max_seconds", 60)
            title = quiz.get("title", "Matchday Quiz").strip()

            text = (
                f"🚨 <b>KICKOFF ALERT: {title.upper()} IS LIVE!</b> ⚽🔥\n\n"
                f"Think you've got elite football knowledge? It's time to lace up and prove it on the pitch! 🏆\n\n"
                f"⚡ <b>Match Intel:</b>\n"
                f"• <b>Fixtures:</b> {n} trivia challenge{'s' if n != 1 else ''}\n"
                f"• <b>Total Points:</b> Up to {total} PTS\n"
                f"• <b>Match Clock:</b> {max_seconds} seconds ⏱️\n"
                f"• <b>Power-Up:</b> ⚡ 2X Booster available to double your score!\n\n"
                f"🥇 <i>Climb to the top of today's leaderboard before the final whistle!</i>\n\n"
                f"👇 <b>Hit the button below to kickoff your match right now!</b>"
            )
            button_label = "⚽ PLAY NOW & WIN"
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
    db.quizzes.update_one(
        {"_id": quiz["_id"]},
        {"$set": {"status": "live", "posted_at": now(), "notified": notified, "notify_error": error}},
    )
    return {"notified": notified, "error": error}


def publish_due(db) -> int:
    count = 0
    for q in list(db.quizzes.find({"status": "scheduled", "scheduled_at": {"$lte": now()}})):
        claimed = db.quizzes.find_one_and_update({"_id": q["_id"], "status": "scheduled"}, {"$set": {"status": "publishing"}})
        if claimed:
            publish_quiz(db, claimed)
            count += 1
    return count


def announce_winners(db) -> list:
    """Post a winner card for each finished day (today excluded) that has not been announced."""
    done = []
    today = now()
    for back in range(1, 4):
        key = day_key(today - timedelta(days=back))
        if db.winners.find_one({"_id": key, "status": "sent"}):
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
        if not claim:
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
            db.winners.update_one({"_id": key}, {"$set": {"status": "sent", "winner_id": w["user_id"], "sent_at": now()}})
            done.append(key)
        except Exception as e:
            db.winners.update_one({"_id": key}, {"$set": {"last_error": str(e)}})
    return done
