import base64
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from pymongo.errors import DuplicateKeyError

from . import config, jobs, telegram
from .auth import admin_user, current_user
from .db import db
from .grading import grade, public_question
from .leaderboard import board_for_day, day_key, next_reset, now
from .models import ChannelIn, QuizIn, SubmitIn, WinnerCardActionIn
from .winner_card import build_card, fmt_time

app = FastAPI(title="Footy Quiz API")
router = APIRouter(prefix="/api")

DEFAULT_MAX_SECONDS = 60
SUBMIT_GRACE_SECONDS = 5


def iso(dt):
    return dt.isoformat() if dt else None


def snapshot(user: dict) -> dict:
    return {k: user.get(k) for k in ("id", "name", "username", "photo_url")}


def is_quiz_expired(q: dict) -> bool:
    if not q or q.get("status") != "live":
        return True
    posted = q.get("posted_at")
    if isinstance(posted, str):
        try:
            posted = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        except ValueError:
            return True
    if not isinstance(posted, datetime):
        return True
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return next_reset(posted) <= now()


def get_live_quiz(d, qid: str) -> dict:
    q = d.quizzes.find_one({"_id": qid, "status": "live"})
    if not q or is_quiz_expired(q):
        raise HTTPException(404, "This quiz is not available any more.")
    return q


def result_payload(d, quiz: dict, attempt: dict) -> dict:
    channel_id = quiz.get("channel_id")
    rows = board_for_day(d, attempt["day_key"], channel_id)
    mine = next((r for r in rows if r["user_id"] == attempt["user_id"]), None)
    return {
        "quiz_id": quiz["_id"],
        "title": quiz["title"],
        "points": attempt["points"],
        "max_points": sum(q["points"] for q in quiz["questions"]),
        "correct_count": sum(1 for r in attempt["results"] if r["correct"]),
        "total": len(quiz["questions"]),
        "time_ms": attempt["time_ms"],
        "results": attempt["results"],
        "rank": mine["rank"] if mine else None,
        "players": len(rows),
        "boosted": bool(attempt.get("boosted", False)),
    }


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    d = db()
    d.users.update_one(
        {"_id": user["id"]},
        {"$set": {**snapshot(user), "last_seen": now()}, "$setOnInsert": {"first_seen": now()}},
        upsert=True,
    )
    rows = board_for_day(d, day_key(now()))
    mine = next((r for r in rows if r["user_id"] == user["id"]), None)
    channel_ids = d.attempts.distinct(
        "channel_id",
        {"user_id": user["id"], "day_key": day_key(now()), "submitted_at": {"$ne": None}, "channel_id": {"$ne": None}},
    )
    return {
        "user": snapshot(user),
        "is_admin": user["is_admin"],
        "today": {
            "points": mine["points"] if mine else 0,
            "channels": len(channel_ids),
            "rank": mine["rank"] if mine else None,
            "players": len(rows),
        },
    }


@router.get("/quizzes")
def live_quizzes(user: dict = Depends(current_user)):
    d = db()
    all_live = list(d.quizzes.find({"status": "live"}).sort("posted_at", -1))
    quizzes = [q for q in all_live if not is_quiz_expired(q)]
    mine = {a["quiz_id"]: a for a in d.attempts.find({"user_id": user["id"], "quiz_id": {"$in": [q["_id"] for q in quizzes]}})}
    out = []
    for q in quizzes:
        a = mine.get(q["_id"])
        done = bool(a and a.get("submitted_at"))
        out.append(
            {
                "id": q["_id"],
                "title": q["title"],
                "question_count": len(q["questions"]),
                "total_points": sum(x["points"] for x in q["questions"]),
                "max_seconds": q.get("max_seconds", DEFAULT_MAX_SECONDS),
                "posted_at": iso(q["posted_at"]),
                "played": done,
                "score": a["points"] if done else None,
                "channel_id": q.get("channel_id"),
                "channel_name": (d.channels.find_one({"_id": q.get("channel_id")}) or {}).get("title") if q.get("channel_id") else None,
            }
        )
    return out


@router.post("/quizzes/{qid}/start")
def start_quiz(qid: str, user: dict = Depends(current_user)):
    d = db()
    quiz = get_live_quiz(d, qid)
    attempt = d.attempts.find_one({"quiz_id": qid, "user_id": user["id"]})
    if attempt and attempt.get("submitted_at"):
        raise HTTPException(409, "already_played")
    if not attempt:
        attempt = {
            "_id": uuid.uuid4().hex,
            "quiz_id": qid,
            "user_id": user["id"],
            "user": snapshot(user),
            "started_at": now(),
            "submitted_at": None,
            "day_key": None,
            "channel_id": quiz.get("channel_id"),
        }
        try:
            d.attempts.insert_one(attempt)
        except DuplicateKeyError:
            attempt = d.attempts.find_one({"quiz_id": qid, "user_id": user["id"]})
            if attempt.get("submitted_at"):
                raise HTTPException(409, "already_played")
    elapsed = int((now() - attempt["started_at"]).total_seconds() * 1000)
    return {
        "id": quiz["_id"],
        "title": quiz["title"],
        "questions": [public_question(q) for q in quiz["questions"]],
        "max_seconds": quiz.get("max_seconds", DEFAULT_MAX_SECONDS),
        "elapsed_ms": max(0, elapsed),
    }


@router.post("/quizzes/{qid}/submit")
def submit_quiz(qid: str, body: SubmitIn, user: dict = Depends(current_user)):
    d = db()
    quiz = get_live_quiz(d, qid)
    attempt = d.attempts.find_one({"quiz_id": qid, "user_id": user["id"]})
    if not attempt:
        raise HTTPException(404, "Quiz not found. Start it first.")
    if attempt.get("submitted_at"):
        raise HTTPException(409, "already_played")
    max_seconds = quiz.get("max_seconds", DEFAULT_MAX_SECONDS)
    submitted = now()
    elapsed_seconds = max(0, (submitted - attempt["started_at"]).total_seconds())
    if elapsed_seconds > max_seconds + SUBMIT_GRACE_SECONDS:
        raise HTTPException(409, "Time limit expired before your answers could be submitted.")
    results, points = [], 0
    for q in quiz["questions"]:
        g = grade(q, body.answers.get(q["id"], ""))
        earned = q["points"] if g["correct"] else 0
        points += earned
        results.append({"id": q["id"], "text": q["text"], "points": earned, "max": q["points"], **g})
    time_ms = min(max_seconds, math.ceil(elapsed_seconds)) * 1000  # measured by the server in whole seconds
    claimed = d.attempts.find_one_and_update(
        {"_id": attempt["_id"], "submitted_at": None},
        {"$set": {"submitted_at": submitted, "day_key": day_key(submitted), "points": points, "time_ms": time_ms, "results": results, "user": snapshot(user)}},
        return_document=True,
    )
    if not claimed:
        raise HTTPException(409, "already_played")
    return result_payload(d, quiz, claimed)


@router.get("/quizzes/{qid}/result")
def quiz_result(qid: str, user: dict = Depends(current_user)):
    d = db()
    quiz = d.quizzes.find_one({"_id": qid})
    attempt = d.attempts.find_one({"quiz_id": qid, "user_id": user["id"], "submitted_at": {"$ne": None}})
    if not quiz or not attempt:
        raise HTTPException(404, "No result yet for this quiz.")
    return result_payload(d, quiz, attempt)


@router.post("/quizzes/{qid}/boost")
def boost_quiz(qid: str, user: dict = Depends(current_user)):
    d = db()
    quiz = d.quizzes.find_one({"_id": qid})
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    if is_quiz_expired(quiz):
        raise HTTPException(409, "This quiz has closed for the day.")
    attempt = d.attempts.find_one({"quiz_id": qid, "user_id": user["id"], "submitted_at": {"$ne": None}})
    if not attempt:
        raise HTTPException(404, "You haven't completed this quiz yet.")
    if attempt.get("boosted"):
        raise HTTPException(409, "Booster has already been used for this quiz.")

    base_points = attempt["points"]
    new_points = base_points * 2
    claimed = d.attempts.find_one_and_update(
        {"_id": attempt["_id"], "boosted": {"$ne": True}},
        {"$set": {"points": new_points, "boosted": True, "boosted_at": now(), "base_points": base_points}},
        return_document=True,
    )
    if not claimed:
        raise HTTPException(409, "Booster has already been used for this quiz.")
    return result_payload(d, quiz, claimed)


@router.get("/leaderboard")
def leaderboard(day: Optional[str] = Query(None), user: dict = Depends(current_user)):
    d = db()
    n = now()
    key = day or day_key(n)
    rows = board_for_day(d, key)
    mine = next((r for r in rows if r["user_id"] == user["id"]), None)
    return {
        "day": key,
        "is_today": key == day_key(n),
        "resets_at": iso(next_reset(n)),
        "rows": rows[:100],
        "me": mine,
        "players": len(rows),
    }


def channel_admin(d, user: dict, channel_id: str) -> dict:
    channel = d.channels.find_one({"_id": str(channel_id)})
    if not channel:
        raise HTTPException(404, "Connected channel not found.")
    if channel.get("owner_id") != user["id"] and user["id"] not in channel.get("admin_ids", []):
        raise HTTPException(403, "You must connect this channel as an administrator before managing it.")
    return channel


@router.get("/channels")
def member_channels(user: dict = Depends(current_user)):
    d = db()
    key = day_key(now())
    channel_ids = d.attempts.distinct(
        "channel_id",
        {"user_id": user["id"], "day_key": key, "submitted_at": {"$ne": None}, "channel_id": {"$ne": None}},
    )
    out = []
    for channel_id in channel_ids:
        channel = d.channels.find_one({"_id": channel_id})
        if not channel:
            continue
        rows = board_for_day(d, key, channel_id)
        mine = next((r for r in rows if r["user_id"] == user["id"]), None)
        out.append({
            "id": channel_id,
            "title": channel["title"],
            "username": channel.get("username"),
            "logo_url": channel_logo_url(channel),
            "rank": mine["rank"] if mine else None,
            "points": mine["points"] if mine else 0,
            "players": len(rows),
        })
    return sorted(out, key=lambda x: (x["title"] or "").casefold())


@router.get("/channels/{channel_id}/leaderboard")
def channel_leaderboard(channel_id: str, day: Optional[str] = Query(None), user: dict = Depends(current_user)):
    d = db()
    channel = d.channels.find_one({"_id": str(channel_id)})
    if not channel:
        raise HTTPException(404, "Channel not found.")
    n = now()
    key = day or day_key(n)
    rows = board_for_day(d, key, str(channel_id))
    mine = next((r for r in rows if r["user_id"] == user["id"]), None)
    return {
        "day": key,
        "is_today": key == day_key(n),
        "resets_at": iso(next_reset(n)),
        "rows": rows[:100],
        "me": mine,
        "players": len(rows),
        "channel": {
            "id": str(channel_id),
            "title": channel["title"],
            "username": channel.get("username"),
            "logo_url": channel_logo_url(channel),
        },
    }


def channel_logo_url(channel: dict) -> Optional[str]:
    return f"/api/channels/{channel['_id']}/logo" if channel.get("photo_file_id") else None


@router.get("/channels/{channel_id}/logo")
def channel_logo(channel_id: str):
    channel = db().channels.find_one({"_id": str(channel_id)})
    if not channel or not channel.get("photo_file_id"):
        raise HTTPException(404, "Channel logo not available.")
    try:
        image = telegram.file_bytes(channel["photo_file_id"])
    except Exception as e:
        raise HTTPException(502, f"Could not load the Telegram channel logo: {e}")
    if not image:
        raise HTTPException(404, "Channel logo not available.")
    content, mime = image
    return Response(content=content, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/admin/channels/lookup")
def lookup_channel(username: str = Query(..., min_length=2, max_length=64), user: dict = Depends(current_user)):
    handle = username.strip().removeprefix("@")
    if not (5 <= len(handle) <= 32) or not handle.isascii() or not handle.replace("_", "").isalnum():
        raise HTTPException(400, "Enter a public channel username.")
    try:
        chat = telegram.get_chat(f"@{handle}")
    except Exception as e:
        raise HTTPException(400, f"Telegram could not find that public channel: {e}")
    if chat.get("type") != "channel":
        raise HTTPException(400, "That username does not belong to a Telegram channel.")
    bot = telegram.get_me()
    return {
        "id": str(chat["id"]),
        "title": chat.get("title", handle),
        "username": chat.get("username", handle),
        "bot_username": bot.get("username"),
    }


@router.post("/admin/channels")
def connect_channel(body: ChannelIn, user: dict = Depends(current_user)):
    d = db()
    handle = body.username.strip().removeprefix("@")
    if not (5 <= len(handle) <= 32) or not handle.isascii() or not handle.replace("_", "").isalnum():
        raise HTTPException(400, "Enter a public channel username.")
    try:
        chat = telegram.get_chat(f"@{handle}")
        verified = telegram.verify_channel_access(str(chat["id"]), user["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Could not verify channel permissions: {e}")
    channel_id = str(verified["id"])
    existing = d.channels.find_one({"_id": channel_id})
    if existing:
        if existing.get("owner_id") == user["id"] or user["id"] in existing.get("admin_ids", []):
            migrated_quizzes = migrate_legacy_channel_data(d, existing, verified)
            return {
                "id": channel_id,
                "title": existing["title"],
                "username": existing.get("username"),
                "already_connected": True,
                "migrated_quizzes": migrated_quizzes,
            }
        d.channels.update_one({"_id": channel_id}, {"$addToSet": {"admin_ids": user["id"]}})
        migrated_quizzes = migrate_legacy_channel_data(d, existing, verified)
        return {
            "id": channel_id,
            "title": existing["title"],
            "username": existing.get("username"),
            "already_connected": False,
            "migrated_quizzes": migrated_quizzes,
        }
    channel = {
        "_id": channel_id,
        "title": verified.get("title", handle),
        "username": verified.get("username", handle),
        "photo_file_id": (verified.get("photo") or {}).get("big_file_id"),
        "owner_id": user["id"],
        "admin_ids": [user["id"]],
        "created_at": now(),
    }
    d.channels.insert_one(channel)
    migrated_quizzes = migrate_legacy_channel_data(d, channel, verified)
    return {
        "id": channel_id,
        "title": channel["title"],
        "username": channel["username"],
        "already_connected": False,
        "migrated_quizzes": migrated_quizzes,
    }


def migrate_legacy_channel_data(d, channel: dict, chat: dict) -> int:
    """Attach the old single-channel records when that configured channel is connected."""
    legacy_id = config.channel_id()
    legacy_handle = f"@{chat.get('username', '')}"
    if not legacy_id or not (
        legacy_id == str(chat["id"]) or legacy_id.casefold() == legacy_handle.casefold()
    ):
        return 0
    legacy_quizzes = list(d.quizzes.find({"channel_id": None}, {"_id": 1}))
    quiz_ids = [q["_id"] for q in legacy_quizzes]
    updated_count = 0
    if quiz_ids:
        updated = d.quizzes.update_many(
            {"_id": {"$in": quiz_ids}, "channel_id": None},
            {"$set": {"channel_id": channel["_id"]}},
        )
        d.attempts.update_many(
            {"quiz_id": {"$in": quiz_ids}, "channel_id": None},
            {"$set": {"channel_id": channel["_id"]}},
        )
        updated_count = updated.modified_count
    for winner in d.winners.find({"channel_id": None}):
        day = winner.get("day", winner.get("_id"))
        try:
            if datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") != day:
                continue
        except (TypeError, ValueError):
            continue
        migrated = {**winner, "_id": f"{channel['_id']}:{day}", "channel_id": channel["_id"]}
        d.winners.update_one(
            {"_id": migrated["_id"]},
            {"$setOnInsert": migrated},
            upsert=True,
        )
    return updated_count


@router.get("/admin/channels")
def admin_channels(user: dict = Depends(current_user)):
    d = db()
    channels = d.channels.find({"$or": [{"owner_id": user["id"]}, {"admin_ids": user["id"]}]}).sort("title", 1)
    return [
        {"id": c["_id"], "title": c["title"], "username": c.get("username"), "logo_url": channel_logo_url(c)}
        for c in channels
    ]


# ---------------------------------------------------------------- admin
@router.post("/admin/quizzes")
def create_quiz(body: QuizIn, user: dict = Depends(current_user)):
    d = db()
    channel = channel_admin(d, user, body.channel_id) if body.channel_id else None
    if not channel and not user["is_admin"]:
        raise HTTPException(403, "Connect a channel before creating quizzes.")
    questions = [{**q.model_dump(), "id": uuid.uuid4().hex[:8]} for q in body.questions]
    is_draft = body.status == "draft"
    quiz = {
        "_id": uuid.uuid4().hex[:10],
        "title": body.title.strip(),
        "questions": questions,
        "max_seconds": body.max_seconds,
        "created_by": user["id"],
        "channel_id": channel["_id"] if channel else None,
        "created_at": now(),
        "status": "draft" if is_draft else "publishing",
        "posted_at": None,
        "expires_at": None,
    }
    if is_draft:
        d.quizzes.insert_one(quiz)
        return {"id": quiz["_id"], "status": "draft", "notified": False, "error": None}

    d.quizzes.insert_one(quiz)
    outcome = jobs.publish_quiz(d, quiz)
    return {"id": quiz["_id"], "status": "live", **outcome}


@router.post("/admin/quizzes/{qid}/publish")
def publish_draft_quiz(qid: str, user: dict = Depends(current_user)):
    d = db()
    existing = d.quizzes.find_one({"_id": qid})
    if not existing:
        raise HTTPException(404, "Quiz not found.")
    if existing.get("channel_id"):
        channel_admin(d, user, existing["channel_id"])
    elif not user["is_admin"]:
        raise HTTPException(403, "Admins only.")
    q = d.quizzes.find_one_and_update(
        {"_id": qid, "status": {"$in": ["draft", "scheduled"]}},
        {"$set": {"status": "publishing", "publishing_started_at": now()}},
    )
    if not q:
        existing = d.quizzes.find_one({"_id": qid})
        if not existing:
            raise HTTPException(404, "Quiz not found.")
        if existing.get("status") == "publishing":
            raise HTTPException(409, "Quiz is already being published.")
        if existing.get("status") == "live":
            raise HTTPException(409, "Quiz is already live.")
        raise HTTPException(400, f"Cannot publish quiz with status '{existing.get('status')}'.")
    outcome = jobs.publish_quiz(d, q)
    return {"id": qid, "status": "live", **outcome}


@router.get("/admin/quizzes")
def admin_quizzes(channel_id: Optional[str] = Query(None), user: dict = Depends(current_user)):
    d = db()
    if channel_id:
        channel_admin(d, user, channel_id)
        query = {"channel_id": str(channel_id), "status": {"$ne": "cancelled"}}
    else:
        if not user["is_admin"]:
            raise HTTPException(403, "Admins only.")
        query = {"status": {"$ne": "cancelled"}}
    out = []
    for q in d.quizzes.find(query).sort("created_at", -1).limit(20):
        out.append(
            {
                "id": q["_id"],
                "title": q["title"],
                "status": q["status"],
                "question_count": len(q["questions"]),
                "max_seconds": q.get("max_seconds", DEFAULT_MAX_SECONDS),
                "posted_at": iso(q.get("posted_at")),
                "players": d.attempts.count_documents({"quiz_id": q["_id"], "submitted_at": {"$ne": None}}),
                "notify_error": q.get("notify_error"),
            }
        )
    return out


@router.delete("/admin/quizzes/{qid}")
def cancel_quiz(qid: str, user: dict = Depends(current_user)):
    d = db()
    quiz = d.quizzes.find_one({"_id": qid})
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    if quiz.get("channel_id"):
        channel_admin(d, user, quiz["channel_id"])
    elif not user["is_admin"]:
        raise HTTPException(403, "Admins only.")
    r = d.quizzes.update_one({"_id": qid, "status": {"$in": ["scheduled", "draft"]}}, {"$set": {"status": "cancelled"}})
    if not r.modified_count:
        raise HTTPException(400, "Only draft or scheduled quizzes can be cancelled.")
    return {"ok": True}


@router.get("/admin/analytics")
def analytics(user: dict = Depends(admin_user)):
    d = db()
    n = now()
    today = day_key(n)
    keys = [day_key(n - timedelta(days=i)) for i in range(6, -1, -1)]
    atts = list(d.attempts.find({"day_key": {"$in": keys}, "submitted_at": {"$ne": None}}))
    daily = [
        {
            "day": k,
            "players": len({a["user_id"] for a in atts if a["day_key"] == k}),
            "plays": sum(1 for a in atts if a["day_key"] == k),
        }
        for k in keys
    ]
    quizzes = []
    for q in d.quizzes.find({"status": "live"}).sort("posted_at", -1).limit(10):
        started = d.attempts.count_documents({"quiz_id": q["_id"]})
        done = list(d.attempts.find({"quiz_id": q["_id"], "submitted_at": {"$ne": None}}))
        mx = sum(x["points"] for x in q["questions"]) or 1
        quizzes.append(
            {
                "id": q["_id"],
                "title": q["title"],
                "started": started,
                "players": len(done),
                "avg_score_pct": round(100 * sum(a["points"] for a in done) / mx / len(done)) if done else 0,
                "avg_time_ms": round(sum(a["time_ms"] for a in done) / len(done)) if done else 0,
                "completion_pct": round(100 * len(done) / started) if started else 0,
            }
        )
    return {
        "total_players": d.users.count_documents({}),
        "players_today": next(x["players"] for x in daily if x["day"] == today),
        "plays_today": next(x["plays"] for x in daily if x["day"] == today),
        "quizzes_live": d.quizzes.count_documents({"status": "live"}),
        "channels_connected": d.channels.count_documents({}),
        "daily": daily,
        "quizzes": quizzes,
    }


# ---------------------------------------------------------------- winner card management
def concluded_day_label(day: str) -> str:
    try:
        parsed_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Invalid day format. Expected YYYY-MM-DD.")
    if parsed_day.isoformat() != day:
        raise HTTPException(400, "Invalid day format. Expected YYYY-MM-DD.")
    if parsed_day >= now().astimezone(config.app_tz()).date():
        raise HTTPException(400, "Winner announcements are only available for concluded days.")
    return parsed_day.strftime("%A, %d %B %Y")


def make_winner_caption(w: dict, rows: list, label: str) -> str:
    medals = ["2nd", "3rd"]
    runners = "".join(f"\n{medals[i]}: {r['name']} ({r['points']} pts)" for i, r in enumerate(rows[1:3]))
    return (
        f"Quiz champion for {label}\n\n"
        f"{w['name']} won with {w['points']} points in {fmt_time(w['time_ms'])}.{runners}\n\n"
        f"A fresh leaderboard is open now. Come and take the top spot.\n\n"
        f"Powered By Footy Quiz"
    )


def add_notification_watermark(caption: str) -> str:
    caption = caption.rstrip()
    if caption.casefold().endswith("powered by footy quiz"):
        return caption
    return f"{caption}\n\nPowered By Footy Quiz"


def winner_scope(d, user: dict, channel_id: Optional[str]):
    if channel_id:
        channel = channel_admin(d, user, channel_id)
        return channel, f"{channel_id}:"
    if not user["is_admin"]:
        raise HTTPException(403, "Admins only.")
    return None, ""


@router.get("/admin/winner-card/days")
def admin_winner_days(channel_id: Optional[str] = Query(None), user: dict = Depends(current_user)):
    d = db()
    channel, prefix = winner_scope(d, user, channel_id)
    n = now()
    days = []
    # Concluded days: 1 to 7 days back
    for back in range(1, 8):
        dt = n - timedelta(days=back)
        k = day_key(dt)
        lbl = dt.astimezone(config.app_tz()).strftime("%A, %d %b %Y")
        record_id = f"{prefix}{k}"
        rec = d.winners.find_one({"_id": record_id})
        query = {"day_key": k, "submitted_at": {"$ne": None}}
        if channel:
            query["channel_id"] = channel["_id"]
        count = d.attempts.count_documents(query)
        status = rec.get("status") if rec and rec.get("status") in ("sent", "draft") else ("unsent" if count > 0 else "no_plays")
        days.append({
            "day": k,
            "label": lbl,
            "status": status,
            "players": count,
            "sent_at": iso(rec.get("sent_at")) if rec else None,
        })
    return days


@router.get("/admin/winner-card")
def admin_winner_card(day: Optional[str] = Query(None), channel_id: Optional[str] = Query(None), user: dict = Depends(current_user)):
    d = db()
    channel, prefix = winner_scope(d, user, channel_id)
    target_day = day or day_key(now() - timedelta(days=1))
    label = concluded_day_label(target_day)

    rows = board_for_day(d, target_day, channel["_id"] if channel else None)
    record_id = f"{prefix}{target_day}"
    existing = d.winners.find_one({"_id": record_id})
    status = existing.get("status") if existing else "ready"
    if status not in ("draft", "sent"):
        status = "ready"
    sent_at = existing.get("sent_at") if existing else None

    if not rows:
        return {
            "day": target_day,
            "day_label": label,
            "has_data": False,
            "players": 0,
            "winner": None,
            "second": None,
            "third": None,
            "caption": "",
            "card_image": None,
            "status": "none",
            "sent_at": iso(sent_at),
            "message": f"No quiz attempts recorded for {label}.",
        }

    w = rows[0]
    second = rows[1] if len(rows) > 1 else None
    third = rows[2] if len(rows) > 2 else None
    default_caption = make_winner_caption(w, rows, label)
    caption = (existing.get("caption") if existing and existing.get("caption") else default_caption)

    # Generate the winner card PNG and base64 preview
    photo = telegram.profile_photo(w["user_id"], w.get("photo_url"))
    card_channel = channel.get("username") if channel else config.env("CHANNEL_HANDLE")
    png = build_card(w["name"], w["points"], w["time_ms"], label, photo, card_channel)
    b64_img = f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"

    return {
        "day": target_day,
        "channel_name": channel["title"] if channel else None,
        "day_label": label,
        "has_data": True,
        "players": len(rows),
        "winner": {"user_id": w["user_id"], "name": w["name"], "points": w["points"], "time_ms": w["time_ms"], "photo_url": w.get("photo_url")},
        "second": {"user_id": second["user_id"], "name": second["name"], "points": second["points"], "time_ms": second["time_ms"]} if second else None,
        "third": {"user_id": third["user_id"], "name": third["name"], "points": third["points"], "time_ms": third["time_ms"]} if third else None,
        "caption": caption,
        "card_image": b64_img,
        "status": status,
        "sent_at": iso(sent_at),
    }


@router.post("/admin/winner-card/save-draft")
def admin_save_winner_draft(body: WinnerCardActionIn, user: dict = Depends(current_user)):
    d = db()
    channel, prefix = winner_scope(d, user, body.channel_id)
    label = concluded_day_label(body.day)
    rows = board_for_day(d, body.day, channel["_id"] if channel else None)
    if not rows:
        raise HTTPException(400, f"No attempts recorded for {body.day}.")
    record_id = f"{prefix}{body.day}"
    existing = d.winners.find_one({"_id": record_id})
    if existing and existing.get("status") in ("sent", "posting"):
        raise HTTPException(409, "This winner announcement has already been posted or is being posted.")
    caption = add_notification_watermark(body.caption.strip() if body.caption else make_winner_caption(rows[0], rows, label))
    d.winners.update_one(
        {"_id": record_id},
        {
            "$set": {
                "day": body.day,
                "channel_id": channel["_id"] if channel else None,
                "status": "draft",
                "caption": caption,
                "winner_id": rows[0]["user_id"],
                "updated_at": now(),
            },
            "$setOnInsert": {"created_at": now()},
        },
        upsert=True,
    )
    return {"ok": True, "day": body.day, "status": "draft"}


@router.post("/admin/winner-card/post")
def admin_post_winner_card(body: WinnerCardActionIn, user: dict = Depends(current_user)):
    d = db()
    channel, prefix = winner_scope(d, user, body.channel_id)
    label = concluded_day_label(body.day)
    rows = board_for_day(d, body.day, channel["_id"] if channel else None)
    if not rows:
        raise HTTPException(400, f"No attempts recorded for {body.day}.")
    if (channel and not config.bot_token()) or (not channel and not telegram.configured()):
        raise HTTPException(400, "Telegram bot is not configured (check BOT_TOKEN and CHANNEL_ID).")

    w = rows[0]
    caption = add_notification_watermark(body.caption.strip() if body.caption else make_winner_caption(w, rows, label))
    photo = telegram.profile_photo(w["user_id"], w.get("photo_url"))
    card_channel = channel.get("username") if channel else config.env("CHANNEL_HANDLE")
    png = build_card(w["name"], w["points"], w["time_ms"], label, photo, card_channel)
    record_id = f"{prefix}{body.day}"

    d.winners.update_one(
        {"_id": record_id},
        {"$setOnInsert": {"day": body.day, "channel_id": channel["_id"] if channel else None, "status": "draft", "created_at": now()}},
        upsert=True,
    )
    claim = d.winners.update_one(
        {"_id": record_id, "status": {"$nin": ["sent", "posting"]}},
        {"$set": {"status": "posting", "caption": caption, "winner_id": w["user_id"], "updated_at": now()}},
    )
    if not claim.modified_count:
        raise HTTPException(409, "This winner announcement has already been posted or is being posted.")

    try:
        if channel:
            telegram.send_photo(png, caption, "Play today's quiz", config.mini_app_link() or "https://t.me", chat_id=channel["_id"])
        else:
            telegram.send_photo(png, caption, "Play today's quiz", config.mini_app_link() or "https://t.me")
    except Exception as e:
        d.winners.update_one(
            {"_id": record_id, "status": "posting"},
            {"$set": {"status": "draft", "last_error": str(e)}},
        )
        raise HTTPException(502, f"Failed posting to Telegram: {e}")

    sent_time = now()
    d.winners.update_one(
        {"_id": record_id},
        {
            "$set": {
                "day": body.day,
                "channel_id": channel["_id"] if channel else None,
                "status": "sent",
                "caption": caption,
                "winner_id": w["user_id"],
                "sent_at": sent_time,
                "last_error": None,
                "updated_at": sent_time,
            },
            "$setOnInsert": {"created_at": sent_time},
        },
        upsert=True,
    )
    return {"ok": True, "day": body.day, "status": "sent", "sent_at": iso(sent_time)}


app.include_router(router)
