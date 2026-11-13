import hashlib, hmac, json, os, sys, time
from datetime import timedelta
from urllib.parse import urlencode

os.environ.update(MONGODB_URI="mongomock://", DEV_MODE="1", ADMIN_IDS="1", CRON_SECRET="s3cret", APP_TZ="Africa/Lagos", BOT_TOKEN="123:ABC")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from fastapi.testclient import TestClient
from _lib import auth, jobs, routes, telegram
from _lib.db import db
from _lib.leaderboard import now
from _lib.routes import app
from _lib.winner_card import build_card

c = TestClient(app)


def H(uid, name="P"):
    return {"X-Dev-User": json.dumps({"id": uid, "first_name": name})}


QUIZ = {
    "title": "Matchday 1",
    "questions": [
        {"type": "poll", "text": "Who won the 2022 World Cup?", "options": ["France", "Argentina", "Brazil"], "correct_index": 1, "points": 10},
        {"type": "text", "text": "Capital of Spain's top club city?", "accepted": ["Madrid", "madrid fc"], "points": 20},
        {"type": "image", "text": "Name this stadium", "image_url": "https://x.test/a.jpg", "answer_mode": "options", "options": ["A", "B"], "correct_index": 0, "points": 5},
    ],
}


def play(uid, qid, answers):
    r = c.post(f"/api/quizzes/{qid}/start", headers=H(uid)); assert r.status_code == 200, r.text
    assert "correct_index" not in json.dumps(r.json())  # answers never reach the client
    qs = r.json()["questions"]
    body = {"answers": {qs[i]["id"]: a for i, a in enumerate(answers)}}
    return c.post(f"/api/quizzes/{qid}/submit", json=body, headers=H(uid))


def test_flow():
    assert c.post("/api/admin/quizzes", json=QUIZ, headers=H(2)).status_code == 403
    bad = dict(QUIZ, questions=[{"type": "poll", "text": "x", "options": ["a", "b"], "points": 5}])
    assert c.post("/api/admin/quizzes", json=bad, headers=H(1)).status_code == 422
    r = c.post("/api/admin/quizzes", json=QUIZ, headers=H(1)); assert r.status_code == 200
    qid = r.json()["id"]; assert r.json()["status"] == "live" and r.json()["notified"] is False
    assert len(c.get("/api/quizzes", headers=H(2)).json()) == 1

    r = play(2, qid, ["1", "Madrid!", "0"]); assert r.status_code == 200, r.text
    assert r.json()["points"] == 35 and r.json()["rank"] == 1
    assert c.post(f"/api/quizzes/{qid}/start", headers=H(2)).status_code == 409   # one play only
    assert play(3, qid, ["1", "wrong", "1"]).json()["points"] == 10
    assert play(4, qid, ["0", "", ""]).json()["points"] == 0

    lb = c.get("/api/leaderboard", headers=H(3)).json()
    assert [x["user_id"] for x in lb["rows"]] == [2, 3, 4] and lb["me"]["rank"] == 2
    assert c.get("/api/me", headers=H(3)).json()["today"] == {"rank": 2, "points": 10, "players": 3}

    # second quiz same day: points accumulate, movement shows
    q2 = c.post("/api/admin/quizzes", json={"title": "Q2", "questions": [QUIZ["questions"][0]]}, headers=H(1)).json()["id"]
    play(3, q2, ["1"]); play(2, q2, ["0"])
    # user 3 now has 20, user 2 has 35
    rows = {x["user_id"]: x for x in c.get("/api/leaderboard", headers=H(3)).json()["rows"]}
    assert rows[2]["points"] == 35 and rows[3]["points"] == 20 and rows[3]["rank"] == 2

    a = c.get("/api/admin/analytics", headers=H(1)).json()
    assert a["players_today"] == 3 and a["quizzes_live"] == 2
    assert c.get("/api/admin/analytics", headers=H(2)).status_code == 403


def test_quiz_time_limit_and_whole_second_timing(monkeypatch):
    assert c.post("/api/admin/quizzes", json=dict(QUIZ, max_seconds=0), headers=H(1)).status_code == 422
    r = c.post("/api/admin/quizzes", json=dict(QUIZ, max_seconds=5), headers=H(1))
    assert r.status_code == 200
    qid = r.json()["id"]
    started = c.post(f"/api/quizzes/{qid}/start", headers=H(20)).json()
    assert started["max_seconds"] == 5
    started_at = db().attempts.find_one({"quiz_id": qid, "user_id": 20})["started_at"]
    monkeypatch.setattr(routes, "now", lambda: started_at + timedelta(seconds=1.2))
    question_id = started["questions"][0]["id"]
    result = c.post(f"/api/quizzes/{qid}/submit", json={"answers": {question_id: "1"}}, headers=H(20))
    assert result.status_code == 200 and result.json()["time_ms"] == 2000

    r = c.post("/api/admin/quizzes", json=dict(QUIZ, max_seconds=1), headers=H(1))
    qid = r.json()["id"]
    c.post(f"/api/quizzes/{qid}/start", headers=H(21))
    started_at = db().attempts.find_one({"quiz_id": qid, "user_id": 21})["started_at"]
    monkeypatch.setattr(routes, "now", lambda: started_at + timedelta(seconds=7))
    result = c.post(f"/api/quizzes/{qid}/submit", json={"answers": {}}, headers=H(21))
    assert result.status_code == 409 and "Time limit expired" in result.json()["detail"]


def test_tie_break_by_time():
    d = db(); t = now()
    for uid, ms in [(10, 9100), (11, 9400)]:
        d.attempts.insert_one({"_id": f"t{uid}", "quiz_id": "tie", "user_id": uid, "user": {"id": uid, "name": f"U{uid}"}, "started_at": t,
                               "submitted_at": t, "day_key": "2000-01-01", "points": 50, "time_ms": ms, "results": []})
    rows = __import__("_lib.leaderboard", fromlist=["x"]).board_for_day(d, "2000-01-01")
    assert [r["time_ms"] for r in rows] == [10000, 10000]


def test_schedule_and_tick():
    later = (now() + timedelta(hours=1)).isoformat()
    r = c.post("/api/admin/quizzes", json=dict(QUIZ, title="Later", scheduled_at=later), headers=H(1)).json()
    assert r["status"] == "scheduled"
    assert c.get("/api/cron/tick").status_code == 401
    assert c.get("/api/cron/tick?key=s3cret").json()["published"] == 0
    db().quizzes.update_one({"_id": r["id"]}, {"$set": {"scheduled_at": now() - timedelta(minutes=1)}})
    assert c.get("/api/cron/tick", headers={"Authorization": "Bearer s3cret"}).json()["published"] == 1
    assert db().quizzes.find_one({"_id": r["id"]})["status"] == "live"


def test_winner_announcement(monkeypatch=None):
    d = db(); y = (now() - timedelta(days=1))
    from _lib.leaderboard import day_key
    key = day_key(y)
    d.attempts.insert_one({"_id": "w1", "quiz_id": "old", "user_id": 77, "user": {"id": 77, "name": "Samuel Eto'o", "username": "s"}, "started_at": y,
                           "submitted_at": y, "day_key": key, "points": 80, "time_ms": 61000, "results": []})
    sent = {}
    os.environ["CHANNEL_ID"] = "@chan"; os.environ["MINI_APP_LINK"] = "https://t.me/bot/app"
    telegram.profile_photo = lambda uid, url: None
    telegram.send_photo = lambda png, cap, bt, url: sent.update(png=png, cap=cap)
    assert jobs.announce_winners(d) == [key]
    assert sent["png"][:8] == b"\x89PNG\r\n\x1a\n" and "Samuel" in sent["cap"]
    assert jobs.announce_winners(d) == []   # never announced twice


def test_card_and_initdata(tmp_path):
    open(tmp_path / "card.png", "wb").write(build_card("Lionel Messi", 120, 83000, "Friday, 13 November 2026", None, "@footyriddles"))
    open("/tmp/card.png", "wb").write(build_card("Lionel Messi", 120, 83000, "Friday, 13 November 2026", None, "@footyriddles"))
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 5, "first_name": "Z"}), "query_id": "q"}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    sec = hmac.new(b"WebAppData", b"123:ABC", hashlib.sha256).digest()
    fields["hash"] = hmac.new(sec, check.encode(), hashlib.sha256).hexdigest()
    assert auth.validate_init_data(urlencode(fields), "123:ABC")["id"] == 5
    fields["hash"] = "0" * 64
    try:
        auth.validate_init_data(urlencode(fields), "123:ABC"); assert False
    except ValueError:
        pass
