import hashlib, hmac, json, os, sys, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

os.environ.update(MONGODB_URI="mongomock://", DEV_MODE="1", ADMIN_IDS="1", APP_TZ="Africa/Lagos", BOT_TOKEN="123:ABC")
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
    assert c.get("/api/me", headers=H(3)).json()["today"] == {"rank": 2, "points": 10, "players": 3, "channels": 0}

    # second quiz same day: points accumulate, movement shows
    q2 = c.post("/api/admin/quizzes", json={"title": "Q2", "questions": [QUIZ["questions"][0]]}, headers=H(1)).json()["id"]
    play(3, q2, ["1"]); play(2, q2, ["0"])
    # user 3 now has 20, user 2 has 35
    rows = {x["user_id"]: x for x in c.get("/api/leaderboard", headers=H(3)).json()["rows"]}
    assert rows[2]["points"] == 35 and rows[3]["points"] == 20 and rows[3]["rank"] == 2

    a = c.get("/api/admin/analytics", headers=H(1)).json()
    assert a["players_today"] == 3 and a["quizzes_live"] == 2
    assert c.get("/api/admin/analytics", headers=H(2)).status_code == 403


def test_booster_doubles_score():
    r = c.post("/api/admin/quizzes", json=QUIZ, headers=H(1))
    qid = r.json()["id"]
    res = play(50, qid, ["1", "Madrid!", "0"])
    assert res.status_code == 200
    assert res.json()["points"] == 35
    assert res.json().get("boosted") is False

    # Booster doubles score to 70 and sets boosted = True
    b = c.post(f"/api/quizzes/{qid}/boost", headers=H(50))
    assert b.status_code == 200
    assert b.json()["points"] == 70
    assert b.json()["boosted"] is True

    # Cannot boost twice
    b_again = c.post(f"/api/quizzes/{qid}/boost", headers=H(50))
    assert b_again.status_code == 409

    # Leaderboard reflects doubled points
    lb = c.get("/api/leaderboard", headers=H(50)).json()
    me_row = next(r for r in lb["rows"] if r["user_id"] == 50)
    assert me_row["points"] == 70

    # Cannot boost quiz not played
    assert c.post("/api/quizzes/invalid-id/boost", headers=H(50)).status_code == 404


def test_discover_channels_only_lists_connected_channels_with_live_quizzes_today(monkeypatch, request):
    current_time = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(routes, "now", lambda: current_time)
    d = db()
    quiz_ids = [f"discover-{name}" for name in ("alpha-1", "alpha-2", "beta-1", "stale-1", "draft-1", "unsent-1", "unconnected-1")]
    channel_ids = [f"discover-{name}" for name in ("alpha", "beta", "quiet", "stale", "draft", "unsent")]
    request.addfinalizer(lambda: d.quizzes.delete_many({"_id": {"$in": quiz_ids}}))
    request.addfinalizer(lambda: d.channels.delete_many({"_id": {"$in": channel_ids}}))
    d.channels.insert_many([
        {"_id": "discover-alpha", "title": "Alpha League", "username": "alphaleague"},
        {"_id": "discover-beta", "title": "Beta League", "username": "betaleague"},
        {"_id": "discover-quiet", "title": "Quiet League", "username": "quietleague"},
        {"_id": "discover-stale", "title": "Yesterday League", "username": "yesterdayleague"},
        {"_id": "discover-draft", "title": "Draft League", "username": "draftleague"},
        {"_id": "discover-unsent", "title": "Unsent League", "username": "unsentleague"},
    ])
    d.quizzes.insert_many([
        {"_id": "discover-alpha-1", "title": "Alpha 1", "questions": [], "channel_id": "discover-alpha", "status": "live", "notified": True, "channel_message_id": 1, "posted_at": current_time - timedelta(hours=1)},
        {"_id": "discover-alpha-2", "title": "Alpha 2", "questions": [], "channel_id": "discover-alpha", "status": "live", "notified": True, "channel_message_id": 2, "posted_at": current_time - timedelta(hours=2)},
        {"_id": "discover-beta-1", "title": "Beta 1", "questions": [], "channel_id": "discover-beta", "status": "live", "notified": True, "channel_message_id": 3, "posted_at": current_time - timedelta(hours=3)},
        {"_id": "discover-stale-1", "title": "Stale", "questions": [], "channel_id": "discover-stale", "status": "live", "notified": True, "channel_message_id": 4, "posted_at": current_time - timedelta(hours=13, minutes=1)},
        {"_id": "discover-draft-1", "title": "Draft", "questions": [], "channel_id": "discover-draft", "status": "draft", "notified": True, "channel_message_id": 5, "posted_at": current_time - timedelta(hours=1)},
        {"_id": "discover-unsent-1", "title": "Unsent", "questions": [], "channel_id": "discover-unsent", "status": "live", "notified": False, "posted_at": current_time - timedelta(hours=1)},
        {"_id": "discover-unconnected-1", "title": "Unconnected", "questions": [], "channel_id": "not-connected", "status": "live", "notified": True, "channel_message_id": 6, "posted_at": current_time - timedelta(hours=1)},
    ])

    response = c.get("/api/discover/channels", headers=H(800)).json()
    assert [channel["id"] for channel in response["channels"]] == ["discover-alpha", "discover-beta"]
    assert [channel["quizzes_today"] for channel in response["channels"]] == [2, 1]
    assert response["channels"][0]["username"] == "alphaleague"
    assert response["resets_at"] == "2026-01-02T23:00:00+00:00"


def test_admin_broadcast_preview_and_delivery(monkeypatch, request):
    d = db()
    recipient_ids = [83001, 83002]
    request.addfinalizer(lambda: d.users.delete_many({"_id": {"$in": recipient_ids}}))
    d.users.insert_many([{"_id": uid, "name": f"Player {uid}"} for uid in recipient_ids])
    sent = []

    def send_broadcast(text, image_url=None, button_text=None, button_url=None, chat_id=None):
        sent.append({
            "text": text,
            "image_url": image_url,
            "button_text": button_text,
            "button_url": button_url,
            "chat_id": chat_id,
        })
        if chat_id == "83002":
            raise RuntimeError("bot was blocked")

    monkeypatch.setattr(telegram, "send_broadcast", send_broadcast)
    payload = {
        "text": "Weekend quiz is live!",
        "image_url": "https://example.com/poster.jpg",
        "button_text": "Play now",
        "button_url": "https://t.me/footyquizbot/play",
    }

    preview = c.post("/api/admin/broadcast/preview", json=payload, headers=H(1))
    assert preview.status_code == 200 and preview.json() == {"ok": True}
    assert sent[0] == {**payload, "chat_id": "1"}

    existing_users = d.users.count_documents({})
    result = c.post("/api/admin/broadcast", json=payload, headers=H(1))
    assert result.status_code == 200
    assert result.json()["attempted"] == existing_users
    assert result.json()["sent"] == existing_users - 1
    assert result.json()["failed"] == 1
    assert result.json()["errors"] == [{"user_id": 83002, "error": "bot was blocked"}]

    assert c.post("/api/admin/broadcast/preview", json=payload, headers=H(2)).status_code == 403
    assert c.post("/api/admin/broadcast", json=payload, headers=H(2)).status_code == 403


def test_broadcast_rejects_invalid_links_and_photo_caption_length():
    base = {"text": "Hello players"}
    assert c.post("/api/admin/broadcast", json={**base, "button_url": "https://example.com"}, headers=H(1)).status_code == 422
    assert c.post("/api/admin/broadcast", json={**base, "image_url": "javascript:alert(1)"}, headers=H(1)).status_code == 422
    assert c.post("/api/admin/broadcast", json={**base, "text": "x" * 1025, "image_url": "https://example.com/image.jpg"}, headers=H(1)).status_code == 422


def test_import_library_quiz_posts_as_channel_quiz_and_scores_on_channel_leaderboard(monkeypatch, request):
    d = db()
    channel_id = "-10088001"
    request.addfinalizer(lambda: d.channels.delete_many({"_id": channel_id}))
    request.addfinalizer(lambda: d.import_quizzes.delete_many({"title": "Shared league quiz"}))
    request.addfinalizer(lambda: d.quizzes.delete_many({"channel_id": channel_id}))
    request.addfinalizer(lambda: d.attempts.delete_many({"channel_id": channel_id}))
    d.channels.insert_one({
        "_id": channel_id,
        "title": "Import Test League",
        "username": "importtestleague",
        "owner_id": 88001,
        "admin_ids": [88001],
    })
    sent = []
    monkeypatch.setenv("MINI_APP_LINK", "https://t.me/footyquizbot/play")
    monkeypatch.setattr(telegram, "send_quiz_notification", lambda caption, button_text, url, image_url=None, chat_id=None: sent.append({"chat_id": chat_id, "url": url}) or {"message_id": 111})

    template = c.post(
        "/api/admin/import-quizzes",
        json={"title": "Shared league quiz", "questions": [QUIZ["questions"][0]], "max_seconds": 45},
        headers=H(1),
    )
    assert template.status_code == 200
    template_id = template.json()["id"]
    assert c.get("/api/admin/import-quizzes", headers=H(1)).json()[0]["id"] == template_id
    assert c.get("/api/admin/import-quizzes", headers=H(2)).status_code == 403
    assert c.get(f"/api/admin/channels/{channel_id}/import-quizzes", headers=H(88002)).status_code == 403

    available = c.get(f"/api/admin/channels/{channel_id}/import-quizzes", headers=H(88001))
    assert available.status_code == 200
    assert available.json()[0]["title"] == "Shared league quiz"

    imported = c.post(f"/api/admin/channels/{channel_id}/import-quizzes/{template_id}", headers=H(88001))
    assert imported.status_code == 200 and imported.json()["notified"] is True
    quiz_id = imported.json()["id"]
    stored = d.quizzes.find_one({"_id": quiz_id})
    assert stored["channel_id"] == channel_id
    assert stored["imported_from"] == template_id
    assert stored["questions"][0]["id"] != d.import_quizzes.find_one({"_id": template_id})["questions"][0]["id"]
    assert sent == [{"chat_id": channel_id, "url": f"https://t.me/footyquizbot/play?startapp={quiz_id}"}]
    channel_quizzes = c.get(f"/api/admin/quizzes?channel_id={channel_id}", headers=H(88001)).json()
    assert any(quiz["id"] == quiz_id and quiz["status"] == "live" for quiz in channel_quizzes)

    played = play(88002, quiz_id, ["1"])
    assert played.status_code == 200
    board = c.get(f"/api/channels/{channel_id}/leaderboard", headers=H(88002)).json()
    assert board["rows"][0]["user_id"] == 88002
    assert board["rows"][0]["points"] == 10
    assert d.attempts.find_one({"quiz_id": quiz_id})["channel_id"] == channel_id


def test_import_quizzes_requires_valid_questions_and_channel_admin():
    assert c.post("/api/admin/import-quizzes", json={"title": "Invalid", "questions": [], "max_seconds": 60}, headers=H(1)).status_code == 422
    assert c.post("/api/admin/import-quizzes", json={"title": "Forbidden", "questions": [QUIZ["questions"][0]]}, headers=H(2)).status_code == 403


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


def test_draft_quiz_can_be_manually_published_and_scheduler_routes_are_gone():
    future = (now() + timedelta(hours=1)).isoformat()
    scheduled = c.post(
        "/api/admin/quizzes",
        json=dict(QUIZ, scheduled_at=future),
        headers=H(1),
    )
    assert scheduled.status_code == 422

    response = c.post(
        "/api/admin/quizzes",
        json=dict(QUIZ, title="Draft quiz", status="draft"),
        headers=H(1),
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "draft" and result["notified"] is False
    assert not any(q["id"] == result["id"] for q in c.get("/api/quizzes", headers=H(2)).json())

    published = c.post(f"/api/admin/quizzes/{result['id']}/publish", headers=H(1))
    assert published.status_code == 200 and published.json()["status"] == "live"
    assert db().quizzes.find_one({"_id": result["id"]})["status"] == "live"
    assert c.post(f"/api/admin/quizzes/{result['id']}/publish", headers=H(1)).status_code == 409

    assert c.get("/api/cron/tick").status_code == 404
    assert c.post("/api/admin/scheduler/tick", headers=H(1)).status_code == 404


def test_channels_require_post_rights_and_keep_standings_separate(monkeypatch):
    channel_data = {
        "@leagueone": {"id": -100101, "type": "channel", "title": "League One", "username": "leagueone"},
        "@leaguetwo": {"id": -100102, "type": "channel", "title": "League Two", "username": "leaguetwo"},
        "@leaguethree": {"id": -100103, "type": "channel", "title": "League Three", "username": "leaguethree"},
    }

    def get_chat(chat):
        return channel_data.get(chat) or next((c for c in channel_data.values() if str(c["id"]) == str(chat)), {})

    monkeypatch.setattr(telegram, "get_chat", get_chat)
    monkeypatch.setattr(telegram, "get_me", lambda: {"username": "footyquizbot"})
    monkeypatch.setattr(telegram, "verify_channel_access", lambda chat_id, user_id: get_chat(chat_id))
    sent = []

    def send_notification(caption, button_text, url, image_url=None, chat_id=None):
        sent.append({"caption": caption, "chat_id": chat_id})
        return {"message_id": len(sent)}

    monkeypatch.setattr(telegram, "send_quiz_notification", send_notification)
    monkeypatch.setenv("MINI_APP_LINK", "https://t.me/bot/app")

    one = c.post("/api/admin/channels", json={"username": "@leagueone"}, headers=H(1))
    two = c.post("/api/admin/channels", json={"username": "leaguetwo"}, headers=H(990))
    three = c.post("/api/admin/channels", json={"username": "leaguethree"}, headers=H(992))
    assert one.status_code == two.status_code == three.status_code == 200
    lookup = c.get("/api/admin/channels/lookup?username=leagueone", headers=H(1))
    assert lookup.status_code == 200 and lookup.json()["bot_username"] == "footyquizbot"
    one_id, two_id, three_id = one.json()["id"], two.json()["id"], three.json()["id"]
    added_admin = c.post("/api/admin/channels", json={"username": "leagueone"}, headers=H(991))
    assert added_admin.status_code == 200 and one_id in [channel["id"] for channel in c.get("/api/admin/channels", headers=H(991)).json()]

    q1 = c.post("/api/admin/quizzes", json={**QUIZ, "channel_id": one_id}, headers=H(1)).json()
    q2 = c.post("/api/admin/quizzes", json={**QUIZ, "channel_id": two_id}, headers=H(990)).json()
    q3 = c.post("/api/admin/quizzes", json={**QUIZ, "channel_id": three_id}, headers=H(992)).json()
    assert q1["notified"] and q2["notified"]
    assert sent[0]["chat_id"] == one_id
    assert '<a href="https://t.me/bot/app">Powered By Footy Quiz</a>' in sent[0]["caption"]
    assert sent[1]["chat_id"] == two_id

    assert not any(q["channel_id"] for q in c.get("/api/quizzes", headers=H(773)).json())
    assert play(771, q1["id"], ["1", "Madrid!", "0"]).json()["points"] == 35
    assert play(772, q1["id"], ["1", "wrong", "1"]).json()["points"] == 10
    assert play(771, q2["id"], ["1", "Madrid!", "0"]).json()["points"] == 35
    assert play(773, q2["id"], ["1", "Madrid!", "0"]).status_code == 200
    assert play(773, q3["id"], ["1", "Madrid!", "0"]).status_code == 200
    visible_to_773 = {q["id"] for q in c.get("/api/quizzes", headers=H(773)).json() if q["channel_id"]}
    assert visible_to_773 == {q2["id"], q3["id"]}

    board_one = c.get(f"/api/channels/{one_id}/leaderboard", headers=H(771)).json()
    board_two = c.get(f"/api/channels/{two_id}/leaderboard", headers=H(771)).json()
    assert board_one["channel"]["title"] == "League One"
    assert [r["user_id"] for r in board_one["rows"]] == [771, 772]
    assert [r["user_id"] for r in board_two["rows"]] == [771, 773]
    assert len(c.get("/api/channels", headers=H(771)).json()) == 2
    assert c.get("/api/me", headers=H(771)).json()["today"]["points"] == 70
    assert c.get("/api/me", headers=H(771)).json()["today"]["channels"] == 2
    assert c.post("/api/admin/quizzes", json={**QUIZ, "channel_id": one_id}, headers=H(3)).status_code == 403

    from _lib.leaderboard import day_key
    yesterday = day_key(now() - timedelta(days=1))
    for channel_id, uid, points in [(one_id, 781, 50), (two_id, 782, 20)]:
        db().attempts.insert_one({
            "_id": f"channel-winner-{uid}",
            "quiz_id": f"old-{channel_id}",
            "channel_id": channel_id,
            "user_id": uid,
            "user": {"id": uid, "name": f"Winner {uid}"},
            "started_at": now(),
            "submitted_at": now(),
            "day_key": yesterday,
            "points": points,
            "time_ms": 1000,
            "results": [],
        })
    monkeypatch.setattr(telegram, "profile_photo", lambda uid, url: None)
    posted_to = {}

    def send_winner(png, caption, button_text, url, parse_mode="HTML", chat_id=None):
        posted_to.update(chat_id=chat_id, caption=caption)

    monkeypatch.setattr(telegram, "send_photo", send_winner)
    preview = c.get(f"/api/admin/winner-card?day={yesterday}&channel_id={one_id}", headers=H(1))
    assert preview.status_code == 200 and preview.json()["channel_name"] == "League One"
    assert preview.json()["winner"]["user_id"] == 781
    posted = c.post(
        "/api/admin/winner-card/post",
        json={"day": yesterday, "channel_id": one_id, "caption": "League One champion"},
        headers=H(1),
    )
    assert posted.status_code == 200
    assert posted_to["chat_id"] == one_id
    assert posted_to["caption"].endswith('<a href="https://t.me/bot/app">Powered By Footy Quiz</a>')


def test_channel_connection_rejects_bot_without_post_permission(monkeypatch):
    monkeypatch.setattr(telegram, "get_chat", lambda chat: {"id": -100201, "type": "channel", "title": "No Posts", "username": "noposts"})
    monkeypatch.setattr(telegram, "get_me", lambda: {"id": 999})

    def member(chat_id, user_id):
        return {"status": "administrator", "can_post_messages": user_id != 999}

    monkeypatch.setattr(telegram, "get_chat_member", member)
    response = c.post("/api/admin/channels", json={"username": "noposts"}, headers=H(1))
    assert response.status_code == 400
    assert "permission to post" in response.json()["detail"]


def test_connecting_the_legacy_channel_migrates_existing_daily_records(monkeypatch):
    channel = {"id": -100301, "type": "channel", "title": "Legacy League", "username": "legacychannel"}
    monkeypatch.setenv("CHANNEL_ID", "@legacychannel")
    monkeypatch.setattr(telegram, "get_chat", lambda chat: channel)
    monkeypatch.setattr(telegram, "verify_channel_access", lambda chat_id, user_id: channel)
    d = db()
    quiz_id = "legacy-channel-migration"
    d.quizzes.insert_one({"_id": quiz_id, "title": "Old quiz", "questions": [], "status": "live"})
    day = "2001-02-03"
    d.attempts.insert_one({
        "_id": "legacy-channel-attempt",
        "quiz_id": quiz_id,
        "user_id": 4501,
        "user": {"id": 4501, "name": "Legacy player"},
        "started_at": now(),
        "submitted_at": now(),
        "day_key": day,
        "points": 25,
        "time_ms": 1000,
        "results": [],
    })
    d.winners.insert_one({"_id": day, "day": day, "status": "draft", "caption": "Legacy winner"})

    response = c.post("/api/admin/channels", json={"username": "legacychannel"}, headers=H(4500))
    assert response.status_code == 200 and response.json()["migrated_quizzes"] >= 1
    channel_id = response.json()["id"]
    assert d.quizzes.find_one({"_id": quiz_id})["channel_id"] == channel_id
    assert d.attempts.find_one({"_id": "legacy-channel-attempt"})["channel_id"] == channel_id
    assert d.winners.find_one({"_id": f"{channel_id}:{day}"})["caption"] == "Legacy winner"


def test_quiz_notification_with_image_and_catchy_text():
    d = db()
    os.environ["CHANNEL_ID"] = "@chan"
    os.environ["MINI_APP_LINK"] = "https://t.me/bot/app"
    sent = {}

    def fake_send_quiz_notification(caption, button_text, url, image_url=None):
        sent.update(caption=caption, button_text=button_text, url=url, image_url=image_url)
        return {"message_id": 999}

    telegram.send_quiz_notification = fake_send_quiz_notification

    quiz_doc = {
        "_id": "quiz_notify_test",
        "title": "Champions League Final Special",
        "questions": [
            {"id": "q1", "text": "Q1", "points": 25},
            {"id": "q2", "text": "Q2", "points": 25},
        ],
        "max_seconds": 45,
    }

    res = jobs.publish_quiz(d, quiz_doc)
    assert res["notified"] is True
    assert res["error"] is None
    assert sent["image_url"] == "https://ibb.co/B5RgyFsH"
    assert "New Quiz Available" in sent["caption"]
    assert "Champions League Final Special" in sent["caption"]
    assert "Total questions:" in sent["caption"]
    assert "Total points:" in sent["caption"]
    assert "Available until:" in sent["caption"] and "23:59" in sent["caption"]
    assert "Play Now" in sent["caption"]
    assert '<a href="https://t.me/bot/app">Powered By Footy Quiz</a>' in sent["caption"]
    assert sent["button_text"] == "Play now"
    assert sent["url"] == "https://t.me/bot/app?startapp=quiz_notify_test"


def test_quiz_expires_at_daily_leaderboard_reset(monkeypatch):
    legacy_expiration = c.post(
        "/api/admin/quizzes",
        json=dict(QUIZ, expires_hours=6),
        headers=H(1),
    )
    assert legacy_expiration.status_code == 422

    r = c.post("/api/admin/quizzes", json=dict(QUIZ, title="Daily Quiz"), headers=H(1))
    assert r.status_code == 200
    qid = r.json()["id"]
    quiz_in_db = db().quizzes.find_one({"_id": qid})
    from _lib.leaderboard import next_reset
    resets_at = next_reset(quiz_in_db["posted_at"])
    assert quiz_in_db["expires_at"] == resets_at
    assert "expires_hours" not in quiz_in_db
    db().quizzes.update_one(
        {"_id": qid},
        {"$set": {"expires_at": quiz_in_db["posted_at"] + timedelta(hours=24)}},
    )

    monkeypatch.setattr(routes, "now", lambda: resets_at - timedelta(seconds=1))
    assert any(q["id"] == qid for q in c.get("/api/quizzes", headers=H(2)).json())
    started = c.post(f"/api/quizzes/{qid}/start", headers=H(90))
    assert started.status_code == 200

    monkeypatch.setattr(routes, "now", lambda: resets_at)
    assert not any(q["id"] == qid for q in c.get("/api/quizzes", headers=H(2)).json())
    assert c.post(f"/api/quizzes/{qid}/start", headers=H(91)).status_code == 404
    question_id = started.json()["questions"][0]["id"]
    submit = c.post(
        f"/api/quizzes/{qid}/submit",
        json={"answers": {question_id: "1"}},
        headers=H(90),
    )
    assert submit.status_code == 404
    assert c.post(f"/api/quizzes/{qid}/boost", headers=H(90)).status_code == 409


def test_manual_winner_announcement_draft_and_post():
    d = db()
    key = "2000-01-02"
    for uid, name, points, elapsed in [
        (77, "Samuel Eto'o", 80, 61000),
        (78, "Second place", 70, 65000),
        (79, "Third place", 60, 70000),
    ]:
        d.attempts.insert_one({
            "_id": f"winner-{uid}",
            "quiz_id": "old",
            "user_id": uid,
            "user": {"id": uid, "name": name},
            "started_at": now(),
            "submitted_at": now(),
            "day_key": key,
            "points": points,
            "time_ms": elapsed,
            "results": [],
        })

    sent = {}
    os.environ["CHANNEL_ID"] = "@chan"
    os.environ["MINI_APP_LINK"] = "https://t.me/bot/app"
    telegram.profile_photo = lambda uid, url: None
    telegram.send_photo = lambda png, cap, bt, url: sent.update(png=png, cap=cap)

    preview = c.get(f"/api/admin/winner-card?day={key}", headers=H(1))
    assert preview.status_code == 200
    assert preview.json()["status"] == "ready"
    assert preview.json()["winner"]["name"] == "Samuel Eto'o"
    assert preview.json()["second"]["name"] == "Second place"
    assert preview.json()["third"]["name"] == "Third place"
    assert preview.json()["card_image"].startswith("data:image/png;base64,")

    draft = c.post("/api/admin/winner-card/save-draft", json={"day": key}, headers=H(1))
    assert draft.status_code == 200 and draft.json()["status"] == "draft"

    posted = c.post("/api/admin/winner-card/post", json={"day": key}, headers=H(1))
    assert posted.status_code == 200 and posted.json()["status"] == "sent"
    assert sent["png"][:8] == b"\x89PNG\r\n\x1a\n" and "Samuel" in sent["cap"]
    assert "Powered By Footy Quiz" in sent["cap"]
    assert c.post("/api/admin/winner-card/post", json={"day": key}, headers=H(1)).status_code == 409
    assert c.post("/api/admin/winner-card/save-draft", json={"day": key}, headers=H(1)).status_code == 409

    from _lib.leaderboard import day_key
    today = day_key(now())
    assert c.post("/api/admin/winner-card/post", json={"day": today}, headers=H(1)).status_code == 400


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


def test_telegram_image_scraping():
    html_mock = """
    <!DOCTYPE html>
    <html>
      <head>
        <meta property="og:image" content="https://i.ibb.co/abc123/banner.jpg" />
      </head>
      <body></body>
    </html>
    """
    extracted = telegram.extract_direct_image_url(html_mock)
    assert extracted == "https://i.ibb.co/abc123/banner.jpg"

    jpeg_magic = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    is_img, mime = telegram.is_image_bytes(jpeg_magic)
    assert is_img is True and mime == "image/jpeg"

    png_magic = b"\x89PNG\r\n\x1a\n"
    is_img, mime = telegram.is_image_bytes(png_magic)
    assert is_img is True and mime == "image/png"

    not_img, mime = telegram.is_image_bytes(b"<html>not an image</html>")
    assert not_img is False and mime == ""


def test_legacy_scheduled_quiz_requires_manual_publish():
    quiz_id = "legacy_scheduled_quiz"
    d = db()
    d.quizzes.insert_one({
        "_id": quiz_id,
        "title": "Previously scheduled",
        "questions": [{"id": "q1", **QUIZ["questions"][0]}],
        "max_seconds": 60,
        "expires_hours": 24,
        "status": "scheduled",
        "scheduled_at": now() - timedelta(minutes=1),
        "created_at": now(),
    })

    result = c.get("/api/admin/quizzes", headers=H(1))
    legacy_quiz = next(q for q in result.json() if q["id"] == quiz_id)
    assert legacy_quiz["status"] == "scheduled"
    assert d.quizzes.find_one({"_id": quiz_id})["status"] == "scheduled"

    published = c.post(f"/api/admin/quizzes/{quiz_id}/publish", headers=H(1))
    assert published.status_code == 200 and published.json()["status"] == "live"


