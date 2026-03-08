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

from app.models.completed_trade import CompletedTrade
from app.models.user_profile import UserProfile
from app.core.trading_defaults import COLD_START_DEFAULTS, UNIVERSAL_FLOORS

logger = logging.getLogger(__name__)

MIN_SESSIONS = 5              # Minimum distinct trading days before baselines are used
LOOKBACK_DAYS = 90            # Analyse last 90 days — captures enough variety in markets
BURST_WINDOW_MIN = 15         # Minutes for intraday burst detection
RECOMPUTE_INTERVAL_HOURS = 24 # Skip recompute if last run < this many hours ago


def _percentile(data: List[float], p: int) -> float:
    """Linear interpolation percentile. Returns 0.0 for empty list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (n - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, n - 1)
    return sorted_data[lo] + (k - lo) * (sorted_data[hi] - sorted_data[lo])


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

            baseline = await self._compute_baselines(db, broker_account_id)
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
                    f"Baseline updated: {broker_account_id} | "
                    f"sessions={baseline['session_count']} | "
                    f"daily_limit={baseline['daily_trade_limit']} | "
                    f"burst={baseline['burst_trades_per_15min']} | "
                    f"revenge_window={baseline['revenge_window_min']}min"
                )

            return baseline

        except Exception as e:
            logger.error(f"Baseline computation failed for {broker_account_id}: {e}")
            return None

    async def _compute_baselines(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Core computation. Returns None if fewer than MIN_SESSIONS sessions.

        Statistics computed (all percentile-based, not mean — robust to outlier days):
          - daily_trade_limit: P75 of trades_per_session
            75th percentile means alerts fire only on unusually active days.
          - burst_trades_per_15min: P75 of max-burst-in-session
            Calibrated to what's actually a burst for this particular trader.
          - revenge_window_min: P25 of loss→next-entry gap (fast end of their behaviour)
            Detects re-entry that's faster than their own typical fast behaviour.
          - consecutive_loss_caution: P60 of max_consec_losses_per_session (early warning)
          - consecutive_loss_danger:  P85 of max_consec_losses_per_session (serious risk)
        """
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")

        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

        result = await db.execute(
            select(
                CompletedTrade.entry_time,
                CompletedTrade.exit_time,
                CompletedTrade.realized_pnl,
            )
            .where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
                CompletedTrade.exit_time.is_not(None),
                CompletedTrade.entry_time.is_not(None),
            )
            .order_by(CompletedTrade.entry_time)
        )
        rows = result.all()

        if not rows:
            return None

        # Group rows into IST trading sessions
        sessions: Dict[str, List[Dict]] = {}
        for entry_time, exit_time, pnl in rows:
            if entry_time is None or exit_time is None:
                continue
            # Ensure tz-awareness
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            if exit_time.tzinfo is None:
                exit_time = exit_time.replace(tzinfo=timezone.utc)

            # Use exit_time for session assignment (a trade's day = when it closed)
            session_date = exit_time.astimezone(IST).date().isoformat()
            if session_date not in sessions:
                sessions[session_date] = []
            sessions[session_date].append({
                'entry_time': entry_time.astimezone(IST),
                'exit_time':  exit_time.astimezone(IST),
                'pnl':        float(pnl or 0),
            })

        if len(sessions) < MIN_SESSIONS:
            return None

        trades_per_session:    List[float] = []
        max_burst_per_session: List[float] = []
        revenge_gaps_min:      List[float] = []
        consec_loss_per_session: List[float] = []

        for session_trades in sessions.values():
            # Sort within session by entry_time
            session_trades.sort(key=lambda t: t['entry_time'])
            n = len(session_trades)

            trades_per_session.append(float(n))

            # --- Max burst: max trades starting in any 15-min window ---
            entry_times = [t['entry_time'] for t in session_trades]
            max_burst = 1
            for i, ts in enumerate(entry_times):
                window_end = ts + timedelta(minutes=BURST_WINDOW_MIN)
                count = sum(1 for et in entry_times[i:] if et <= window_end)
                if count > max_burst:
                    max_burst = count
            max_burst_per_session.append(float(max_burst))

            # --- Loss → re-entry gaps (within session, gap < 60 min) ---
            for i in range(n - 1):
                if session_trades[i]['pnl'] < 0:
                    gap_min = (
                        session_trades[i + 1]['entry_time'] - session_trades[i]['exit_time']
                    ).total_seconds() / 60.0
                    # Only count gaps that are plausibly "re-entering after a loss"
                    # (positive = next trade starts after current exits, < 60 min = same session)
                    if 0 < gap_min < 60:
                        revenge_gaps_min.append(gap_min)

            # --- Max consecutive losses in session ---
            max_consec = 0
            current_consec = 0
            for t in session_trades:
                if t['pnl'] < 0:
                    current_consec += 1
                    if current_consec > max_consec:
                        max_consec = current_consec
                else:
                    current_consec = 0
            consec_loss_per_session.append(float(max_consec))

        # --- Apply percentile statistics ---

        # Daily trade limit: P75 — active-but-not-outlier day for this trader
        daily_trade_limit = max(
            int(round(_percentile(trades_per_session, 75))),
            COLD_START_DEFAULTS['daily_trade_limit'],
        )

        # Burst threshold: P75 of session max bursts
        burst = max(
            int(round(_percentile(max_burst_per_session, 75))),
            UNIVERSAL_FLOORS['burst_trades_per_15min'],
        )

        # Revenge window: P25 of loss→re-entry gaps (their fast end)
        # If they typically wait 7 min but sometimes 2 min, alert at 2-3 min.
        # If no data: keep cold-start default.
        if revenge_gaps_min:
            revenge_window = round(
                max(_percentile(revenge_gaps_min, 25), float(UNIVERSAL_FLOORS['revenge_window_min'])),
                1,
            )
        else:
            revenge_window = float(COLD_START_DEFAULTS['revenge_window_min'])

        # Consecutive loss thresholds
        caution = max(
            int(round(_percentile(consec_loss_per_session, 60))),
            UNIVERSAL_FLOORS['consecutive_loss_caution'],
        )
        danger = max(
            int(round(_percentile(consec_loss_per_session, 85))),
            caution + 1,  # danger must be strictly greater than caution
        )

        return {
            'daily_trade_limit':        daily_trade_limit,
            'burst_trades_per_15min':   burst,
            'revenge_window_min':       revenge_window,
            'consecutive_loss_caution': caution,
            'consecutive_loss_danger':  danger,
            'session_count':            len(sessions),
            'computed_at':              datetime.now(timezone.utc).isoformat(),
        }

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
