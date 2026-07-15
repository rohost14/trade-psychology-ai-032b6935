"""
Detector Feature Flags — safe, per-detector migration control (Engine v2).

Each detector can be in one of four modes:

    off      detector does not run at all
    shadow   detector RUNS and records its BehaviorEvent (evidence), but the
             event is marked shadow=True → it never alerts and never moves any
             score. Use to observe a new/changed detector against live data.
    canary   run LIVE for `rollout_pct` % of accounts (deterministic per
             detector+account), shadow for the rest. The gradual ramp.
    on       fully live

Source of truth:
    - The detector REGISTRY provides the DEFAULT mode per detector (compile-time).
    - The `detector_flags` table OVERRIDES it at runtime (flip without a deploy).

Resolution is a pure dict lookup + hash — no I/O — so it is called per detector
per trade. The merged flag map is loaded once per engine run and cached in Redis
(short TTL) to avoid a DB hit on the hot path.

shadow ≠ suppressed: a suppressed event still feeds the score (notification-layer
only); a shadow event does not (it is a dark-launched detector).
"""

import hashlib
import json
import logging
from typing import Dict, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_CACHE_KEY = "detector_flags:v1"
_CACHE_TTL = 60  # seconds — a flip is visible within a minute across processes
VALID_MODES = frozenset({"off", "shadow", "canary", "on"})

# Effective (resolved) modes the engine acts on — canary collapses to on/shadow.
EFFECTIVE_ON = "on"
EFFECTIVE_OFF = "off"
EFFECTIVE_SHADOW = "shadow"


class DetectorFlagService:
    """Resolves per-detector run mode from registry defaults + DB overrides."""

    async def get_flags(self, db: AsyncSession) -> Dict[str, Tuple[str, int]]:
        """
        Return {detector_name: (mode, rollout_pct)} merging registry defaults with
        DB overrides. Redis-cached (60s). Never raises — on any failure returns the
        registry defaults so detection keeps running.
        """
        cached = self._cache_get()
        if cached is not None:
            return cached
        flags = await self._load_from_db(db)
        self._cache_set(flags)
        return flags

    async def _load_from_db(self, db: AsyncSession) -> Dict[str, Tuple[str, int]]:
        from app.services.detector_registry import REGISTRY

        # Registry defaults first (every known detector present).
        flags: Dict[str, Tuple[str, int]] = {
            spec.name: (getattr(spec, "default_mode", "on"), 100) for spec in REGISTRY
        }
        # Run the override query inside a SAVEPOINT. This is on the detection hot
        # path and shares the caller's transaction: if the query fails (table
        # missing pre-migration, transient error) a failed statement would
        # otherwise abort the whole transaction and break the detection writes that
        # follow. The savepoint confines the failure so we cleanly fall back to
        # registry defaults without poisoning the caller.
        try:
            async with db.begin_nested():
                result = await db.execute(
                    text("SELECT detector, mode, rollout_pct FROM detector_flags")
                )
                rows = result.all()
            for detector, mode, rollout_pct in rows:
                if mode in VALID_MODES:
                    flags[detector] = (mode, int(rollout_pct))
        except Exception as e:
            logger.warning(f"[detector_flags] DB load failed, using registry defaults: {e}")
        return flags

    def resolve(
        self,
        detector: str,
        broker_account_id,
        flags: Dict[str, Tuple[str, int]],
    ) -> str:
        """
        Collapse the configured mode to an EFFECTIVE mode the engine acts on:
        returns 'on', 'off', or 'shadow'. Canary resolves per account via a stable
        hash so the same account is consistently live-or-dark for a given detector.
        """
        mode, rollout_pct = flags.get(detector, ("on", 100))
        if mode == "canary":
            return EFFECTIVE_ON if self._bucket(detector, broker_account_id) < rollout_pct else EFFECTIVE_SHADOW
        if mode in (EFFECTIVE_ON, EFFECTIVE_OFF, EFFECTIVE_SHADOW):
            return mode
        return EFFECTIVE_ON  # unknown value — fail safe to live

    @staticmethod
    def _bucket(detector: str, broker_account_id) -> int:
        """Deterministic 0-99 bucket for (detector, account). Stable across runs;
        different detectors hash to different account subsets (no correlation)."""
        h = hashlib.md5(f"{detector}:{broker_account_id}".encode()).hexdigest()
        return int(h, 16) % 100

    async def set_flag(
        self,
        db: AsyncSession,
        detector: str,
        mode: str,
        rollout_pct: int = 100,
        updated_by: str = "admin",
    ) -> None:
        """Upsert a detector override and invalidate the cache. Validates inputs."""
        if mode not in VALID_MODES:
            raise ValueError(f"invalid mode {mode!r} (expected one of {sorted(VALID_MODES)})")
        if not (0 <= int(rollout_pct) <= 100):
            raise ValueError("rollout_pct must be 0-100")
        await db.execute(
            text(
                "INSERT INTO detector_flags (detector, mode, rollout_pct, updated_by, updated_at) "
                "VALUES (:detector, :mode, :rollout_pct, :updated_by, now()) "
                "ON CONFLICT (detector) DO UPDATE SET "
                "  mode = EXCLUDED.mode, rollout_pct = EXCLUDED.rollout_pct, "
                "  updated_by = EXCLUDED.updated_by, updated_at = now()"
            ),
            {"detector": detector, "mode": mode, "rollout_pct": int(rollout_pct), "updated_by": updated_by},
        )
        await db.commit()
        self._cache_invalidate()

    async def list_flags(self, db: AsyncSession) -> Dict[str, Tuple[str, int]]:
        """Fresh (uncached) merged view — for the admin UI."""
        return await self._load_from_db(db)

    # ── Redis cache (best-effort; failures degrade to a DB read) ──────────────

    def _redis(self):
        from app.core.redis_pool import get_sync_redis
        return get_sync_redis()

    def _cache_get(self):
        try:
            raw = self._redis().get(_CACHE_KEY)
            if not raw:
                return None
            data = json.loads(raw)
            return {k: (v[0], int(v[1])) for k, v in data.items()}
        except Exception:
            return None

    def _cache_set(self, flags: Dict[str, Tuple[str, int]]):
        try:
            payload = {k: [v[0], v[1]] for k, v in flags.items()}
            self._redis().set(_CACHE_KEY, json.dumps(payload), ex=_CACHE_TTL)
        except Exception:
            pass

    def _cache_invalidate(self):
        try:
            self._redis().delete(_CACHE_KEY)
        except Exception:
            pass


detector_flags = DetectorFlagService()
