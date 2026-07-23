"""In-app error feed — a capped Redis ring buffer of recent ERROR/CRITICAL log records,
surfaced in the admin System page so ops can see live application errors without SSH/Sentry.

A logging.Handler pushes each error onto `admin:error_feed` (LPUSH + LTRIM to CAP). Fully
best-effort: if Redis is down the handler silently drops (never breaks logging or requests).
"""
import json
import logging
import time

FEED_KEY = "admin:error_feed"
CAP = 200


def _sync_redis():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


class RedisErrorFeedHandler(logging.Handler):
    """Pushes ERROR+ records into a capped Redis list. Never raises."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.ERROR:
                return
            entry = {
                "level":   record.levelname,
                "logger":  record.name,
                "message": self.format(record)[:2000],
                "ts":      time.time(),
                "request_id": getattr(record, "request_id", None),
            }
            r = _sync_redis()
            pipe = r.pipeline()
            pipe.lpush(FEED_KEY, json.dumps(entry))
            pipe.ltrim(FEED_KEY, 0, CAP - 1)
            pipe.execute()
        except Exception:
            pass  # error feed must never disrupt logging


def read_error_feed(limit: int = 100) -> list[dict]:
    try:
        limit = max(1, min(limit, CAP))
        raw = _sync_redis().lrange(FEED_KEY, 0, limit - 1)
        out = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except Exception:
                continue
        return out
    except Exception:
        return []


def error_feed_count() -> int:
    try:
        return int(_sync_redis().llen(FEED_KEY))
    except Exception:
        return 0
