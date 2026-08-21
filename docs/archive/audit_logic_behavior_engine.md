> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> Audits the pre-registry engine; findings keyed to patterns merged away in Phase 4 and to RISK_DELTAS, deleted 2026-08-13. Its two CRITICALs are both fixed. Its live finding (fomo pre-close threshold) was rescued and fixed in a67fc4f.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# Behavioral Engine Logic Audit

**Audited files:**
- `backend/app/services/behavior_engine.py` (1849 lines)
- `backend/app/core/trading_defaults.py`
- `backend/app/services/instrument_parser.py`
- `backend/app/core/market_hours.py`
- `backend/app/tasks/trade_tasks.py`
- `backend/app/models/risk_alert.py`
- `backend/app/schemas/risk_alert.py`

**Audit date:** 2026-06-10  
**Auditor:** Claude Sonnet 4.6 (automated logic review)

---

## Cross-Cutting Issues (apply to multiple patterns)

### CROSS-1: session_trades includes the current completed_trade itself
**File**: behavior_engine.py:266–275  
**Status**: BUG  
**Finding**: The `session_trades` query fetches ALL trades with `exit_time >= session_start`, which **includes** `completed_trade` itself. Several patterns filter it out with `t.id != ct.id`, but some do not, or the inclusion creates subtle double-counting.  
**Evidence**:
```python
ct_result = await db.execute(
    select(CompletedTrade)
    .where(and_(
        CompletedTrade.broker_account_id == broker_account_id,
        CompletedTrade.exit_time >= session_start,
    ))
    .order_by(CompletedTrade.exit_time.asc())
)
session_trades = list(ct_result.scalars().all())
```
Patterns that rely on `len(ctx.session_trades)` for daily count (e.g., `_detect_overtrading_burst` daily check at line 562) count the current trade, which is correct. But `_detect_consecutive_loss_streak` iterates `reversed(trades)` and the current trade IS the last element, so its own P&L is always included in the streak. This is actually correct behaviour for streak detection but it means some patterns that `filter t.id != ct.id` may be inconsistent with patterns that do not.  
**Impact**: Minor inconsistency but not a hard bug for most patterns; see CROSS-2 below for a concrete consequence.  
**Fix**: Confirm intent per pattern and add a clear comment; or load session_trades *excluding* the current trade and add the current trade explicitly where needed.

---

### CROSS-2: consecutive_loss_streak — double-builds losing_trades list
**File**: behavior_engine.py:380–405  
**Status**: MINOR_ISSUE  
**Finding**: The streak is computed by iterating `reversed(trades)` (line 382) and then the `losing_trades` list for the context is **also** built by iterating `reversed(trades)` again (line 395) and reversing at the end. This is redundant work, and more critically the second loop uses an identical guard (`pnl < 0 / else: break`) but starts from the newest trade. If `ct` itself is a zero-P&L trade (e.g. `realized_pnl = 0`), the streak loop breaks on it but `losing_trades` would also break — which is correct. If `ct` is a winner, both break immediately and `streak = 0` so the function returns `None`. However, there is no guard that the `losing_trades` list was built from exactly the same trades that contributed to `streak`. The count `streak` and the list `losing_trades` both restart from the most-recent trade going backwards, so they are consistent. Risk: low, but the duplicate logic is fragile.  
**Impact**: Cosmetic/fragility only in current code.  
**Fix**: Build `losing_trades` once in the first pass, reverse at the end.

---

### CROSS-3: session_trades query uses exit_time but some patterns care about entry_time
**File**: behavior_engine.py:268–274  
**Status**: MINOR_ISSUE  
**Finding**: `session_trades` is filtered by `exit_time >= session_start`. A trade that **entered yesterday** (NRML overnight) but **exited today** will appear in today's session. This is correct for P&L accounting but will distort time-based patterns like `revenge_trade` (gap from exit to next entry), `overtrading_burst` (30-min window uses `entry_time`), and `opening_5min_trap` (checks `entry_time`). An overnight carry that closes at 09:20 IST will trigger `opening_5min_trap` even though the entry was yesterday's deliberate position.  
**Impact**: False positives on `opening_5min_trap`, possible false positive on `overtrading_burst` and `rapid_reentry` for overnight NRML carries.  
**Fix**: `opening_5min_trap` and `end_of_session_mis_panic` should explicitly check that `entry_time` is also within today's session date. `_detect_opening_5min_trap` already checks `entry_ist` time range (09:15–09:25) which partially protects it. For NRML carries that entered pre-09:15 yesterday, `entry_time` would not be in 09:15–09:25 so it would not fire — actually this is handled. Low impact.

---

### CROSS-4: Decimal/float mixing for loss_pct comparisons
**File**: behavior_engine.py:1071, 1326–1327, 1379–1381  
**Status**: MINOR_ISSUE  
**Finding**: `loss_pct` is computed as `Decimal / Decimal * 100` giving a `Decimal`, but then compared to `Decimal(str(loss_threshold_pct))` where `loss_threshold_pct` is a float from `thresholds.get()`. This is safe because of the `Decimal(str(...))` wrapping, but in `_detect_premium_destruction` (line 1440–1443), the fallback P&L % is computed as raw `float` arithmetic and then compared against `threshold` which is a `float`. Inconsistent mixing increases the chance of precision errors.  
**Impact**: Very low; Python's `Decimal(str(float))` approach is correct but verbose.  
**Fix**: Standardise: compute all percentages as floats or all as Decimals.

---

### CROSS-5: strategy_group suppression only blocks 4 patterns
**File**: behavior_engine.py:325–330  
**Status**: MINOR_ISSUE  
**Finding**: `_STRATEGY_SUPPRESSED` covers `revenge_trade`, `martingale_behaviour`, `size_escalation`, `consecutive_loss_streak`. But other patterns like `rapid_reentry`, `rapid_flip`, `panic_exit`, `no_stoploss`, and `post_loss_recovery_bet` can also generate false positives for legitimate hedge legs. For example, a short put spread (sell put, buy lower put) will trigger `rapid_reentry` or `no_stoploss` on the protective long put leg if it expires worthless.  
**Impact**: False positive alerts on legitimate multi-leg strategies.  
**Fix**: Extend `_STRATEGY_SUPPRESSED` to also include `rapid_reentry`, `no_stoploss` (or at least a per-pattern check for `ctx.strategy_group`).

---

### CROSS-6: _detect_cooldown_violation is never called
**File**: behavior_engine.py:332–370 (detector list)  
**Status**: BUG  
**Finding**: `_detect_cooldown_violation` (Pattern 8, line 781) is **not in the `_run_all_detectors` list**. The docstring at line 48 lists it as pattern 8 ("cooldown_violation"), and RISK_DELTAS at line 92 has an entry for it, but the method is never called. The session memory notes say "cooldown_violation removed as alert (kept in engine for analytics)" — but it is not called at all so it contributes nothing to analytics either.  
**Impact**: Active cooldown violations are never detected or surfaced. `RISK_DELTAS["cooldown_violation"] = 25` is dead configuration.  
**Fix**: Either add it back to the detector list (with alert suppression / info-only severity) or remove the method and RISK_DELTAS entry entirely.

---

## Pattern-Level Findings

### Pattern 1: consecutive_loss_streak
**File**: behavior_engine.py:375–427  
**Status**: MINOR_ISSUE  
**Finding 1**: The streak is built by iterating `reversed(trades)`, where `trades = ctx.session_trades` includes `completed_trade` itself. Since `session_trades` is ordered by `exit_time ASC`, the current trade is the last element. `reversed()` therefore starts from the current trade. If the current trade is a winner (`pnl >= 0`), the loop breaks immediately and `streak = 0`, returning `None` — correct. If it is a loser, it is counted first, which is correct.  
**Finding 2 (BUG)**: The `losing_trades` list (for UI display) is built by iterating `reversed(trades)` a **second time** without filtering out `ct.id`. Both loops are identical and would produce the same result, but the first loop's `streak` count and the second loop's `losing_trades` list are computed independently. If the list differs from the count (e.g., a race or future refactor), the UI detail panel would show the wrong trades. Low risk today, but fragile.  
**Finding 3 (MINOR_ISSUE)**: No severity-escalation based on total loss amount — only streak count. A 3-trade streak losing ₹50 gets the same `caution` as one losing ₹500,000.  
**Impact**: Cosmetic + minor fragility.  
**Fix**: Build `losing_trades` in the first loop; consider adding a loss-amount modifier.

---

### Pattern 2: revenge_trade
**File**: behavior_engine.py:431–488  
**Status**: MINOR_ISSUE  
**Finding 1**: `prior = [t for t in trades if t.exit_time and t.exit_time < ct.entry_time]` — this correctly finds trades that **exited** before the current **entry**. The `gap_min` is computed as `(ct.entry_time - last.exit_time).total_seconds() / 60`. This is the correct formula (exit of prior → entry of current).  
**Finding 2 (MINOR_ISSUE)**: The `prior` list is built from `ctx.session_trades` which already includes the current trade. The filter `t.exit_time < ct.entry_time` excludes the current trade (its exit_time > its entry_time by definition), so this is safe.  
**Finding 3 (MINOR_ISSUE)**: `danger_window = 5` min, `caution_window = 20` min. If `gap_min <= danger_window` (≤5 min), it fires danger. If `gap_min <= caution_window` (≤20 min, i.e. 6–20 min), it fires caution. The logic is `if gap_min <= danger_window` first, then `elif gap_min <= caution_window`. This is correct, no off-by-one.  
**Finding 4 (MINOR_ISSUE)**: Revenge trade is only triggered if `last_pnl < 0` (the immediately preceding trade by exit time was a loss). But what if trades are: win, loss, win, loss, loss, [new trade]? The `prior[-1]` is the second loss. The pattern correctly catches this. Edge case: if two trades close simultaneously (same exit_time), `prior[-1]` is non-deterministic.  
**Impact**: Edge case with simultaneous exits.  
**Fix**: Add a secondary sort key on `id` for deterministic ordering when exit_times collide.

---

### Pattern 3: overtrading_burst + daily count
**File**: behavior_engine.py:492–586  
**Status**: MINOR_ISSUE  
**Finding 1 (BUG — logic gap)**: The burst count window is `cutoff = ct.entry_time - timedelta(minutes=30)`. It counts `recent = [t for t in ctx.session_trades if t.entry_time and t.entry_time >= cutoff and t.id != ct.id]`. Then `burst_count = len(recent) + 1`. **Problem**: `session_trades` is filtered by `exit_time >= session_start`, not by `entry_time >= session_start`. For the burst window, it uses `entry_time`. These two timestamps are from different ranges. An NRML trade entered at 09:20 that closed at 11:00 will be in session_trades; its `entry_time` is in the session, correct. But an overnight NRML that entered yesterday and closed at 09:30 will also be in session_trades, and if the current trade's `entry_time` is 09:40, the overnight carry's `entry_time` (yesterday afternoon) would NOT be >= `cutoff` (09:10 today), so it would be excluded from the burst window. This is actually correct behaviour — no bug here.  
**Finding 2 (MINOR_ISSUE)**: The "profitable burst suppression" logic at line 513–518: `if session_pnl > 0 and all_burst_profitable: pass`. The `pass` falls through to the `elif burst_count >= burst_danger` check. If the burst is profitable and below the danger threshold, the code reaches line 546 and checks `losing_in_burst > 0`. Since all burst trades are profitable, `losing_in_burst = 0` and no alert fires — correct. But the flow is confusing: the `pass` inside the `if burst_count >= burst_caution:` block means execution continues past the suppression check into the nested elif/else. This is correct Python but misleading.  
**Finding 3 (MINOR_ISSUE)**: The daily count check at line 562: `daily_count = len(ctx.session_trades)`. This counts **all session trades including the current one** (since the current trade is in session_trades). So when the 12th trade fires, `daily_count = 12` which is `>= daily_danger` (12). Correct: fires at exactly 12.  
**Finding 4 (BUG)**: The daily count caution only fires `if session_pnl < 0` (line 576). If a user has traded 8+ times in a day with a positive session P&L, **no daily overtrading caution ever fires**. SEBI data says >7 trades/day has 94% loss probability regardless of current session profit. A profitable 8-trade session can easily turn into a loss on trade 9. This gate is too permissive.  
**Impact**: Significant false negatives for profitable high-frequency traders who are genuinely overtrading.  
**Fix**: Remove or relax the `session_pnl < 0` gate on the daily caution; at minimum fire caution even when profitable, but phrase it differently ("tracking 8 trades today, historically high counts reduce your edge").

---

### Pattern 4: size_escalation
**File**: behavior_engine.py:590–641  
**Status**: MINOR_ISSUE  
**Finding 1**: The function requires exactly `len(trades) < 3` to return (line 593), meaning it needs at least 3 session trades. Then it fetches `prior` = last 3 trades on the same underlying (excluding current trade). **Off-by-one issue**: `prior = sorted(...)[-3:]` gets the last 3, then checks `len(prior) < 3: return None`. So it needs at least 3 *prior* trades on the same underlying, which means the current trade is the 4th+. The `sizes` check is `sizes[0] < sizes[1] < sizes[2]` — strictly increasing. If sizes are flat or decreasing in any step, it returns None. This is correct for the pattern definition.  
**Finding 2 (MINOR_ISSUE)**: Size is measured in `total_quantity` (raw lot count), not notional value. For different strikes/expiries of the same underlying, the lot size is the same (NSE standardizes per underlying), so this is acceptable. However, if a user trades both NIFTY and NIFTY-equivalent via different expiries, underlying filtering handles this.  
**Finding 3 (MINOR_ISSUE)**: `losses_before = sum(1 for p in pnls[:2] if p < 0)` — checks first 2 of the 3 prior trades. Only requires 1 loss. This is correct: the pattern is "size escalated during a losing stretch", requiring at least 1 of the 2 preceding trades to be a loss.  
**Finding 4 (BUG)**: The 3 prior trades come from `ctx.session_trades` which can include the current trade. The filter `t.id != ct.id` correctly excludes it. But `prior` is sorted by `exit_time` and takes `[-3:]`. If there are exactly 3 prior trades, this is fine. The escalation check is `sizes[0] < sizes[1] < sizes[2]`. Note that `sizes[2]` is the most recent of the prior 3, **not** the current trade. The current trade's size is never included in the escalation comparison. This means the pattern fires based on 3 prior trades, and the "current trade" that triggered it may have any size. The message says "3 consecutive trades" using the prior 3, which is correct. However, the current trade's size is shown in `all_sizes` in `_detect_martingale_behaviour` (line 750) but NOT in `_detect_size_escalation` — inconsistency.  
**Impact**: Minor inconsistency in what "current trade" represents across patterns.

---

### Pattern 5: rapid_reentry
**File**: behavior_engine.py:646–679  
**Status**: CORRECT  
**Finding**: Only fires after a loss on the same symbol (`prior_pnl >= 0: return None`). Gap is computed from `last_same.exit_time` to `ct.entry_time`. Guard for negative gap (`0 <= gap_min <= window`). Logic is sound.  
**Edge case**: If the same symbol appears twice with the same exit_time (partial fills assembled into 2 completed trades), `max(prior_same, key=lambda t: t.exit_time)` picks one non-deterministically. Low risk in practice.

---

### Pattern 6: panic_exit
**File**: behavior_engine.py:683–709  
**Status**: CORRECT  
**Finding**: Fires when hold < 5 min AND loss AND no SL/SL-M exit order. The SL detection checks `exit_types & {"SL", "SL-M", "SLM", "SL-MKT"}`. Logic is sound.  
**Minor**: `hold_min = (ct.exit_time - ct.entry_time).total_seconds() / 60` uses wall-clock time, not `duration_minutes`. For an intraday trade this is fine. For NRML this could give a negative or enormous number if entry/exit span dates — but `panic_exit` is typically relevant only for quick exits, so NRML positions held for days would have hold_min >> 5 and not fire. Correct.

---

### Pattern 7: martingale_behaviour
**File**: behavior_engine.py:713–777  
**Status**: MINOR_ISSUE  
**Finding 1**: Requires `len(prior) >= 2` (line 733), so at least 2 prior trades on same underlying. Then computes `max_ratio` over consecutive size steps.  
**Finding 2 (BUG — semantic)**: The `max_ratio` check uses `prior` (up to the last 3 session trades), but then the message string includes `all_sizes = sizes + [ct.total_quantity or 1]` (line 750), displaying the current trade's size. However, `max_ratio` was computed only on `prior`, NOT including the current trade. The alert fires based on the *prior* trades doubling, then appends the current trade for display. This means: if prior trades showed martingale (doubling), the alert fires on the NEXT trade even if that next trade is smaller. The interpretation is "you have been doing martingale — your current trade continues that context", which is a reasonable framing. But if the current trade is actually *smaller* than prior, the martingale sequence may have ended, yet the alert still fires. Marginal false positive.  
**Finding 3**: `loss_count` counts any loss in the prior trades (not just consecutive). `min_losses = 2` means at least 2 of the prior 3 trades must be losses. This is correct — martingale is "doubling up after losses", so 2/3 losing is appropriate.  
**Impact**: Occasional false positive when martingale-sequence is resolving.  
**Fix**: Include current trade's size in `max_ratio` calculation, or add a guard that the current trade's size >= last prior trade's size.

---

### Pattern 8: cooldown_violation
**File**: behavior_engine.py:781–798  
**Status**: CRITICAL_BUG  
**Finding**: See CROSS-6. The method exists and logic is correct, but it is **never called** — it is missing from the `_run_all_detectors` list (line 334–358). Active cooldown violations produce zero alerts.  
**Impact**: CRITICAL — the entire cooldown system is silently non-functional. Users can trade through cooldowns with no feedback.  
**Fix**: Add `self._detect_cooldown_violation` to the detector list. Per the memory notes, if the intent is to suppress the alert but still count it in risk scoring, add it with `severity = "info"` and filter it before saving to DB.

---

### Pattern 9: rapid_flip
**File**: behavior_engine.py:802–841  
**Status**: MINOR_ISSUE  
**Finding 1**: Correctly checks `last.direction != ct.direction` for a flip. Uses `ct.entry_time - last.exit_time` for the gap — this is the correct measure (exit of prior → entry of current in opposite direction).  
**Finding 2 (MINOR_ISSUE)**: The guard `if gap_min < window` fires for values in range `[0, window)`. A gap of exactly `window` minutes does NOT fire. The code uses `< window` (strict), which is consistent with a "within N minutes" definition.  
**Finding 3 (BUG — options CE/PE flip not covered)**: `rapid_flip` detects direction reversal on the same `tradingsymbol`, checking `last.direction` (LONG/SHORT). However, the more common and dangerous flip in F&O is buying a NIFTY CALL, closing it, then immediately buying a NIFTY PUT — same underlying, opposite market view. This is covered by `_detect_options_direction_confusion` (Pattern 16), but that pattern checks `instrument_type` (CE vs PE) flip only for LONG options. If a trader short-sells a call then short-sells a put (both SHORT direction), neither `rapid_flip` nor `options_direction_confusion` would catch the directional confusion. Edge case but worth noting.  
**Impact**: Low — most common flip scenarios are covered.

---

### Pattern 10: excess_exposure
**File**: behavior_engine.py:845–887  
**Status**: MINOR_ISSUE  
**Finding 1**: Uses `estimate_capital_at_risk()` which uses SPAN margin approximations. For futures, SPAN is approximated at 10–15% of notional. For LONG CE/PE, uses full premium (correct). For SHORT options, uses SPAN approximation.  
**Finding 2 (MINOR_ISSUE)**: Guard `if not capital or float(capital) < 10000: return None` — silently skips for all users with no profile or capital < ₹10,000. This means the most under-capitalised traders (most at risk of over-exposure) never get excess_exposure alerts. The comment in `_detect_session_meltdown` at line 905 says "The ≥10k floor was wrong — a ₹5k account can still blow up" but this fix was only applied to session_meltdown, not excess_exposure.  
**Impact**: Excess exposure detection completely disabled for small accounts.  
**Fix**: Remove the ₹10,000 floor, or lower it significantly (e.g., ₹1,000).

---

### Pattern 11: session_meltdown
**File**: behavior_engine.py:891–941  
**Status**: MINOR_ISSUE  
**Finding 1**: When `daily_loss_limit` is not set, falls back to 5% of `trading_capital`. This is reasonable.  
**Finding 2 (MINOR_ISSUE)**: If neither `daily_loss_limit` nor `trading_capital` is set (true cold start), the pattern returns `None` silently. This means users with no profile configuration never get meltdown alerts even if they're losing large amounts. Cross-reference: `excess_exposure` has the same gap.  
**Finding 3**: Strategy group net P&L check at line 893–897: if `strategy_group.net_pnl >= 0 and leg_pnl < 0`, skips. This is correct — a losing hedge leg in a net-profitable strategy should not contribute to meltdown detection.  
**Finding 4 (MINOR_ISSUE)**: `session_pnl = Decimal(str(ctx.session.session_pnl or 0))`. If session_pnl is updated asynchronously and lags, the meltdown may fire slightly late or not at all for the exact trade that crosses the threshold. Low-risk in practice.

---

### Pattern 12: fomo_entry
**File**: behavior_engine.py:950–1022  
**Status**: BUG  
**Finding 1 (BUG)**: The `fomo_close_window_min` threshold uses `fomo_open_symbols` (line 999), not `fomo_close_window_min` or a dedicated close-window symbol count threshold. This is a copy-paste error:
```python
elif is_close_window:
    threshold = fomo_open_symbols   # <-- should be fomo_close_symbols or similar
    context_note = "pre-close"
```
The close-window applies the **opening** threshold (2 underlyings) instead of the general threshold (3 underlyings). This makes end-of-day FOMO fire with only 2 underlyings in 30 min — arguably intentional for risk purposes, but it's unnamed and there is no `fomo_close_symbols` threshold defined in `trading_defaults.py`.  
**Impact**: Pre-close FOMO fires at 2 underlyings instead of 3. Could be intentional but is inconsistently documented.  
**Fix**: Define `fomo_close_symbols` in `trading_defaults.py` and use it here; or confirm the open=close threshold intent and document it.

**Finding 2 (BUG)**: The `window_trades` list at line 980–984 includes trades where `window_start <= t.entry_time <= ct.entry_time`. The condition `t.entry_time <= ct.entry_time` includes the current trade (`ct`) itself (its entry_time == ct.entry_time). The current trade's underlying will always be in `distinct_underlyings`. If a trader enters only 1 new underlying but had 2 others in the window, `distinct_underlyings` = 3 and the alert fires. This is correct. However if the trader enters the same underlying twice in the window, it still counts as 1 distinct underlying — also correct. No bug here.

**Finding 3 (MINOR_ISSUE)**: `is_expiry_day` is imported from `instrument_parser` using a late import inside the function (`from app.services.instrument_parser import parse_symbol, is_expiry_day as _is_expiry_day`). This is fine but the import shadows `is_expiry_day` in a way that could be confusing. Not a bug.

**Finding 4 (MINOR_ISSUE)**: The `is_open_window` guard uses `0 <= mins_after_open <= fomo_open_window_min`. If `entry_ist < market_open` (e.g., a pre-market or overnight trade), `mins_after_open` is negative, so `is_open_window = False`. Correct.

---

### Pattern 13: no_stoploss
**File**: behavior_engine.py:1029–1123  
**Status**: MINOR_ISSUE  
**Finding 1**: Monthly expiry detection uses `len(_parsed.expiry_key) == 7`. Monthly expiry_key format is `"YYYY-MM"` which is indeed 7 chars. Weekly is `"YYYY-MM-DD"` which is 10 chars. EQ has `expiry_key = ""` (0 chars). This is correct.  
**Finding 2 (BUG — threshold duplication in trading_defaults.py)**: `trading_defaults.py` defines `no_stoploss_monthly_hold_min` and `no_stoploss_monthly_loss_pct` **twice** — once at line 111–112 and again at lines 167–168. The second definition overwrites the first since it's in the same `COLD_START_DEFAULTS` dict. The values are the same (5 min, 20%), so no functional impact today, but this is a latent bug — a future edit to one copy would silently be overridden.  
**Impact**: Low risk today (same values); high risk of confusion if values diverge.  
**Fix**: Remove the duplicate definition at lines 111–112 (or 167–168).

**Finding 3 (MINOR_ISSUE)**: `duration = ct.duration_minutes or 0`. `duration_minutes` is a computed field on `CompletedTrade`. If it's NULL (not yet computed), `duration = 0` and the condition `duration < hold_threshold` will be True (0 < 5), so the function returns None. This means trades with uncomputed durations are silently skipped, not flagged.  
**Impact**: Missed alerts when `duration_minutes` is NULL.  
**Fix**: Fall back to computing duration from `entry_time`/`exit_time` if `duration_minutes` is None.

**Finding 4 (MINOR_ISSUE)**: For FUT instruments, `capital_at_risk` is estimated via SPAN margin approximation. The `loss_pct` is then `abs(pnl) / capital_at_risk * 100`. If the SPAN estimate is too low, `loss_pct` will be inflated and more alerts will fire than warranted. If too high (which is more common), fewer alerts fire. The approximation errs towards over-estimating margin, which under-estimates loss_pct — i.e., fewer false positives but more false negatives. Acceptable tradeoff.

---

### Pattern 14: early_exit
**File**: behavior_engine.py:1130–1171  
**Status**: MINOR_ISSUE  
**Finding 1**: Only fires when the **current** trade is a winner (`pnl > 0`). This ensures the pattern fires in context — "you just closed a winner quickly, and historically you hold losers longer". Correct semantic.  
**Finding 2**: Uses `t.duration_minutes` for both winners and losers. If `duration_minutes` is NULL for some trades, those trades are excluded from `winners` / `losers` lists (the `and t.duration_minutes` guard). If many trades have NULL duration, the sample size may be artificially inflated below `min_samples = 3`, causing the pattern to not fire.  
**Finding 3 (MINOR_ISSUE)**: The condition checks `avg_winner_hold < avg_loser_hold * ratio_threshold AND avg_winner_hold < max_winner_min`. The second condition (`avg_winner_hold < 20 min`) prevents false positives when both winners and losers are held very briefly. However, if `avg_winner_hold = 25` min and `avg_loser_hold = 120` min, the ratio is `25/120 = 0.21 < 0.40` but `avg_winner_hold` is NOT `< 20`, so no alert fires. A trader who holds winners 25 min and losers 2 hours has a clear disposition effect that goes undetected.  
**Impact**: Significant false negative when winners are held for 20–40 min but losers are held much longer.  
**Fix**: Either remove the `avg_winner_hold < max_winner_min` condition, or increase `max_winner_min` to 60.

---

### Pattern 15: winning_streak_overconfidence
**File**: behavior_engine.py:1178–1235  
**Status**: CORRECT  
**Finding 1**: `is_win_streak(n)` checks `prior[-n:]` — the last N trades before current. `prior` filters `t.id != ct.id`, so current trade is excluded. Correct.  
**Finding 2**: Danger (5 consecutive wins) fires regardless of current trade size. Caution (3 consecutive wins) requires size escalation (`current_qty >= avg_streak_qty * 1.3`). Logic is sound.  
**Finding 3 (MINOR_ISSUE)**: If a trader has exactly 5 wins, both `is_win_streak(5)` and `is_win_streak(3)` would be true. The code checks danger first (`if is_win_streak(danger_streak)`) and returns early, so only the danger alert fires. Correct priority.

---

### Pattern 16: options_direction_confusion
**File**: behavior_engine.py:1243–1292  
**Status**: MINOR_ISSUE  
**Finding 1**: Only fires for `ct.direction == "LONG"` and `prior.direction == "LONG"`. A SHORT CE → SHORT PE flip (writing the other side) is not detected. This is intentional since short options strategies are generally more sophisticated.  
**Finding 2 (BUG)**: The check `if not (window_start <= prior.exit_time <= ct.entry_time)` finds priors that exited within the confusion window. But there is no check that `prior.exit_time <= ct.entry_time` — wait, actually the condition `prior.exit_time <= ct.entry_time` IS checked as part of the range. Let's trace: `window_start = ct.entry_time - timedelta(minutes=window_min)`. Condition: `window_start <= prior.exit_time <= ct.entry_time`. So `prior.exit_time` must be between `(ct.entry_time - 10 min)` and `ct.entry_time`. If a trader exited a NIFTY CE at 10:00 and entered a NIFTY PE at 10:08, `window_start = 09:58`, and `prior.exit_time (10:00)` is in range — fires. Correct.  
**Finding 3 (MINOR_ISSUE)**: The loop returns on the **first** matching prior trade found in `ctx.session_trades` (no sort by exit_time). `session_trades` is sorted by `exit_time ASC`, so iterating it in order means the **earliest** matching prior is found, not the most recent. The alert message says "You flipped from X to Y in N min" but N is calculated from this earliest matching prior, which could be an older trade than the most relevant one. Should use the **most recent** prior in the window.  
**Fix**: Find the most recent prior in the confusion window rather than the first found.

---

### Pattern 17: options_premium_avg_down
**File**: behavior_engine.py:1299–1351  
**Status**: CORRECT  
**Finding 1**: Correctly finds all prior LONG CE/PE trades on the same underlying that lost >= 20% of premium. Then fires if any exist. Severity is always "caution" regardless of how many prior losers.  
**Finding 2 (MINOR_ISSUE)**: No severity escalation — whether there is 1 prior loser or 5, it's always "caution". Consider escalating to "danger" after 2+ prior losers on the same underlying.  
**Finding 3 (MINOR_ISSUE)**: The message shows `len(prior_losers)` and the worst loss percentage. `worst_pct` is computed from `max(prior_losers, key=lambda x: x[1])`. Correct.

---

### Pattern 18: iv_crush_behavior
**File**: behavior_engine.py:1359–1399  
**Status**: MINOR_ISSUE  
**Finding 1**: The proxy logic is: LONG CE/PE + lost > 40% premium + held < 30 min = IV crush. This is a reasonable heuristic proxy.  
**Finding 2 (MINOR_ISSUE)**: **Overlap with premium_destruction**: `iv_crush_behavior` fires when `loss_pct >= 40` and `hold_min < 30`. `premium_destruction` fires when `loss_pct >= 60` (i.e., pnl_pct < -60%) regardless of hold time. There is significant overlap: a LONG option that loses 65% of premium in 20 min would trigger **both** `iv_crush_behavior` (65% > 40% in < 30 min) and `premium_destruction` (65% > 60%). Both fire on the same trade generating 2 alerts for the same underlying loss event.  
**Impact**: Alert duplication — noisy UX, inflated risk score (+10 + +25 = +35 for the same event).  
**Fix**: Add an `or` guard: if `premium_destruction` would fire, skip `iv_crush_behavior` (the stronger pattern covers it). Or add `iv_crush_behavior` to dedup against `premium_destruction`.

**Finding 3 (MINOR_ISSUE)**: `hold_min = ct.duration_minutes or 0`. Same NULL-duration issue as no_stoploss — trades with NULL duration will have `hold_min = 0 < 30`, so they pass the hold threshold check and the alert may fire on trades that didn't really qualify. In this case it errs towards false positives.  
**Fix**: Fall back to computing hold_min from `entry_time`/`exit_time`.

---

### Pattern 19: premium_destruction
**File**: behavior_engine.py:1413–1466  
**Status**: MINOR_ISSUE  
**Finding 1 (BUG — fallback computation)**: When `ct.pnl_pct` is None, the fallback is:
```python
loss_pct = (exit_price - entry_price) / entry_price * 100
```
This computes per-unit P&L percentage, NOT total P&L as percentage of total premium paid. For an options trade, if `avg_entry_price = 100` and `avg_exit_price = 30`, `loss_pct = (30 - 100) / 100 * 100 = -70%`. The stored `pnl_pct` would likely be computed the same way (per-unit), so this is consistent. But if `realized_pnl` is used in the message (`ct.realized_pnl`), the message could show a large absolute loss while `loss_pct` shows per-unit percentage — potentially inconsistent framing.  
**Finding 2 (MINOR_ISSUE)**: The prior_destruction count uses the same fallback formula inline at line 1440–1443 — a complex nested expression. This is hard to read and maintain.  
**Finding 3 (MINOR_ISSUE)**: The threshold check is `if loss_pct >= threshold: return None` where `threshold = -60`. Since `loss_pct` is negative (e.g., -70), and -70 < -60, the condition `-70 >= -60` is False, so the trade proceeds. If `loss_pct = -55`, then `-55 >= -60` is True and it returns None. Logic is correct but unintuitive (threshold is stored as a negative number).  
**Finding 4 (MINOR_ISSUE)**: Alert severity is "danger" only if there are prior destruction trades today. First destruction = "caution". This is reasonable escalation.

---

### Pattern 20: expiry_day_overtrading
**File**: behavior_engine.py:1474–1528  
**Status**: MINOR_ISSUE  
**Finding 1**: Uses `is_expiry_day(ct.tradingsymbol, entry_ist.date())` from `instrument_parser.py`. For weekly options, this is an exact date match. For monthly options/futures, it computes last Thursday of the contract month. This is correct and no longer uses the hardcoded `weekday() == 3`.  
**Finding 2 (BUG — monthly expiry holiday not handled)**: `is_expiry_day` for monthly contracts returns `expected_expiry = _last_thursday_of_month(...)`. When the last Thursday is an NSE holiday, NSE moves expiry to Wednesday — but `is_expiry_day` still returns the original Thursday. On the actual expiry (Wednesday), `is_expiry_day` would return False, missing the entire expiry day overtrading pattern. This is documented in `instrument_parser.py`'s docstring but is still a gap.  
**Impact**: On holiday-adjusted expiry months (several per year), the expiry_day_overtrading pattern completely misses the actual expiry day and may fire on a regular Thursday instead.  
**Fix**: Integrate with `is_trading_holiday()` in `market_hours.py` to step back when the last Thursday is a holiday.

**Finding 3 (MINOR_ISSUE)**: Cold-start gate: `if entry_ist.hour < 13: return None`. This means any expiry day trade before 13:00 IST does not trigger `expiry_day_overtrading`. This is a conservative design choice. The downside: a trader who does all 8+ expiry trades before 13:00 never gets an alert. Only the trade at or after 13:00 (if there is one) would trigger it. If the trader stops at noon, they get no alert despite excessive trading.

**Finding 4 (MINOR_ISSUE)**: `today_expiry_trades` is built by iterating `ctx.session_trades` and checking `parse_symbol(t.tradingsymbol).underlying == underlying`. This calls `parse_symbol` for every session trade on every invocation of this pattern. Since `_run_all_detectors` runs all 23 patterns for each completed trade, and this inner loop also runs for `_detect_fomo_entry`, there is significant repeated parsing work. Not a bug but a performance issue for high-frequency traders.

---

### Pattern 21 (named 20 in comment): opening_5min_trap
**File**: behavior_engine.py:1536–1619  
**Status**: MINOR_ISSUE  
**Finding 1 (MINOR_ISSUE — naming mismatch)**: The comment header says "Pattern 20: Opening 5-minute trap" (line 1530) but the pattern is actually the 21st in the list. The docstring header also calls it "opening_5min_trap" but the window is 09:15–09:25, which is 10 minutes. The name "5-minute trap" does not match the implementation window. The comment at line 1533 says "Derivative entry in the 09:15–09:20 IST window" but the code uses `trap_end = entry_ist.replace(hour=9, minute=25, ...)` making it 09:15–09:25 (10 minutes).  
**Impact**: Documentation mismatch only — user-facing message says "09:15–09:25 window" which matches the code. No functional bug.

**Finding 2 (MINOR_ISSUE)**: `is_quick_reactive = duration <= 15`. The duration cutoff is 15 minutes, which is much wider than "opening 5-minute trap". A trade entered at 09:24 and held for 15 min exits at 09:39 — this is not really an "opening trap" anymore. The entry window (09:15–09:25) is the key constraint.  
**Impact**: Minor — the entry window constraint is tight, so the 15-min exit window is secondary.

**Finding 3**: `loss_pct` is only computed for CE/PE (options), not FUT:
```python
if ct.instrument_type in ("CE", "PE") and entry_price > 0 and qty > 0:
    loss_pct = abs(pnl) / (entry_price * qty) * 100
```
For FUT, `loss_pct = 0`. So `is_large_loss` (loss_pct >= 30) will never fire for FUT entries. The pattern still fires via `is_quick_reactive` for FUT trades, but never escalates to "danger" (which requires both quick and large loss). FUT losses in the opening window can be substantial in absolute terms. Acceptable trade-off.

---

### Pattern 22 (named 21 in comment): end_of_session_mis_panic
**File**: behavior_engine.py:1626–1675  
**Status**: MINOR_ISSUE  
**Finding 1**: Pattern number in comment is "21" (line 1621) but it's listed 22nd in the detector list. Off-by-one in numbering throughout the file (multiple patterns are numbered incorrectly in comments).

**Finding 2 (BUG — auto-squareoff time is broker-specific and approximate)**: The code hardcodes `15:20` as Zerodha's auto-square-off time in the message:
```python
f"Zerodha auto-squares MIS at 15:20."
```
And `mins_remaining = max(0, (15 * 60 + 20) - (entry_ist.hour * 60 + entry_ist.minute))`. Zerodha's actual auto-square-off time is **15:15 for equity MIS** and **15:25 for F&O MIS**. The code uses 15:20 as a single value for both, which is wrong for both segments. F&O MIS actually gets 5 extra minutes (15:25), meaning the alert is more urgent than coded. Equity MIS traders have less time (15:15) than the 15:20 shown.  
**Impact**: Incorrect time shown to users; wrong urgency calculation.  
**Fix**: Use segment-aware auto-square-off time: NFO/BFO = 15:25, NSE/BSE equity = 15:15. Check `ct.exchange` or `ct.instrument_type`.

**Finding 3 (MINOR_ISSUE)**: `panic_start` is hardcoded to `15:00` IST. Comment says "MIS trades entered after 15:10". The MEMORY.md says "window 15:10 → 15:00" was a bug fix, meaning 15:00 is the intended current value. The current code at line 1634 uses 15:00 and the comment at line 1621 says "MIS entries after 15:10" — documentation is stale. Not a functional bug since the code is 15:00 which is the fixed value.

**Finding 4 (MINOR_ISSUE)**: The `panic_trades` count includes the current trade in `ctx.session_trades`. Since the current trade is an MIS trade entered after 15:00, it should be counted. The count is correct.

---

### Pattern 23 (named 22 in comment): post_loss_recovery_bet
**File**: behavior_engine.py:1683–1754  
**Status**: MINOR_ISSUE  
**Finding 1**: Requires `len(trades) < 3: return None`. Then `prior` = all non-current trades on same underlying sorted by exit_time, and `len(prior) < 2: return None`. Then checks last 2 are losses. The **average** is computed from `prior[-3:]` (last 3 prior trades):
```python
recent_qtys = [t.total_quantity or 1 for t in prior[-3:]]
avg_qty = sum(recent_qtys) / len(recent_qtys)
```
If there are exactly 2 prior trades, `prior[-3:]` returns all 2. The average is of 2 trades (both are confirmed losses). If there are 3+ prior trades, the average is of the last 3 (of which last 2 are confirmed losses, the 3rd could be a win). Using 3 trades to average is correct for context.

**Finding 2 (BUG — denominator inconsistency)**: When `len(prior) == 2`, `recent_qtys = [qty0, qty1]` and `avg_qty = (qty0 + qty1) / 2`. The current trade size is then compared: `size_ratio = current_qty / avg_qty`. But the `last_two_pnls` check requires EXACTLY the last 2 to be losses — and the average uses 2–3 trades. If there are exactly 2 prior trades and both are losses with small sizes (e.g., 50, 50), avg = 50, and a 100 qty current trade gives ratio = 2.0, firing caution. This is correct behaviour. No bug, just wanted to confirm.

**Finding 3 (MINOR_ISSUE)**: The `total_prior_loss` only sums `last_two_pnls` (the 2 losses), not all losses in `prior[-3:]`. So the message "After 2 NIFTY losses (₹X total)" refers to only the last 2, which is correct and unambiguous.

**Finding 4 (MINOR_ISSUE)**: Unlike `martingale_behaviour`, this pattern is **not in `_STRATEGY_SUPPRESSED`**. A hedge leg buying protective options after 2 losing legs could trigger this. For example, in an iron condor built over several exits, the last protective buy could appear to be a "recovery bet." Consider adding to `_STRATEGY_SUPPRESSED`.

---

### Pattern 23 (actual): profit_giveaway
**File**: behavior_engine.py:1770–1845  
**Status**: MINOR_ISSUE  
**Finding 1**: Computes `peak_pnl` by running cumulative P&L through `session_trades` in exit_time order and tracking the maximum. This is correct.  
**Finding 2 (BUG — peak_pnl includes current trade)**: `trades = ctx.session_trades` which includes `completed_trade`. The running P&L loop includes the current trade in the peak computation. If the current trade is a large loss that brings P&L from a peak down, `peak_pnl` was set before this trade, and `current_pnl` (running_pnl) includes this trade's loss. `erosion = peak_pnl - current_pnl` correctly captures the drawdown. However, `peak_pnl` was the max OVER ALL trades including the current one. If the current trade somehow has positive P&L (unlikely for profit_giveaway to trigger, but it runs for all trades), the loop updates `peak_pnl` to include it. The logic is: even if the current trade is a winner, the overall session may have eroded from a prior peak. The comment at line 1776 explicitly notes this. Logic is correct, just non-obvious.  
**Finding 3 (MINOR_ISSUE)**: Dedup is handled by the 2h window in `trade_tasks.py`. The comment at line 1802 says "No 'first crossing' guard here — DB-level dedup prevents this from firing more than once per session." This is true for the 2h window. But if a trader gives back 50% of peak, then gains some back, then gives back another 50%, the alert would fire again after 2h. This is intentional per the design.  
**Finding 4 (MINOR_ISSUE)**: `erosion = peak_pnl - current_pnl`. If `current_pnl > peak_pnl` (currently at all-time-high), `erosion < 0`, and `erosion < min_erosion` returns None. Correct.

---

## run_risk_detection_async: Invocation Issues

### INVOKE-1: Engine only runs on the MOST RECENT completed trade
**File**: trade_tasks.py:523–529  
**Status**: BUG  
**Finding**: `run_risk_detection_async` fetches only the single most recent `CompletedTrade` via `.limit(1)` and runs the engine on that one trade. This means patterns like `consecutive_loss_streak`, `size_escalation`, and `martingale_behaviour` only get the most recent context — they're computed from `ctx.session_trades` which includes all today's trades. So the PATTERN DETECTION itself is correct (uses full session). However, consider this scenario: 3 quick losses happen in sequence. Webhooks fire nearly simultaneously. The FIFO lock serializes them, but each call to `run_risk_detection_async` fetches `latest CompletedTrade` again — which may be the SAME trade for two concurrent calls if the ledger hasn't flushed yet.  
**Impact**: Moderate — in practice the `behavior_lock` (TTL=15s) prevents concurrent runs. The issue is more of a theoretical race.

### INVOKE-2: Full-session replay (run_behavior_engine_full_session) does not update dedup state between iterations
**File**: trade_tasks.py:625–698  
**Status**: BUG  
**Finding**: In `run_behavior_engine_full_session`, `last_fired` and `today_patterns` are initialized from **existing** DB alerts. For each trade in the loop, `_is_deduped_full` checks if the pattern was fired within the dedup window. After adding a new alert, `last_fired[alert.pattern_type] = now_utc` is updated in memory but `today_patterns` is only checked, not updated inline. Actually, let me re-read...

At line 693+, the loop does commit per-alert but the dedup state in-memory is updated: `last_fired[alert.pattern_type] = now_utc`. However, the DB commits happen inside the inner loop but `all_existing` was fetched once before the loop. If two trades in sequence would both fire `revenge_trade` in different 2-hour windows (for patterns with 24h dedup), the first fires and updates `last_fired`, and the second correctly gets deduplicated. This is correct.

**HOWEVER**: The dedup window for a pattern fired inside the loop uses `now_utc` (current wall clock) as the timestamp for the newly emitted alert, not the historical trade's exit_time. So if running a full-session replay at 16:00 for trades that happened at 10:00 and 11:00, both would mark `last_fired[pattern] = now_utc (16:00)` in memory. The second trade would be deduplicated because `(16:00 - 16:00) < 2 hours`. But it SHOULD fire because the events were 1 hour apart in real trading time. This means **full-session replays can suppress alerts that should have fired in sequence**.  
**Impact**: Full-session replays (REST sync path) may miss the 2nd+ occurrence of streak patterns that would have fired in real-time.  
**Fix**: Use `ct.exit_time` as the `last_fired` timestamp instead of `now_utc` when replaying historical sessions.

---

## is_expiry_day — Holiday Adjustment Gap

### EXPIRY-1: Monthly expiry holiday adjustment not implemented
**File**: instrument_parser.py:181–209  
**Status**: ~~BUG~~ **RESOLVED (already fixed)**  
**Finding**: ~~`_last_thursday_of_month()` does not check NSE holidays.~~  
**Resolution**: `_last_thursday_of_month()` already calls `is_trading_holiday(d)` and walks back until it lands on a trading day (lines 178–179). The docstring on `is_expiry_day` was stale and incorrectly described this as an open gap. Docstring corrected 2026-06-12.

---

## trading_defaults.py Issues

### DEFAULTS-1: Duplicate key `no_stoploss_monthly_hold_min` / `no_stoploss_monthly_loss_pct`
**File**: trading_defaults.py:111–112 and 167–168  
**Status**: BUG  
**Finding**: Both keys are defined twice in `COLD_START_DEFAULTS`. Python dicts use the last definition, so lines 167–168 take effect. Values happen to be identical (5 and 20), but this is a ticking time bomb.  
**Fix**: Remove lines 111–112.

### DEFAULTS-2: `get_thresholds` danger level for daily trade limit derived from caution
**File**: trading_defaults.py:269  
**Status**: MINOR_ISSUE  
**Finding**: `result['daily_trade_danger'] = int(result['daily_trade_limit'] * 1.5)`. If user sets `daily_trade_limit = 5`, danger becomes `7`. Default: limit=7 → danger=10.5 → int=10. But `COLD_START_DEFAULTS['daily_trade_danger'] = 12`. So when a user profile has `daily_trade_limit = 7` (same as default), `daily_trade_danger` becomes 10, not 12. The user's declared limit can inadvertently lower the danger threshold even without them setting a danger threshold. Whether this is desirable is debatable.  
**Impact**: Lower danger threshold than documented when user declares any trade limit.  
**Fix**: Only compute `daily_trade_danger` from user limit if user explicitly set it; otherwise keep the research default (12).

---

## market_hours.py Issues

### MKT-1: NSE_HOLIDAYS_2026 is incomplete
**File**: market_hours.py:42–49  
**Status**: ~~MINOR_ISSUE~~ **RESOLVED**  
**Finding**: ~~Only 6 dates in NSE_HOLIDAYS_2026.~~  
**Resolution**: `NSE_HOLIDAYS_2026` now has 14 dates: Republic Day, Mahashivratri, Holi, Ram Navami, Good Friday, Ambedkar Jayanti, Maharashtra Day, Bakri Id (tentative), Ganesh Chaturthi, Gandhi Jayanti, Diwali Laxmi Puja, Diwali Balipratipada, Guru Nanak Jayanti, Christmas. Verified 2026-06-12.

---

## Summary Table

| ID | Pattern | Status | Severity |
|----|---------|--------|----------|
| CROSS-1 | session_trades includes current trade | ~~MINOR_ISSUE~~ RESOLVED (2026-06-12) | Low |
| CROSS-2 | consecutive_loss_streak double-build | MINOR_ISSUE | Low |
| CROSS-3 | session_trades exit_time vs entry_time | MINOR_ISSUE | Low |
| CROSS-4 | Decimal/float mixing | MINOR_ISSUE | Low |
| CROSS-5 | Incomplete strategy suppression set | MINOR_ISSUE | Medium |
| CROSS-6 | cooldown_violation never called | CRITICAL_BUG | Critical |
| Pat-1 | consecutive_loss_streak: fragile dual-loop | MINOR_ISSUE | Low |
| Pat-2 | revenge_trade: non-deterministic on same-exit-time | MINOR_ISSUE | Low |
| Pat-3 | overtrading_burst: daily caution gate too strict | BUG | Medium |
| Pat-4 | size_escalation: current trade excluded from escalation seq | MINOR_ISSUE | Low |
| Pat-6 | panic_exit: wall-clock vs duration_minutes | MINOR_ISSUE | Low |
| Pat-7 | martingale_behaviour: current trade not in max_ratio | MINOR_ISSUE | Low |
| Pat-8 | cooldown_violation: never called | CRITICAL_BUG | Critical |
| Pat-10 | excess_exposure: ₹10k floor silences small accounts | MINOR_ISSUE | Medium |
| Pat-11 | session_meltdown: silent when no profile | MINOR_ISSUE | Medium |
| Pat-12 | fomo_entry: close-window uses open-window threshold | BUG | Medium |
| Pat-13 | no_stoploss: duplicate threshold keys | BUG | Low |
| Pat-13 | no_stoploss: NULL duration_minutes skips detection | MINOR_ISSUE | Medium |
| Pat-14 | early_exit: max_winner_min too low (20 min) | MINOR_ISSUE | Medium |
| Pat-16 | options_direction_confusion: uses earliest not most recent prior | MINOR_ISSUE | Low |
| Pat-17 | options_premium_avg_down: no severity escalation | MINOR_ISSUE | Low |
| Pat-18 | iv_crush_behavior: overlaps with premium_destruction | MINOR_ISSUE | Medium |
| Pat-18 | iv_crush_behavior: NULL duration = false positive | MINOR_ISSUE | Medium |
| Pat-19 | premium_destruction: fallback pnl_pct formula | MINOR_ISSUE | Low |
| Pat-20 | expiry_day_overtrading: holiday-adjusted expiry not handled | BUG | High |
| Pat-21 | opening_5min_trap: name says 5-min, window is 10-min | MINOR_ISSUE | Low |
| Pat-22 | end_of_session_mis_panic: wrong auto-squareoff time (15:20 vs 15:15/15:25) | BUG | Medium |
| Pat-22 | end_of_session_mis_panic: stale comment says 15:10 | MINOR_ISSUE | Low |
| Pat-23 | post_loss_recovery_bet: not in _STRATEGY_SUPPRESSED | MINOR_ISSUE | Low |
| INVOKE-1 | run_risk_detection_async: latest CT only | ~~MINOR_ISSUE~~ RESOLVED (2026-06-12) | Low |
| INVOKE-2 | run_behavior_engine_full_session: dedup uses now_utc not trade time | BUG | Medium |
| EXPIRY-1 | is_expiry_day: holiday adjustment not implemented | BUG | High |
| DEFAULTS-1 | trading_defaults: duplicate no_stoploss_monthly keys | BUG | Low |
| DEFAULTS-2 | trading_defaults: daily_trade_danger derivation | MINOR_ISSUE | Low |
| MKT-1 | market_hours: NSE_HOLIDAYS_2026 incomplete | MINOR_ISSUE | High |

---

## Priority Fix List (ordered by impact)

1. **CROSS-6 / Pat-8 — CRITICAL**: Add `self._detect_cooldown_violation` to the `_run_all_detectors` list. This is the most impactful bug — entire cooldown system is non-functional.

2. **EXPIRY-1 + MKT-1 — HIGH**: Fix `is_expiry_day()` to check `is_trading_holiday()` and step back on holidays. Complete `NSE_HOLIDAYS_2026`. These affect multiple patterns on several days per year.

3. **Pat-3 — MEDIUM**: Remove or relax the `session_pnl < 0` gate on the daily overtrading caution. A profitable overtrader should still see a caution alert.

4. **Pat-22 — MEDIUM**: Use segment-aware auto-square-off times: F&O MIS = 15:25, equity MIS = 15:15.

5. **Pat-12 — MEDIUM**: Define `fomo_close_symbols` threshold and use it for pre-close FOMO instead of reusing `fomo_open_symbols`.

6. **INVOKE-2 — MEDIUM**: In `run_behavior_engine_full_session`, use `ct.exit_time` as the `last_fired` timestamp for historical replay.

7. **Pat-18 — MEDIUM**: Suppress `iv_crush_behavior` when `premium_destruction` would also fire on the same trade.

8. **Pat-13 + Pat-18 — MEDIUM**: Fall back to computing hold minutes from `entry_time`/`exit_time` when `duration_minutes` is NULL.

9. **DEFAULTS-1 — LOW**: Remove duplicate `no_stoploss_monthly_*` keys from `COLD_START_DEFAULTS`.

10. **CROSS-5 — MEDIUM**: Add `rapid_reentry`, `no_stoploss`, and `post_loss_recovery_bet` to `_STRATEGY_SUPPRESSED` or add per-pattern strategy group checks.
