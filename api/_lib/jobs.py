"""Helpers for manually publishing quizzes from the admin interface."""
from datetime import timedelta

from . import config, telegram
from .leaderboard import now


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
