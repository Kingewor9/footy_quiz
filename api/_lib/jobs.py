"""Helpers for manually publishing quizzes from the admin interface."""
from datetime import timedelta

from . import config, telegram
from .leaderboard import next_reset, now


def publish_quiz(db, quiz: dict) -> dict:
    """Mark a quiz live and post the channel notification. Returns {notified, error}."""
    notified, error = False, None
    posted = now()
    channel = db.channels.find_one({"_id": quiz.get("channel_id")}) if quiz.get("channel_id") else None
    chat_id = str(channel["_id"]) if channel else None
    posting_configured = (bool(config.bot_token()) and bool(channel)) if quiz.get("channel_id") else telegram.configured()
    if posting_configured and config.mini_app_link():
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
                f"Hit the <b>Play Now</b> button below to start!\n\n"
                f"{telegram.watermark_html()}"
            )
            if channel:
                text = text.replace(
                    "<b>New Quiz Available</b>",
                    f"<b>New Quiz Available · {channel['title']}</b>",
                )
            button_label = "Play now"
            kwargs = {
                "caption": text,
                "button_text": button_label,
                "url": telegram.quiz_link(quiz["_id"]),
                "image_url": config.quiz_notification_image_url(),
            }
            if channel:
                kwargs["chat_id"] = chat_id
            msg = telegram.send_quiz_notification(**kwargs)
            notified = True
            db.quizzes.update_one({"_id": quiz["_id"]}, {"$set": {"channel_message_id": msg["message_id"]}})
        except Exception as e:  # keep the quiz live even if the post fails
            error = str(e)
    else:
        error = "Bot token, connected channel or MINI_APP_LINK is not set, so no channel post was made."
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
