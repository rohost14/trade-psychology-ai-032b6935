"""
ARCHIVED analytics endpoints — NOT registered on any router.

Lifted out of `app/api/analytics.py` on 2026-07-18. Kept per the project's
archive-never-delete rule; this module is not imported anywhere.

- /edge-map, /recovery-pattern, /trading-dna
  Orphaned by the 8-tab -> 6-tab Analytics rewrite. Their only frontend
  callers now live in `src/components/analytics/_archive/`.

- /discipline-summary
  Dropped on purpose, not merely orphaned. 40 of its 100 points came from
  `CompletedTrade.quality_score`, which no service ever populates, so that
  component was permanently pinned to the neutral 20/40 default. The alert
  half used invented weights (danger x10, caution x3). That is the same
  arbitrary-composite family as the removed Emotional Tax and it conflicts
  with the factual-numbers-only policy. Its one real signal,
  `revenge_free_days`, is already computed on the My Patterns page.

Restoring any of these means re-adding the router decorator and checking the
imports below still exist in analytics.py.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 11.5 — Edge Map: capital allocation vs win rate per underlying
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/edge-map")
async def get_edge_map(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    days_back: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Per-underlying: % of trades allocated vs personal win rate.
    Reveals misalignment between where capital goes and where edge exists.
    """
    try:
        from statistics import mean as _mean
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        res = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
                CompletedTrade.status == "closed",
                CompletedTrade.realized_pnl.isnot(None),
            )
        )
        trades = res.scalars().all()

        if not trades:
            return {"has_data": False, "instruments": [], "overall_win_rate": 0, "total_trades": 0}

        def _get_underlying(sym: str) -> str:
            import re
            # Strip DDMMMYY + strike + CE/PE for options/futures
            m = re.match(r'^([A-Z&\-]+?)(\d|[A-Z]{3}\d{2})', sym)
            return m.group(1) if m else sym

        groups: dict[str, list] = defaultdict(list)
        for t in trades:
            groups[_get_underlying(t.tradingsymbol)].append(t)

        total_trades = len(trades)
        all_wins = sum(1 for t in trades if float(t.realized_pnl) > 0)
        overall_wr = round(all_wins / total_trades * 100, 1)

        MIN_TRADES = 4
        instruments = []
        for underlying, grp in groups.items():
            if len(grp) < MIN_TRADES:
                continue
            pnls = [float(t.realized_pnl) for t in grp]
            wins = [p for p in pnls if p > 0]
            instruments.append({
                "underlying":  underlying,
                "trade_count": len(grp),
                "trade_pct":   round(len(grp) / total_trades * 100, 1),
                "win_rate":    round(len(wins) / len(grp) * 100, 1),
                "avg_pnl":     round(_mean(pnls), 2),
                "total_pnl":   round(sum(pnls), 2),
            })

        instruments.sort(key=lambda x: x["trade_pct"], reverse=True)
        prop = round(100 / len(instruments), 1) if instruments else 0

        return {
            "has_data":               bool(instruments),
            "instruments":            instruments,
            "overall_win_rate":       overall_wr,
            "total_trades":           total_trades,
            "proportional_benchmark": prop,
        }
    except Exception as e:
        logger.error(f"edge-map failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────────────────────────────────────────────────────
# 11.15 — Recovery Pattern: post-bad-day trading behavior
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/recovery-pattern")
async def get_recovery_pattern(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    days_back: int = Query(default=180, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Analyze what the trader does the day after a bad session.
    Requires ≥10 trading days and ≥3 bad days to compute.
    """
    try:
        from statistics import mean as _mean, median as _median
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        res = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
                CompletedTrade.status == "closed",
            ).order_by(CompletedTrade.exit_time.asc())
        )
        trades = res.scalars().all()

        if not trades:
            return {"has_data": False}

        # Group by IST date
        daily: dict[str, list] = defaultdict(list)
        for t in trades:
            if t.exit_time:
                from datetime import timezone as _tz
                import pytz
                try:
                    ist = pytz.timezone("Asia/Kolkata")
                    local_dt = t.exit_time.astimezone(ist)
                except Exception:
                    local_dt = t.exit_time
                daily[local_dt.strftime("%Y-%m-%d")].append(t)

        sorted_days = sorted(daily.keys())
        if len(sorted_days) < 10:
            return {"has_data": False, "reason": "Need at least 10 trading days"}

        daily_pnl   = {d: sum(float(t.realized_pnl or 0) for t in ts) for d, ts in daily.items()}
        daily_count = {d: len(ts) for d, ts in daily.items()}
        daily_wins  = {d: sum(1 for t in ts if float(t.realized_pnl or 0) > 0) for d, ts in daily.items()}
        daily_wr    = {d: round(daily_wins[d] / daily_count[d] * 100, 1) for d in daily.keys()}

        pnl_vals = list(daily_pnl.values())
        loss_vals = [p for p in pnl_vals if p < 0]
        if not loss_vals:
            return {"has_data": False, "reason": "No losing days found"}

        median_abs_loss = abs(_median(loss_vals))
        threshold = -median_abs_loss * 1.5

        bad_days = [d for d, pnl in daily_pnl.items() if pnl < threshold]
        if len(bad_days) < 3:
            return {"has_data": False, "reason": "Need at least 3 bad days"}

        avg_normal = _mean(list(daily_count.values()))

        next_counts, next_wrs, next_pnls = [], [], []
        d23_counts, d23_wrs = [], []

        for bad in bad_days:
            idx = sorted_days.index(bad)
            for offset, dest_c, dest_w, dest_p in [
                (1, next_counts, next_wrs, next_pnls),
            ]:
                nxt_idx = idx + offset
                if nxt_idx < len(sorted_days):
                    nxt = sorted_days[nxt_idx]
                    if nxt in daily_count:
                        dest_c.append(daily_count[nxt])
                        dest_w.append(daily_wr[nxt])
                        dest_p.append(daily_pnl[nxt])
            for offset in [2, 3]:
                nxt_idx = idx + offset
                if nxt_idx < len(sorted_days):
                    nxt = sorted_days[nxt_idx]
                    if nxt in daily_count:
                        d23_counts.append(daily_count[nxt])
                        d23_wrs.append(daily_wr[nxt])

        if not next_counts:
            return {"has_data": False}

        avg_next_count = round(_mean(next_counts), 1)
        avg_next_wr    = round(_mean(next_wrs), 1)
        avg_next_pnl   = round(_mean(next_pnls), 2)
        overtrade_pct  = round((avg_next_count - avg_normal) / avg_normal * 100, 1) if avg_normal else 0

        return {
            "has_data":          True,
            "bad_day_threshold": round(abs(threshold), 2),
            "bad_day_count":     len(bad_days),
            "avg_normal_count":  round(avg_normal, 1),
            "overall_win_rate":  round(_mean(list(daily_wr.values())), 1),
            "next_day": {
                "avg_count":    avg_next_count,
                "avg_wr":       avg_next_wr,
                "avg_pnl":      avg_next_pnl,
                "overtrade_pct": overtrade_pct,
            },
            "days_2_3": {
                "avg_count": round(_mean(d23_counts), 1) if d23_counts else round(avg_normal, 1),
                "avg_wr":    round(_mean(d23_wrs),    1) if d23_wrs    else 0,
            },
        }
    except Exception as e:
        logger.error(f"recovery-pattern failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────────────────────────────────────────────────────
# 11.11 — VIX Context: India VIX regime + trader's stats
# ─────────────────────────────────────────────────────────────────────────────

# NOTE: /vix-context removed 2026-07-16 — VIX win-rate context was not useful and
# the regime-specific breakdown was never computable (VIX-per-trade not stored).
# Its only consumer, VixStrip.tsx, was already orphaned (VIX moved inline to the hero).


# ─────────────────────────────────────────────────────────────────────────────
# 7.3 — Trading DNA: AI-generated narrative profile
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/trading-dna")
async def get_trading_dna(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    days_back: int = Query(default=90, ge=1, le=365),
    force_refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    AI-generated narrative trading profile.
    Requires ≥30 trades. Cached 24h in Redis. Max 3 manual refreshes/day.
    """
    try:
        from statistics import mean as _mean
        from app.services.ai_service import ai_service
        import json
        import re as _re

        MIN_TRADES = 30
        CACHE_TTL_SEC = 86400  # 24h
        REFRESH_LIMIT = 3

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        res = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
                CompletedTrade.status == "closed",
                CompletedTrade.realized_pnl.isnot(None),
            ).order_by(CompletedTrade.exit_time.asc())
        )
        trades = res.scalars().all()

        if len(trades) < MIN_TRADES:
            return {
                "has_data": False,
                "reason": f"Need at least {MIN_TRADES} trades. You have {len(trades)} in the last {days_back} days.",
                "trade_count": len(trades),
                "min_trades": MIN_TRADES,
            }

        cache_key     = f"dna:{broker_account_id}:{days_back}"
        refresh_key   = f"dna_refreshes:{broker_account_id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()

        # Check refresh limit
        if force_refresh:
            refreshes = int(await r.get(refresh_key) or 0)
            if refreshes >= REFRESH_LIMIT:
                cached = await r.get(cache_key)
                if cached:
                    d = json.loads(cached)
                    d["refresh_limit_hit"] = True
                    return d
                # No cache + limit hit → still compute (rare first-run edge case)
            else:
                await r.incr(refresh_key)
                await r.expire(refresh_key, 86400)
                await r.delete(cache_key)

        # Try cache first
        if not force_refresh:
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)

        # ── Compute pre-stats for AI prompt ──────────────────────────────────
        def _get_underlying(sym: str) -> str:
            import re
            m = re.match(r'^([A-Z&\-]+?)(\d|[A-Z]{3}\d{2})', sym)
            return m.group(1) if m else sym

        # Win rate by hour
        from collections import defaultdict as _ddict
        hourly: dict[int, list] = _ddict(list)
        for t in trades:
            if t.entry_time:
                try:
                    import pytz
                    ist = pytz.timezone("Asia/Kolkata")
                    h = t.entry_time.astimezone(ist).hour
                except Exception:
                    h = t.entry_time.hour
                hourly[h].append(float(t.realized_pnl))

        hour_stats = []
        for h, pnls in hourly.items():
            if len(pnls) >= 4:
                wins = [p for p in pnls if p > 0]
                hour_stats.append({
                    "hour": h,
                    "label": f"{h:02d}:00–{h+1:02d}:00",
                    "trades": len(pnls),
                    "win_rate": round(len(wins) / len(pnls) * 100, 1),
                    "avg_pnl": round(_mean(pnls), 2),
                })
        hour_stats.sort(key=lambda x: x["win_rate"], reverse=True)
        best_hour  = hour_stats[0]  if hour_stats else None
        worst_hour = hour_stats[-1] if len(hour_stats) > 1 else None

        # Win rate by underlying
        inst: dict[str, list] = _ddict(list)
        for t in trades:
            inst[_get_underlying(t.tradingsymbol)].append(float(t.realized_pnl))
        inst_stats = []
        for sym, pnls in inst.items():
            if len(pnls) >= 5:
                wins = [p for p in pnls if p > 0]
                inst_stats.append({
                    "symbol": sym,
                    "trades": len(pnls),
                    "win_rate": round(len(wins) / len(pnls) * 100, 1),
                    "avg_pnl": round(_mean(pnls), 2),
                })
        inst_stats.sort(key=lambda x: x["win_rate"], reverse=True)
        best_inst  = inst_stats[0]  if inst_stats else None
        worst_inst = inst_stats[-1] if len(inst_stats) > 1 else None

        # Post-loss behavior
        all_pnls = [float(t.realized_pnl) for t in trades]
        wins_total = [p for p in all_pnls if p > 0]
        overall_wr = round(len(wins_total) / len(all_pnls) * 100, 1)

        stats_payload = {
            "total_trades": len(trades),
            "overall_win_rate": overall_wr,
            "best_hour": best_hour,
            "worst_hour": worst_hour,
            "best_instrument": best_inst,
            "worst_instrument": worst_inst,
            "avg_hold_minutes": round(_mean([t.duration_minutes or 0 for t in trades]), 1),
        }

        # ── AI call ──────────────────────────────────────────────────────────
        system_prompt = (
            "You are writing a concise 2-paragraph trading profile for a retail Indian F&O trader. "
            "Write in second person ('you'). Paragraph 1: lead with their edge — where they win, when, with what instrument. "
            "Paragraph 2: their primary weakness — be specific and direct. "
            "Use the exact numbers from the data. No bullet points. No headers. Plain prose only. "
            "Do not give trading advice. Do not tell them what to do. Mirror facts only."
        )
        user_msg = f"Trader data: {json.dumps(stats_payload, default=str)}"

        ai_response = await ai_service._make_request(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            model=ai_service.primary_model,
            temperature=0.6,
            max_tokens=400,
        )

        narrative = ai_response["content"].strip() if ai_response else None

        result = {
            "has_data":   True,
            "narrative":  narrative,
            "stats":      stats_payload,
            "cached_at":  datetime.now(timezone.utc).isoformat(),
            "refresh_limit_hit": False,
        }

        await r.set(cache_key, json.dumps(result, default=str), ex=CACHE_TTL_SEC)
        return result

    except Exception as e:
        logger.error(f"trading-dna failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



# ─────────────────────────────────────────────────────────────────────────────
# 11.8 — Discipline Summary: weekly score + streaks
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/discipline-summary")
async def get_discipline_summary(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Computes current week's discipline score + streak data on-demand.
    """
    try:
        from statistics import mean as _mean
        from zoneinfo import ZoneInfo as _ZoneInfo

        now_utc = datetime.now(timezone.utc)
        IST = _ZoneInfo("Asia/Kolkata")
        now_ist = now_utc.astimezone(IST)

        # Current week: Monday 00:00 IST → now
        week_start_ist = now_ist - timedelta(days=now_ist.weekday())
        week_start_ist = week_start_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start_utc = week_start_ist.astimezone(timezone.utc)

        # Last 4 weeks for trend
        four_weeks_ago = now_utc - timedelta(weeks=4)

        # ── Alerts this week ──────────────────────────────────────────────────
        alerts_res = await db.execute(
            select(RiskAlert).where(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= week_start_utc,
            )
        )
        week_alerts = alerts_res.scalars().all()

        danger_count  = sum(1 for a in week_alerts if a.severity == "danger")
        caution_count = sum(1 for a in week_alerts if a.severity == "caution")

        # ── Trades this week ──────────────────────────────────────────────────
        trades_res = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= week_start_utc,
                CompletedTrade.status == "closed",
            )
        )
        week_trades = trades_res.scalars().all()

        # ── Quality component (avg quality score this week) ───────────────────
        scored = [t.quality_score for t in week_trades if t.quality_score is not None]
        quality_avg = (sum(scored) / len(scored)) if scored else 4.0  # 4/8 = neutral 20pts default

        # ── Discipline score formula ──────────────────────────────────────────
        # Alerts component (60 points): penalise hard violations more
        alert_score = max(0, 60 - (danger_count * 10) - (caution_count * 3))

        # Quality component (40 points): based on avg quality
        quality_score_component = min(40, round((quality_avg / 8) * 40))

        total_score = alert_score + quality_score_component

        # ── Streak: days without revenge_trade alert ──────────────────────────
        # Look back up to 30 days
        thirty_days_ago = now_utc - timedelta(days=30)
        revenge_res = await db.execute(
            select(RiskAlert.detected_at).where(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= thirty_days_ago,
                RiskAlert.pattern_type == "revenge_trade",
            ).order_by(RiskAlert.detected_at.desc())
        )
        revenge_times = [r[0] for r in revenge_res.fetchall()]

        revenge_free_days = 0
        if not revenge_times:
            revenge_free_days = 30
        else:
            last_revenge = revenge_times[0]
            # Compare IST dates to avoid ±1 day error in 18:30–23:59 UTC window
            now_ist_date = now_utc.astimezone(IST).date()
            last_revenge_ist_date = last_revenge.astimezone(IST).date()
            revenge_free_days = (now_ist_date - last_revenge_ist_date).days

        # ── 4-week trend ──────────────────────────────────────────────────────
        weeks_res = await db.execute(
            select(RiskAlert.detected_at, RiskAlert.severity).where(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= four_weeks_ago,
            ).order_by(RiskAlert.detected_at.asc())
        )
        all_past_alerts = weeks_res.fetchall()

        # Neutral quality component for past weeks — quality_score field is not yet
        # populated by any service, so using 4.0/8 neutral default rather than
        # leaking current week's quality into all historical weeks.
        neutral_quality = min(40, round((4.0 / 8) * 40))  # 20 pts

        # Build weekly scores for sparkline (last 4 weeks)
        weekly_trend = []
        for w in range(3, -1, -1):
            ws = now_utc - timedelta(weeks=w+1)
            we = now_utc - timedelta(weeks=w)
            wk_danger  = sum(1 for at, sev in all_past_alerts if ws <= at < we and sev == "danger")
            wk_caution = sum(1 for at, sev in all_past_alerts if ws <= at < we and sev == "caution")
            wk_score   = max(0, 60 - (wk_danger * 10) - (wk_caution * 3)) + neutral_quality
            weekly_trend.append(min(100, wk_score))

        return {
            "has_data":            True,
            "score":               min(100, total_score),
            "max_score":           100,
            "week_start":          week_start_ist.strftime("%Y-%m-%d"),
            "danger_alerts":       danger_count,
            "caution_alerts":      caution_count,
            "trades_this_week":    len(week_trades),
            "revenge_free_days":   revenge_free_days,
            "weekly_trend":        weekly_trend,
            "breakdown": {
                "alerts_score":  alert_score,
                "quality_score": quality_score_component,
            },
        }
    except Exception as e:
        logger.error(f"discipline-summary failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


