"""
Behavioral Baseline Service

Derives personalized alert thresholds from a trader's own historical behavior.
This is Tier 2 in the 3-tier threshold hierarchy:

  Tier 1: user-declared (daily_trade_limit, cooldown_after_loss, etc.)
  Tier 2: behavior-derived baselines (this service) — replaces style labels
  Tier 3: universal floors (UNIVERSAL_FLOORS in trading_defaults.py)

Why baselines beat style labels:
  The same trader scalps on expiry day and holds overnight on a slow trend day.
  Labeling them "scalper" or "swing" is wrong. Instead, we observe what they
  actually do and calibrate thresholds to their own 90-day history.

How it works:
  - Query completed_trades for the last LOOKBACK_DAYS days
  - Group into sessions (distinct IST trading dates)
  - Compute percentile statistics across sessions
  - Store result in user_profiles.detected_patterns['baseline'] (JSONB)
  - get_thresholds() in trading_defaults.py reads this as Tier 2

Minimum data requirement:
  MIN_SESSIONS distinct trading days before baselines are trusted.
  Below this, COLD_START_DEFAULTS remain active.

Recomputation:
  Called after every sync. Skipped if last computation < RECOMPUTE_INTERVAL_HOURS ago
  to avoid unnecessary DB load. Forced recompute can be triggered via API.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import UserProfile
from app.core.trading_defaults import COLD_START_DEFAULTS, UNIVERSAL_FLOORS

logger = logging.getLogger(__name__)

MIN_SESSIONS = 5              # Minimum distinct trading days before baselines are used
LOOKBACK_DAYS = 90            # Analyse last 90 days — captures enough variety in markets
BURST_WINDOW_MIN = 15         # Minutes for intraday burst detection
RECOMPUTE_INTERVAL_HOURS = 24 # Skip recompute if last run < this many hours ago


# _percentile went with _compute_baselines; baseline_service has its own.

class BehavioralBaselineService:
    """
    Stateless service — all state lives in user_profiles.detected_patterns['baseline'].
    Safe to instantiate per-request or as a singleton.
    """

    async def compute_and_store(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Compute behavioral baselines and write them into user_profiles.detected_patterns.

        Args:
            db: Async SQLAlchemy session.
            broker_account_id: Account to compute for.
            force: Skip the RECOMPUTE_INTERVAL_HOURS guard and always recompute.

        Returns:
            Computed baseline dict, or None if insufficient data or skipped.
        """
        try:
            # Check if recompute is needed (avoid redundant computation on every sync)
            if not force:
                result = await db.execute(
                    select(UserProfile).where(
                        UserProfile.broker_account_id == broker_account_id
                    )
                )
                profile = result.scalar_one_or_none()
                if profile:
                    existing = (profile.detected_patterns or {}).get('baseline')
                    if existing and isinstance(existing, dict):
                        computed_at_str = existing.get('computed_at')
                        if computed_at_str:
                            try:
                                computed_at = datetime.fromisoformat(computed_at_str)
                                age_hours = (datetime.now(timezone.utc) - computed_at).total_seconds() / 3600
                                if age_hours < RECOMPUTE_INTERVAL_HOURS:
                                    logger.debug(
                                        f"Baseline for {broker_account_id} is {age_hours:.1f}h old — skipping recompute"
                                    )
                                    return existing
                            except ValueError:
                                pass  # Malformed timestamp — proceed with recompute

            # ONE writer, ONE shape. This service used to compute its own flat
            # dict here while ai_personalization_service wrote a nested one to
            # the SAME JSONB key, and threshold resolution sniffed for a
            # "metrics" key to tell them apart - so which personalisation a
            # trader received depended on which service last happened to run.
            # Worse, two of the five values this service produced never reached
            # the reader at all: it emitted `revenge_window_min` and
            # `burst_trades_per_15min` where resolution reads
            # `revenge_window_caution_min` and `burst_trades_per_30min_caution`.
            #
            # compute_baseline is now the only producer. It carries the
            # percentile derivations this service was right about, and adds the
            # per-metric confidence this service had no way to express.
            from app.services.baseline_service import compute_baseline
            _prof = (await db.execute(
                select(UserProfile).where(
                    UserProfile.broker_account_id == broker_account_id
                )
            )).scalar_one_or_none()
            # The previous baseline is what capped adaptation caps AGAINST. Without
            # it every recompute is unconstrained, and a fortnight of escalation
            # quietly becomes the new normal.
            _previous = (getattr(_prof, "detected_patterns", None) or {}).get("baseline")
            baseline = await compute_baseline(
                broker_account_id, db,
                trading_capital=getattr(_prof, "trading_capital", None),
                previous=_previous,
            )
            if baseline is None:
                logger.info(f"Insufficient data for baseline: {broker_account_id}")
                return None

            # Persist to detected_patterns JSONB — no schema migration needed
            result = await db.execute(
                select(UserProfile).where(
                    UserProfile.broker_account_id == broker_account_id
                )
            )
            profile = result.scalar_one_or_none()
            if profile:
                patterns = dict(profile.detected_patterns or {})
                patterns['baseline'] = baseline
                profile.detected_patterns = patterns
                await db.commit()

                logger.info(
                    f"Baseline v{baseline.get('version')} updated: {broker_account_id} | "
                    f"sessions={baseline.get('sessions_analyzed')} | "
                    f"trades={baseline.get('trades_analyzed')} | "
                    f"metrics={sorted(baseline.get('metrics', {}))}"
                )

            return baseline

        except Exception as e:
            logger.error(f"Baseline computation failed for {broker_account_id}: {e}")
            return None

    # _compute_baselines was removed 2026-08-22. It was the flat-shape producer:
    # correct percentile statistics (P75 daily trades, P25 re-entry gap, P60/P85
    # loss streaks) writing to key names the threshold reader did not read. The
    # statistics were the good half and now live in baseline_service as
    # daily_trades_p75 / burst_per_30min_p75 / reentry_after_loss_p25 /
    # loss_streak_p60 / loss_streak_p85, each carrying its own confidence.
    # compute_and_store above delegates there; this service no longer computes.

    async def get_current_baseline(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Read stored baseline without recomputing. Returns None if not computed yet."""
        result = await db.execute(
            select(UserProfile).where(
                UserProfile.broker_account_id == broker_account_id
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return (profile.detected_patterns or {}).get('baseline')


behavioral_baseline_service = BehavioralBaselineService()
