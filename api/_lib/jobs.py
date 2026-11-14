"""Helpers for manually publishing quizzes from the admin interface."""
from datetime import timedelta

from . import config, telegram
from .leaderboard import next_reset, now


def publish_quiz(db, quiz: dict) -> dict:
    """Mark a quiz live and post the channel notification. Returns {notified, error}."""
    notified, error = False, None
    posted = now()
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
                f"<b>Available until:</b> 23:59 {posted.astimezone(config.app_tz()).strftime('%Z')}\n\n"
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
    expires_at = next_reset(posted)
    db.quizzes.update_one(
        {"_id": quiz["_id"]},
        {
            "$set": {
                "status": "live",
                "posted_at": posted,
                "expires_at": expires_at,
                "notified": notified,
                "notify_error": error,
            }
        },
    )
    return {"notified": notified, "error": error}
