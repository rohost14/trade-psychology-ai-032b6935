"""Runtime global settings (migration 074) — feature kill-switches, signup gate, AI model
overrides — flippable from the admin panel without a redeploy.

Source of truth = `admin_settings` DB table. A Redis snapshot (`admin:settings`) fronts it so
SYNC consumers (whatsapp property, push, ai_service) can read cheaply without awaiting the DB.
Anything unset falls back to DEFAULTS, so an empty table == current behaviour.

FAIL-SAFE: on any store error, features default ENABLED and signup OPEN — a broken settings
store must never take the whole product down or lock everyone out.
"""
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_KEY = "admin:settings"
_CACHE_TTL = 10.0  # seconds — in-process cache over the Redis snapshot

# Code defaults. Feature flags TRUE, signup OPEN, models = ai_service constants.
DEFAULTS: dict[str, Any] = {
    "feature_whatsapp": True,
    "feature_ai_coach": True,
    "feature_push":     True,
    "signup_mode":      "open",                              # open | closed | waitlist
    "model_primary":    "anthropic/claude-3.5-haiku",
    "model_deep":       "anthropic/claude-sonnet-4-5",
    "model_reasoning":  "openai/gpt-4o-mini",
    "model_free":       "google/gemini-flash-1.5-8b",
}

SIGNUP_MODES = ("open", "closed", "waitlist")

# Curated allowlist — an admin can only pick a known-good model id (edit here to add more).
MODEL_ALLOWLIST = (
    "anthropic/claude-3.5-haiku",
    "anthropic/claude-sonnet-4-5",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "google/gemini-flash-1.5-8b",
    "google/gemini-2.0-flash-001",
)

_cache: Optional[dict] = None
_cache_at = 0.0


def _sync_redis():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


def get_all_sync() -> dict:
    """DEFAULTS merged with the Redis snapshot. In-process cached; fail-safe to DEFAULTS."""
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is not None and (now - _cache_at) < _CACHE_TTL:
        return _cache
    merged = dict(DEFAULTS)
    try:
        raw = _sync_redis().get(REDIS_KEY)
        if raw:
            merged.update(json.loads(raw))
    except Exception as e:
        logger.warning(f"[admin_settings] snapshot read failed, using defaults: {e}")
    _cache = merged
    _cache_at = now
    return merged


def feature_enabled(name: str) -> bool:
    """e.g. feature_enabled('whatsapp'). Defaults ENABLED (fail-safe)."""
    return bool(get_all_sync().get(f"feature_{name}", True))


def signup_mode() -> str:
    return str(get_all_sync().get("signup_mode", "open"))


def ai_model(role: str) -> str:
    return str(get_all_sync().get(f"model_{role}", DEFAULTS.get(f"model_{role}", "")))


def _invalidate():
    global _cache
    _cache = None


# ── async (admin write path + startup warm) ────────────────────────────────────
async def load_from_db(db) -> dict:
    """Read the table → write the Redis snapshot → return the effective settings."""
    from sqlalchemy import select
    from app.models.admin_setting import AdminSetting
    values = dict(DEFAULTS)
    try:
        rows = (await db.execute(select(AdminSetting))).scalars().all()
        for r in rows:
            values[r.key] = r.value
        _write_snapshot(values)
    except Exception as e:
        logger.warning(f"[admin_settings] load_from_db failed: {e}")
    return values


def _write_snapshot(values: dict) -> None:
    try:
        _sync_redis().set(REDIS_KEY, json.dumps(values))
        _invalidate()
    except Exception as e:
        logger.warning(f"[admin_settings] snapshot write failed: {e}")


async def get_effective(db) -> dict:
    """Authoritative view for the admin UI: DEFAULTS merged with DB rows."""
    from sqlalchemy import select
    from app.models.admin_setting import AdminSetting
    values = dict(DEFAULTS)
    rows = (await db.execute(select(AdminSetting))).scalars().all()
    for r in rows:
        values[r.key] = r.value
    return values


async def save(db, updates: dict, admin_email: str) -> dict:
    """Validate + upsert the given keys, refresh the Redis snapshot. Returns effective settings."""
    from sqlalchemy import select
    from datetime import datetime, timezone
    from app.models.admin_setting import AdminSetting

    for k, v in updates.items():
        if k not in DEFAULTS:
            raise ValueError(f"unknown setting: {k}")
        if k.startswith("feature_") and not isinstance(v, bool):
            raise ValueError(f"{k} must be a boolean")
        if k == "signup_mode" and v not in SIGNUP_MODES:
            raise ValueError(f"signup_mode must be one of {SIGNUP_MODES}")
        if k.startswith("model_") and v not in MODEL_ALLOWLIST:
            raise ValueError(f"{k} must be one of the allowlisted models")

    for k, v in updates.items():
        existing = (await db.execute(select(AdminSetting).where(AdminSetting.key == k))).scalar_one_or_none()
        if existing:
            existing.value = v
            existing.updated_by = admin_email
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(AdminSetting(key=k, value=v, updated_by=admin_email))
    await db.commit()
    return await load_from_db(db)
