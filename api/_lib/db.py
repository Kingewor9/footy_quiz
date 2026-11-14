import os

_client = None
_indexed = False


def db():
    """Return the Mongo database. A single client is reused between invocations."""
    global _client, _indexed
    uri = os.getenv("MONGODB_URI", "")
    if _client is None:
        if uri.startswith("mongomock"):  # local tests only
            import mongomock

            _client = mongomock.MongoClient(tz_aware=True)
        else:
            from pymongo import MongoClient

            _client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=8000, maxPoolSize=5)
    d = _client[os.getenv("MONGODB_DB", "footy_quiz")]
    if not _indexed:
        d.attempts.create_index([("quiz_id", 1), ("user_id", 1)], unique=True)
        d.attempts.create_index("day_key")
        d.quizzes.create_index([("status", 1), ("posted_at", -1)])
        _indexed = True
    return d
