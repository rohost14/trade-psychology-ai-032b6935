"""
Section 1: Backend Health
Checklist items automated: 1.1, 1.2, 1.3, 1.5
"""

import pytest
import httpx
from tests.production.conftest import assert_200

pytestmark = pytest.mark.section1


def test_1_1_health_returns_200(anon: httpx.Client):
    """1.1 GET /health returns 200 with 'status' field."""
    r = anon.get("/health")
    assert r.status_code == 200, f"Health endpoint returned {r.status_code}. Backend not running?"
    data = r.json()
    assert "status" in data, f"Missing 'status' field in health response: {data}"
    assert data["status"] == "ok", f"status={data['status']!r} — backend unhealthy"


def test_1_2_db_reachable(anon: httpx.Client):
    """1.2 Database connection is healthy."""
    r = anon.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("db") == "ok", (
        f"DB unhealthy: db={data.get('db')!r}. Check DATABASE_URL in .env"
    )


def test_1_3_redis_reachable(anon: httpx.Client):
    """1.3 Redis connection is healthy."""
    r = anon.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("redis") == "ok", (
        f"Redis unhealthy: redis={data.get('redis')!r}. Check REDIS_URL in .env"
    )


def test_1_5_encryption_key_valid(anon: httpx.Client):
    """1.5 ENCRYPTION_KEY is valid — backend didn't crash on startup.
    If the key is invalid, uvicorn exits at startup and /health is unreachable.
    """
    r = anon.get("/health")
    # 200 means the startup hook ran successfully (which validates ENCRYPTION_KEY)
    assert r.status_code == 200, (
        "Backend unreachable. Possible causes: ENCRYPTION_KEY invalid (RuntimeError on start), "
        "or backend not running."
    )
