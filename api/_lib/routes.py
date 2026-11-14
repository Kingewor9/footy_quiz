import asyncio
import hmac
import math
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from pymongo.errors import DuplicateKeyError

from . import config, jobs
from .auth import admin_user, current_user
from .db import db
from .grading import grade, public_question
from .leaderboard import board_for_day, day_key, next_reset, now
from .models import QuizIn, SubmitIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start continuous background worker that runs every 20 seconds while server is up
    stop_event = asyncio.Event()

    async def scheduler_worker():
        while not stop_event.is_set():
            try:
                d = db()
                jobs.publish_due(d)
                jobs.announce_winners(d)
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=20)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(scheduler_worker())
    yield
    stop_event.set()
    task.cancel()


app = FastAPI(title="Footy Quiz API", lifespan=lifespan)
router = APIRouter(prefix="/api")

DEFAULT_EXPIRES_HOURS = 24
DEFAULT_MAX_SECONDS = 60
SUBMIT_GRACE_SECONDS = 5


def iso(dt):
    return dt.isoformat() if dt else None


def snapshot(user: dict) -> dict:
    return {k: user.get(k) for k in ("id", "name", "username", "photo_url")}


def check_scheduler_passive(d):
    """Self-healing check on user requests so serverless instances also publish due quizzes immediately."""
    try:
        jobs.publish_due(d)
        jobs.announce_winners(d)
    except Exception:
        pass


def is_quiz_expired(q: dict) -> bool:
    if not q or q.get("status") != "live":
        return True
    if "expires_at" in q and q["expires_at"]:
        return q["expires_at"] <= now()
    hours = q.get("expires_hours", DEFAULT_EXPIRES_HOURS)
    posted = q.get("posted_at")
    return not posted or posted < now() - timedelta(hours=hours)


def get_live_quiz(d, qid: str) -> dict:
    q = d.quizzes.find_one({"_id": qid, "status": "live"})
    if not q or is_quiz_expired(q):
        raise HTTPException(404, "This quiz is not available any more.")
    return q


def result_payload(d, quiz: dict, attempt: dict) -> dict:
    rows = board_for_day(d, attempt["day_key"])
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
    check_scheduler_passive(d)
    d.users.update_one(
        {"_id": user["id"]},
        {"$set": {**snapshot(user), "last_seen": now()}, "$setOnInsert": {"first_seen": now()}},
        upsert=True,
    )
    rows = board_for_day(d, day_key(now()))
    mine = next((r for r in rows if r["user_id"] == user["id"]), None)
    return {
        "user": snapshot(user),
        "is_admin": user["is_admin"],
        "today": {"rank": mine["rank"] if mine else None, "points": mine["points"] if mine else 0, "players": len(rows)},
    }


@router.get("/quizzes")
def live_quizzes(user: dict = Depends(current_user)):
    d = db()
    check_scheduler_passive(d)
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
                "expires_hours": q.get("expires_hours", DEFAULT_EXPIRES_HOURS),
                "posted_at": iso(q["posted_at"]),
                "played": done,
                "score": a["points"] if done else None,
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
    quiz = d.quizzes.find_one({"_id": qid, "status": "live"})
    attempt = d.attempts.find_one({"quiz_id": qid, "user_id": user["id"]})
    if not quiz or not attempt:
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
    check_scheduler_passive(d)
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


# ---------------------------------------------------------------- admin
@router.post("/admin/quizzes")
def create_quiz(body: QuizIn, user: dict = Depends(admin_user)):
    d = db()
    questions = [{**q.model_dump(), "id": uuid.uuid4().hex[:8]} for q in body.questions]
    expires_hours = body.expires_hours or DEFAULT_EXPIRES_HOURS
    quiz = {
        "_id": uuid.uuid4().hex[:10],
        "title": body.title.strip(),
        "questions": questions,
        "max_seconds": body.max_seconds,
        "expires_hours": expires_hours,
        "created_by": user["id"],
        "created_at": now(),
        "scheduled_at": body.scheduled_at,
        "status": "scheduled",
        "posted_at": None,
        "expires_at": None,
    }
    later = body.scheduled_at and body.scheduled_at > now()
    d.quizzes.insert_one(quiz)
    if later:
        return {"id": quiz["_id"], "status": "scheduled", "scheduled_at": iso(body.scheduled_at), "notified": False, "error": None}
    outcome = jobs.publish_quiz(d, quiz)
    return {"id": quiz["_id"], "status": "live", **outcome}


@router.get("/admin/quizzes")
def admin_quizzes(user: dict = Depends(admin_user)):
    d = db()
    check_scheduler_passive(d)
    out = []
    for q in d.quizzes.find({"status": {"$ne": "cancelled"}}).sort("created_at", -1).limit(20):
        out.append(
            {
                "id": q["_id"],
                "title": q["title"],
                "status": q["status"],
                "question_count": len(q["questions"]),
                "max_seconds": q.get("max_seconds", DEFAULT_MAX_SECONDS),
                "expires_hours": q.get("expires_hours", DEFAULT_EXPIRES_HOURS),
                "scheduled_at": iso(q.get("scheduled_at")),
                "posted_at": iso(q.get("posted_at")),
                "players": d.attempts.count_documents({"quiz_id": q["_id"], "submitted_at": {"$ne": None}}),
                "notify_error": q.get("notify_error"),
            }
        )
    return out


@router.delete("/admin/quizzes/{qid}")
def cancel_quiz(qid: str, user: dict = Depends(admin_user)):
    r = db().quizzes.update_one({"_id": qid, "status": "scheduled"}, {"$set": {"status": "cancelled"}})
    if not r.modified_count:
        raise HTTPException(400, "Only scheduled quizzes can be cancelled.")
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
        "daily": daily,
        "quizzes": quizzes,
    }


# ---------------------------------------------------------------- scheduler hook
@router.get("/cron/tick")
def tick(
    authorization: Optional[str] = Header(None),
    key: Optional[str] = Query(None),
    x_vercel_cron: Optional[str] = Header(None),
):
    secret = config.cron_secret()
    given = (authorization or "").removeprefix("Bearer ").strip() or (key or "")
    is_authed = bool(x_vercel_cron) or (secret and hmac.compare_digest(given, secret))
    if not is_authed:
        raise HTTPException(401, "Bad cron secret.")
    d = db()
    return {"published": jobs.publish_due(d), "winners_announced": jobs.announce_winners(d)}


@router.post("/admin/scheduler/tick")
def admin_tick(force_today_winner: bool = Query(False), user: dict = Depends(admin_user)):
    d = db()
    published = jobs.publish_due(d)
    force_day = day_key(now()) if force_today_winner else None
    announced = jobs.announce_winners(d, force_day=force_day)
    last_error = None
    if force_day and not announced:
        rec = d.winners.find_one({"_id": force_day})
        if rec and rec.get("last_error"):
            last_error = rec["last_error"]
        elif not board_for_day(d, force_day):
            last_error = f"No quiz attempts found for {force_day}."
        elif not telegram.configured():
            last_error = "Telegram bot is not configured (check BOT_TOKEN and CHANNEL_ID)."
    return {
        "ok": True,
        "published": published,
        "winners_announced": announced,
        "error": last_error,
    }


app.include_router(router)
