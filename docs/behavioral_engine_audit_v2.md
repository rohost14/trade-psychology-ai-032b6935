# Behavioral Engine — Full Audit v2
*Session 39 · 2026-06-17 · Discussion document — do not implement without approval*

---

## 1. What We Have: 24 Detectors in BehaviorEngine

The old doc (`16_behavioral_patterns_complete.md`) says 23 patterns, 15 in the engine. Reality today: **24 detectors** in `behavior_engine.py` + **8 frontend detectors** (some overlap). This document covers only the backend engine (truth source for all persisted alerts).

---

## 2. Pattern Inventory — All 24 Detectors

For each: current logic quality (1–5), known issues, and what needs fixing.

---

### #1 — `consecutive_loss_streak`
**What it does**: N consecutive losing CompletedTrades today fire caution (3) or danger (5).

**Quality**: 4/5

**Issues**:
- Dedup = 24h. Fires once per day even if trader goes 3→4→5 losses. Should re-fire at each new step (3 caution, then 5 danger is a severity escalation — that already passes dedup? Needs verification).
- No trade list in context. User can't see which 3 losses.

**Fix needed**: Add `loss_trades` list (symbol, pnl, exit_time) to context. Verify severity escalation (3→5) gets through dedup correctly.

**Notification**: YES — both caution and danger. This is the core tilt signal.

**My View**: Is 3 for caution and 5 for critical applicable to all users? lets say user does not have 3 consecutive loss but 2 losses 1 win and again 2 losses what then? is number of losses more imp or total amout loss? or maybe combination. My point it should not be generalized and same for all kind of users. While onboarding or in the app itself can we have per user variable for this? they would themselves set how many looses a day and amout of loss a day is acceptable, which can be locked for a month so they wont be able to change/update it.

---

### #2 — `revenge_trade`
**What it does**: New entry within 20 min of a loss (caution) or within 5 min (danger). Only if prior loss > ₹500.

**Quality**: 3/5

**Issues**:
- `trigger_trade_id = None` EVERYWHERE in the engine — the prior loss trade is identified in code but never stored in the alert record. User gets "revenge trade detected" but can't see which prior loss triggered it or which entry was the revenge.
- Context has `minutes_since_loss` and `prior_loss_amount` which is good — but no prior trade symbol, no entry symbol.
- ₹500 floor: a BANKNIFTY trade losing ₹499 on a small lot shouldn't escape this. Floor may need to be % of position, not absolute.

**Fix needed**: Store prior loss symbol + current entry symbol in context. Consider % floor, not absolute.

**Notification**: YES — danger especially. Caution = in-app is fine.

**My View**: Why do we have 20 mins hardcoded? And more so why do we have 500 hardcoded. On what basis are we deciding this is a revenge trade, We have to be almost sure that that is the case right, we cant just send false positive or keep giving alerts. This would actually take us time to figure out

---

### #3 — `overtrading_burst`
**What it does**: Sub-check 1: 5+ CompletedTrades with entry in rolling 30-min window. Sub-check 2: 7+ total session trades (caution) or 12+ (danger).

**Quality**: 4/5 *(just fixed — trade lists now in context)*

**Issues**:
- Open positions not counted (architectural constraint — engine only sees CompletedTrades). If 3 trades are still open, the real burst is undercounted. This is deferred.
- Daily count (check 2) and burst window (check 1) fire same pattern_type. Semantically different concerns but same name — makes it harder to differentiate in UI.
- Daily count thresholds (7/12) are research defaults. Very low for scalpers/high-frequency traders. A trader doing 20 trades/day profitably should NOT be getting this alert.

**Fix needed**: Consider splitting daily count into its own pattern_type (`daily_overtrading`). Adaptive thresholds critical here.

**Notification**: Burst danger = YES. Daily danger = YES. Burst caution = in-app.

**My View**: Why again have we hardcoded 5+ trades? Again for this cant we have a dynamic option a user itself will set the value which will be locked for a month. In this alert almost everything is hardcoded, how can we overcome this?

---

### #4 — `size_escalation`
**What it does**: 3-trade sequence where each trade has ≥30% bigger position than previous, all after losses.

**Quality**: 2/5

**Issues**:
- **Cross-instrument comparison bug** (same as the one we just fixed in overconfidence). If the 3-trade sequence spans NIFTY (75 qty/lot) → BANKNIFTY (30 qty/lot) → APLAPOLLO (400 qty), raw qty comparison is meaningless.
- No trade list in context. User can't see which 3 trades formed the escalation sequence.
- 30% threshold — is this right? 3 consecutive 30% increases = 2.2× original size. The first increase (30% up) might just be moving from 1 lot to 2 lots.

**Fix needed**: Same-underlying constraint (or lot-size normalised). Add `escalation_trades` list to context. Review 30% threshold.

**Notification**: In-app caution only (no push). This is an observation, not an emergency.

---

### #5 — `rapid_reentry`
**What it does**: Re-entering the same tradingsymbol within 5 min of closing it.

**Quality**: 3/5

**Issues**:
- `tradingsymbol` match is exact string. NIFTY2561825000CE and NIFTY2561825000PE are different symbols even though same underlying. Should catch direction flips on same underlying (but that's `rapid_flip`). These two patterns partially overlap.
- Only fires for same exact symbol re-entry. Does NOT catch: close NIFTY25JUN25000CE → immediately open NIFTY25JUN24900CE (different strike, same trap).

**Fix needed**: Consider adding underlying-level re-entry detection as an enhancement (different from rapid_flip which is direction reversal).

**Notification**: In-app only. Already happened, push too late and too noisy.

---

### #6 — `panic_exit`
**What it does**: Option position closed at a loss after holding < 5 min.

**Quality**: 3/5

**Issues**:
- Fires AFTER the exit. Push notification at this point = "you already panicked." Should this be an analytics/retrospective signal rather than a real-time alert?
- 5-min threshold: legitimate scalpers exit in < 5 min on SL hits (not panic). Primary gate should check exit_order_type — if SL/SL-M, it's a legitimate SL, not panic. Currently not checking this.
- Severity always "caution" — no danger level defined.

**Fix needed**: Check exit_order_type first (SL hits = skip). Add danger tier (< 1 min exit). Consider making this analytics-only (no user alert, just tracked).

**Notification**: In-app only (retrospective). OR analytics-only (no alert at all, just pattern tracking).

---

### #7 — `martingale_behaviour`
**What it does**: 1.5× or 2× position size on consecutive losing trades on same underlying.

**Quality**: 3/5

**Issues**:
- **Same underlying check**: This was added. Need to verify it's actually using `instrument_parser.parse_symbol().underlying` like we did for overconfidence. Check the code.
- Requires `martingale_min_losses = 2` consecutive losses. But if a profitable trade interrupts the sequence, the counter resets. Is this right? A trader losing, winning small, then doubling down on the next loss is still martingaling.
- No trade list in context.

**Fix needed**: Verify same-underlying check is in place. Add trade list to context.

**Notification**: Danger = YES (push). This is the pattern most likely to blow up an account.

---

### #8 — `cooldown_violation`
**What it does**: New entry while an active Cooldown record exists (from a prior loss cooldown).

**Quality**: 3/5

**Issues**:
- Currently severity = "info" → never shown to user, never pushed. The DB record exists but is invisible.
- This is functionally a duplicate of `revenge_trade` (both detect trading too soon after loss). The difference: revenge_trade uses time window, cooldown_violation checks an explicit DB Cooldown record.
- When exactly do we create Cooldown records? If `revenge_trade` fires AND Cooldown is created → both signals overlap. If Cooldown is only from user-declared cooldown setting, then this is meaningful.

**Fix needed**: Clarify separation from revenge_trade. Either remove (redundant) or make visible at caution level for users who set explicit cooldown in settings.

**Notification**: Keep info/invisible OR convert to in-app caution for users who explicitly configured cooldown.

---

### #9 — `rapid_flip`
**What it does**: Reversed direction (LONG→SHORT or vice versa) on same underlying within 10 min.

**Quality**: 4/5

**Issues**:
- On expiry day, 5-min reversals are legitimate (news reaction). Current 10-min window may catch real reversals on high-volatility sessions.
- Context doesn't include the P&L of the first position (was the flip after a loss? After a win?). Flip after a loss = probably emotional. Flip after a profit = could be strategy.
- Context doesn't include which direction flip.

**Fix needed**: Add P&L of prior position to context. Consider whether flip-after-profit is a behavioral alert at all.

**Notification**: In-app only. Retrospective.

---

### #10 — `excess_exposure`
**What it does**: Capital at risk for single trade > X% of declared trading capital.

**Quality**: 3/5

**Issues**:
- **Cold start problem**: If user hasn't set `trading_capital` in settings, this NEVER fires. Most users won't set this.
- Caution = 5%, danger = 10%. For a high-risk trader with large capital who regularly takes big positions, this is constant noise.
- `estimate_capital_at_risk()` for options LONG = notional (full premium). For options sellers and futures = SPAN approximation. The SPAN approx can be wildly off for hedged positions.
- For options buyers: if you buy 1 lot NIFTY CE at ₹200 (cost = ₹200 × 75 = ₹15,000) with ₹10L capital → 1.5% of capital. Won't fire. But the risk profile of buying deep OTM options vs ATM is very different. Premium destruction alert catches this instead.

**Fix needed**: Auto-estimate capital from first 30 sessions if not declared (use max session P&L loss as proxy). OR don't fire if trading_capital not set.

**Notification**: Danger = YES (push). Caution = in-app.

---

### #11 — `session_meltdown`
**What it does**: Session P&L losses exceed 40% (caution) or 75% (danger) of declared daily_loss_limit.

**Quality**: 3/5

**Issues**:
- **Cold start problem**: If no `daily_loss_limit` set → never fires. Critical pattern never active for most users.
- 40%/75% of daily_loss_limit: reasonable percentages. But daily_loss_limit must be accurate.
- No trade list showing what caused the meltdown.

**Fix needed**: Auto-derive daily_loss_limit from historical data if not declared. E.g., average of worst 10% of daily losses from last 90 days.

**Notification**: Danger = YES (push + WhatsApp guardian). This is THE most important alert.

---

### #12 — `fomo_entry`
**What it does**: Trading 3+ different underlyings within 30 min (2+ on expiry day or in first 30 min of session).

**Quality**: 3/5

**Issues**:
- FOMO detection is based purely on instrument diversity (scatter pattern). But 3 underlyings in 30 min could be a legitimate diversification strategy.
- Does NOT detect FOMO within a single instrument (buying more lots of same underlying in a panic). That's caught by `size_escalation` or `martingale_behaviour`.
- Context has `unique_underlyings_count` and `instruments` list. Good. But no P&L context for each.
- `fomo_symbols_at_open = 2` means buying NIFTY + BANKNIFTY in the first 30 min = FOMO? That's not always true.

**Fix needed**: Add session P&L context (buying multiple instruments while down = stronger signal). Review the at-open threshold — 2 underlyings in first 30 min is quite aggressive.

**Notification**: In-app only. Informational, not emergency.

---

### #13 — `no_stoploss`
**What it does**: Option position exits at ≥25% (caution) or ≥50% (danger) premium loss, held ≥5 min, AND exit_order_type was NOT a stop-loss order.

**Quality**: 4/5

**Issues**:
- Primary gate (exit_order_type check) is good — SL hits correctly excluded.
- 25% loss threshold fires quickly for deep OTM options where 30% premium loss in 5 min is normal. The threshold may need to be higher for options closer to expiry.
- Context doesn't show the entry time, exit time, or hold duration in a readable way.
- `premium_destruction` (pattern #19) also catches large premium losses. Overlap exists: a no_stoploss event is often also a premium_destruction event. They could fire for the same trade.

**Fix needed**: Add expiry proximity adjustment (higher threshold near expiry). Verify dedup prevents double-fire with premium_destruction on same trade.

**Notification**: Danger = YES (push). One of the most important patterns.

---

### #14 — `early_exit`
**What it does**: Session-level pattern. Fires if avg winner hold time < 40% of avg loser hold time (need 3+ winners and 3+ losers in session).

**Quality**: 3/5

**Issues**:
- Requires 3+ winners AND 3+ losers. For a trader doing 4 trades/day, this may never fire (only 1-2 of each type).
- Fires as a session-level retrospective, not on a specific trade. But the engine runs per-CompletedTrade. So this fires on every trade after the threshold is met, potentially firing multiple times in a session for the same pattern. Dedup window should handle this.
- The 40% ratio threshold: if losers avg 60 min hold and winners avg 25 min hold → 25/60 = 42% → no alert (just above 40%). Is 40% the right threshold?
- No specific trade breakdown in context (which winners were cut short, which losers were held).

**Fix needed**: Add `winner_trades` and `loser_trades` lists to context. Consider making this a daily EOD report item rather than a real-time alert.

**Notification**: In-app only. This is an analytical observation, not an emergency.

---

### #15 — `winning_streak_overconfidence`
**What it does**: Last 3 (caution) or 5 (danger) session trades all winners, AND current trade on same underlying is ≥1.3× (caution) or ≥2.0× (danger) session average size for that underlying.

**Quality**: 4/5 *(just fixed — same-underlying comparison)*

**Issues**:
- If trader's first trade today on an underlying is after 3 wins on OTHER underlyings → `avg_baseline = None` → no alert even if position is enormous. This is correct behavior per current design (can't assess without baseline), but first-trade-on-underlying is a common case.
- `streak_trades` list now in context. Good.
- The 1.3× caution threshold — for someone who normally does 1 lot, moving to 2 lots (100% increase) is caught. But for someone whose position sizes vary naturally between 1-3 lots, 1.3× is constant noise.

**Fix needed**: For first-trade-on-underlying after streak, fallback to using the streak trades' average size across ALL instruments (as a rough indicator). OR: add a note in context explaining why alert didn't fire.

**Notification**: In-app caution. Danger = push if 5+ wins + 2× size jump.

---

### #16 — `options_direction_confusion`
**What it does**: CE→PE or PE→CE flip on same underlying within 10 min.

**Quality**: 3/5

**Issues**:
- Overlaps with `rapid_flip` (#9). Both detect direction reversals. Difference: rapid_flip = same instrument (exact symbol), direction_confusion = same underlying but different option type. These SHOULD fire separately but could appear to the user as duplicate alerts.
- P&L of prior position not in context (was this flip after a loss?).
- 10 min window: on expiry day this is too tight (legitimate directional changes in 10 min on event days).

**Fix needed**: Merge with `rapid_flip` or clarify the distinction in alert messaging. Add P&L context.

**Notification**: In-app only. Overlaps with rapid_flip.

---

### #17 — `options_premium_avg_down`
**What it does**: Re-entering same options underlying after prior position lost ≥20% premium.

**Quality**: 3/5

**Issues**:
- "Averaging down" in options is almost never justified (options are wasting assets). This is the right pattern to detect.
- BUT: re-entering a call after a put lost money is not averaging down. The check should be: re-entering SAME DIRECTION (CE→CE or PE→PE) after a losing position on that underlying. Currently it may just check the underlying, not the direction.
- Context doesn't show the prior losing position or the re-entry direction.

**Fix needed**: Verify direction check is in place. Add prior position to context.

**Notification**: In-app caution. Danger if re-entry size is larger (martingale + avg down).

---

### #18 — `iv_crush_behavior`
**What it does**: Lost >40% of premium in <30 min (proxy for buying into high IV event, then IV collapses).

**Quality**: 3/5

**Issues**:
- "IV crush proxy" is an inference from fast large loss. Actual IV data not available to us (we don't have live IV from Zerodha in the BehaviorEngine — only trade data). So this is an approximation.
- Can overlap with `panic_exit` (held < 5 min at loss) and `premium_destruction` (lost > 60%). Multiple alerts could fire for the same IV crush event.
- Hold time 0–30 min: options losing 40% in 30 min happens normally on highly volatile days without IV crush.

**Fix needed**: Clarify dedup vs panic_exit and premium_destruction for same trade. May be worth removing this pattern and rolling its message into premium_destruction with richer context.

**Notification**: In-app only. Too much inference to push.

---

### #19 — `premium_destruction`
**What it does**: Option position exits at < -60% of entry premium (regardless of hold time).

**Quality**: 4/5

**Issues**:
- Good pattern. Catches catastrophic premium losses at exit.
- -60% threshold: may fire constantly for OTM options traders (deep OTM options regularly go to near-zero).
- Context is minimal. Should include: entry premium, exit premium, % destroyed, hold time.
- Potential double-fire with `no_stoploss` (pattern #13) for the same trade.

**Fix needed**: Add more context (entry price, exit price, hold time). Verify dedup with no_stoploss. Consider adjusting threshold based on moneyness (deep OTM = higher threshold).

**Notification**: In-app caution. Danger only if >80% destroyed (near total loss of premium).

---

### #20 — `expiry_day_overtrading`
**What it does**: On the expiry date of the instrument being traded: 5+ trades (caution) or 8+ (danger) on that underlying, or 1.5×/2.0× personal baseline count.

**Quality**: 4/5

**Issues**:
- Good pattern. Expiry day is genuinely different (0DTE, theta, forced squareoffs).
- Cold-start (no baseline): fires after 13:00 IST only. This is a good fallback.
- Only checks expiry of the SPECIFIC instrument being traded (uses the trade's expiry field). Correct.

**Fix needed**: Minor — add underlying P&L context for the day (how much lost/made on this underlying today).

**Notification**: Danger = push. Caution = in-app.

---

### #21 — `opening_5min_trap`
**What it does**: Trade entered 09:15–09:25 IST AND either (a) exited quickly with loss or (b) large premium loss.

**Quality**: 4/5

**Issues**:
- Good retrospective pattern. The trap fires AFTER the trade closes.
- Context is good: `entry_time_ist`, `hold_minutes`, `loss_pct`.
- Fires only if the trade went badly. What about catching the ENTRY itself as risky (before exit)? Not possible — engine only runs on CompletedTrades.

**Fix needed**: Mostly fine. Consider adding a note that this fires retrospectively.

**Notification**: In-app only. Already happened.

---

### #22 — `end_of_session_mis_panic`
**What it does**: 2+ (caution) or 3+ (danger) MIS trades entered after 15:00 IST (face auto-squareoff at ~15:20).

**Quality**: 4/5

**Issues**:
- Good pattern. End-of-session MIS entries under time pressure = emotional.
- Context includes count and the specific trades. Good.
- Some traders legitimately scalp MIS trades after 3pm. This will fire for them even when profitable.

**Fix needed**: Suppress if all MIS trades in window are profitable (same logic as overtrading_burst profitable suppression).

**Notification**: Danger = in-app. This is too situational for push.

---

### #23 — `post_loss_recovery_bet`
**What it does**: After 2+ consecutive losses, current trade is 2× (caution) or 3× (danger) the recent average size.

**Quality**: 3/5

**Issues**:
- Very similar to `martingale_behaviour` (#7). Both detect size escalation after losses.
- Martingale: progressive doubling within a sequence (trade-by-trade escalation). Recovery bet: single large outsized position after losses. The conceptual difference is real, but in practice they may fire for the same scenario.
- Cross-instrument comparison issue — same bug as size_escalation and the old overconfidence. Need to verify it uses same-underlying baseline.
- No trade list in context showing which prior losses and what sizes.

**Fix needed**: Verify same-underlying comparison. Clarify dedup vs martingale_behaviour. Add trade list.

**Notification**: Danger = push. This is a "going all-in" signal.

---

### #24 — `profit_giveaway`
**What it does**: Session peak P&L was ≥₹1000, and current trade eroded ≥50% (caution) or ≥70% (danger) of that peak.

**Quality**: 4/5

**Issues**:
- Good pattern. Catches "I was up ₹10k, then gave back ₹7k" scenarios.
- Fires exactly once per threshold crossing — no repeat. Good design.
- ₹1000 minimum peak is very low. If someone's capital is ₹5L and they're making ₹1k peaks, this fires constantly. Minimum peak should scale with capital.
- Context is good: `peak_pnl`, `current_pnl`, `erosion_pct`, `trigger_trade`.

**Fix needed**: Scale `profit_giveaway_min_peak` with capital (e.g., 0.2% of capital, min ₹1000). Add the specific trade that caused the erosion to context.

**Notification**: Danger = push. One of the most important patterns for day traders.

---

## 3. Notification Tiers — What Should Push

**Current behavior**: ALL `danger` alerts push. All `caution` = in-app only.

This is too blunt. Some danger patterns shouldn't push (too noisy/retrospective). Some caution patterns are urgent enough to push.

### Proposed Tier System

| Pattern | Push | In-App | WhatsApp Guardian | Rationale |
|---------|------|--------|-------------------|-----------|
| `session_meltdown` danger | YES | YES | YES | The single most important alert. Account preservation. |
| `revenge_trade` danger (<5min) | YES | YES | YES | Happening right now, actionable. |
| `martingale_behaviour` danger | YES | YES | YES | Progressive blow-up risk. |
| `post_loss_recovery_bet` danger | YES | YES | NO | High urgency, not guardian-level. |
| `consecutive_loss_streak` danger (5+) | YES | YES | YES | Tilt state confirmed. |
| `excess_exposure` danger | YES | YES | NO | Capital risk, actionable. |
| `profit_giveaway` danger (70%+) | YES | YES | NO | Still actionable if session open. |
| `no_stoploss` danger (50%+ loss) | YES | YES | NO | Already happened, but pattern awareness matters. |
| `expiry_day_overtrading` danger | YES | YES | NO | Time-sensitive. |
| `overtrading_burst` danger (8+ in 30min) | YES | YES | NO | Spiral in progress. |
| `winning_streak_overconfidence` danger | YES | YES | NO | About to over-leverage. |
| — all other dangers — | In-app | YES | NO | Retrospective or lower urgency. |
| — all cautions — | NO | YES | NO | Informational. |
| `revenge_trade` caution (<20min) | NO | YES | NO | Observation, not emergency. |
| `session_meltdown` caution (40%) | OPTIONAL | YES | NO | User can configure. |

**Guardian (WhatsApp) rule**: Only 3 patterns → guardian. Everything else is too noisy for a family member/friend. Guardian sees: meltdown danger, revenge danger, consecutive loss danger (5+).

---

## 4. Coverage Analysis

### 4A. Patterns We Should ADD

| Gap | Why | Complexity |
|-----|-----|------------|
| **Time-of-day bias** | Trader consistently loses between 1–3pm but keeps trading then. learn_patterns() detects this but doesn't generate a real-time alert. Should fire: "You've historically lost ₹X between 1-3pm. You're about to trade at 2:15pm." | Medium |
| **All-in bet** | Single position = 70%+ of all open positions' combined value. `excess_exposure` catches per-trade %, but doesn't see concentration across all open positions. | Hard (needs open position data) |
| **Win-rate collapse** | Last 10 CompletedTrades: win rate significantly below personal baseline (e.g. usually 55%, now 20%). Signals strategy breakdown, not just bad luck. | Medium |
| **Same-symbol loss chasing** | 3+ losses on the same underlying today. More specific than consecutive_loss_streak (all instruments). SEBI data shows this is the most common retail F&O destruction pattern. | Easy |
| **Capital concentration** | 60%+ of capital in single underlying across multiple positions. Different from all-in (which is single position). | Hard |
| **Post-event re-entry** | Entering a position within 5 min of an RBI announcement or budget-related time slot. Needs calendar data — complex. | Very Hard |

### 4B. Patterns to MERGE

| Action | Patterns | Reason |
|--------|----------|--------|
| Merge or clarify | `rapid_flip` + `options_direction_confusion` | Both detect direction reversal on same underlying. Rapid_flip = exact symbol, direction_confusion = underlying level. Confusing to users who see both. Should be one pattern with two sub-levels. |
| Merge | `iv_crush_behavior` + `premium_destruction` | IV crush is inferred from fast premium loss. Premium destruction catches the same event at exit. One trade can fire both. Merge into `premium_loss` with hold-time context. |
| Clarify | `martingale_behaviour` + `post_loss_recovery_bet` | Martingale = progressive (trade-by-trade). Recovery bet = single outsized position. Different conceptually but similar mechanically. Keep separate but make messaging very distinct. |
| Clarify | `revenge_trade` + `cooldown_violation` | Both detect trading too soon after loss. `cooldown_violation` is currently invisible (info severity). Either remove it or make it visible and distinct. |

### 4C. Patterns to CONSIDER REMOVING

| Pattern | Reason to Remove | Alternative |
|---------|-----------------|-------------|
| `cooldown_violation` | Already invisible. Redundant with `revenge_trade`. Creates DB noise. | Remove OR convert to in-app caution only for users who set explicit cooldown. |
| `panic_exit` | Fires retroactively. Push is useless. For scalpers it's noise. | Convert to analytics-only tracking (no alert, but visible in Journal/Analytics). |
| `iv_crush_behavior` | Inferred from fast loss — unreliable signal. Too many false positives near events. | Roll into `premium_destruction` with hold-time context. |

---

## 5. Adaptive Thresholds — Critical Gap and Roadmap

### 5A. The Gap: Two Systems That Don't Talk

**`learn_patterns()`** (runs daily 18:15 IST) stores this in `user_profile.detected_patterns`:
```
{
  "last_updated": "...",
  "trades_analyzed": N,
  "time_patterns": { danger_hours: [...], best_hours: [...] },
  "symbol_patterns": { weak_symbols: [...] },
  "intervention_timing": { ... },
  "predictive_windows": [ ... ]
}
```

**`get_thresholds()`** (runs on every trade) looks for this in `user_profile.detected_patterns`:
```python
baseline = detected_patterns.get('baseline')
# Keys: daily_trade_limit, burst_trades_per_30min_caution,
#       revenge_window_caution_min, consecutive_loss_caution, consecutive_loss_danger
```

**`baseline` is NEVER WRITTEN by `learn_patterns()`.** The adaptive threshold system in `get_thresholds()` is wired up but dead — it reads from a key that doesn't exist. All users are running on research defaults (Tier 2) plus their 6 declared inputs (Tier 1).

### 5B. Why This Matters

**Example: Overtrading alert**
- Research default: caution at 7 trades/day.
- A scalper who legitimately does 25 profitable trades/day gets 7-trade alerts constantly → ignores all alerts → alert blindness.
- A positional trader who usually does 2 trades/day: 7 is fine as-is.
- We need to calibrate PER USER.

**Example: Revenge trade**
- Research default: caution within 20 min of loss.
- A fast scalper is back in the market in 3 min by design — their cooldown IS 3 min.
- A swing-style trader should wait 30 min.

**Example: Position sizing**
- Research default: 5% capital per trade.
- A high-leverage trader regularly uses 15% capital per trade and is profitable.
- An aggressive options buyer uses 3% capital per trade.
- Fixed 5% threshold = wrong for everyone.

### 5C. What We Need to Compute (extend learn_patterns)

| Metric | Purpose | Threshold it calibrates |
|--------|---------|------------------------|
| `avg_daily_trades` (30-session rolling) | Personal "normal" trade frequency | `daily_trade_limit`, `burst_trades_per_30min_caution` |
| `p95_daily_trades` | Upper bound without blowing up | `daily_trade_danger` |
| `avg_hold_time_winners_min` | Personal winner hold pattern | `early_exit_winner_max_min` |
| `avg_hold_time_losers_min` | Personal loser hold pattern | `early_exit_ratio` calibration |
| `avg_position_size_pct_capital` (by underlying) | Normal sizing | `overconfidence_size_mul_*`, `size_escalation_pct`, `martingale_*`, `recovery_bet_*` |
| `avg_loss_before_reentry_min` | Actual revenge trade window | `revenge_window_caution_min` |
| `win_rate_rolling_30` | Baseline win rate | `win_rate_collapse` new pattern |
| `typical_session_peak_pnl` | Normal day profit | `profit_giveaway_min_peak` calibration |
| `primary_instruments` (list) | Which patterns to enable/disable | enables options patterns only for options traders |

### 5D. Calibration Logic

Once we have the personal metrics, thresholds adjust like this:

```
daily_trade_limit_adaptive = max(
    floor(avg_daily_trades * 1.5),  # 50% above their own normal
    UNIVERSAL_FLOORS['daily_trade_limit']   # never below 3
)

burst_caution_adaptive = max(
    floor(avg_daily_trades / 4),    # 25% of their typical day in 30 min
    3                                # universal floor
)

revenge_window_adaptive = max(
    avg_loss_before_reentry_min * 0.5,  # fire at half their natural cooldown
    5                                    # minimum 5 min
)
```

The logic: don't alert when someone is within their own normal range. Alert when they're doing something UNUSUAL for THEM.

### 5E. Adaptive Rollout Plan (discuss)

**Phase 1** (extend learn_patterns — low risk):
- Compute the 9 metrics above.
- Write them to `detected_patterns.baseline` dict that `get_thresholds()` already reads.
- No UI change. Thresholds start adapting silently on next 18:15 task run.
- Minimum 20 sessions before baseline kicks in (cold start = research defaults as today).

**Phase 2** (user transparency — show in Settings/Insights):
- InsightsTab shows: "Your personalized thresholds" with explanation of how each was derived.
- User can override individual thresholds (declare "I know I do 20 trades/day, don't alert before 30").

**Phase 3** (online learning — advanced, later):
- Update baseline continuously after each session, not just once a day.
- Track which alerts were acknowledged vs dismissed to learn alert fatigue.
- Patterns with high dismiss rate → automatically raise threshold for that user.

---

## 6. Priority Matrix

| Priority | Work | Effort | Impact |
|----------|------|--------|--------|
| P0 | Fix `baseline` gap in learn_patterns → write it | 1 day | Unlocks all adaptive thresholds for active users |
| P0 | Fix `trigger_trade_id = None` (all 24 patterns) | Half day | Users finally see WHICH trade triggered alert |
| P1 | Fix cross-instrument comparison in `size_escalation` and `post_loss_recovery_bet` and `martingale_behaviour` | 1 day | Eliminates biggest false positive category |
| P1 | Add trade lists to `consecutive_loss_streak`, `rapid_reentry`, `martingale_behaviour` | Half day | Context parity across all alerts |
| P1 | Notification tier overhaul (per table in Section 3) | Half day | Reduce push noise, improve WhatsApp guardian quality |
| P2 | Scale `profit_giveaway_min_peak` with capital | 2 hours | Eliminates noise for small-capital traders |
| P2 | Add `same_symbol_loss_chase` pattern | Half day | Most common missing F&O destruction pattern |
| P2 | `panic_exit` → analytics-only (remove alert) | 1 hour | Reduce noise, eliminate retroactive push |
| P3 | Merge `iv_crush` into `premium_destruction` | Half day | Clean up overlap |
| P3 | Clarify `rapid_flip` vs `options_direction_confusion` | Half day | Reduce user confusion |
| P3 | `early_exit` → EOD report only (remove real-time alert) | 1 hour | Better UX for session-level pattern |
| P4 | Time-of-day bias alert (using learn_patterns output) | 1 day | Highly personalized, high value |
| P4 | Win-rate collapse alert | 1 day | Strategy-level signal |

---

## 7. Open Questions (For Discussion)

1. **Cooldown violation**: Remove entirely? Make visible? Keep as invisible analytics?

2. **Panic exit**: Keep as real-time alert or move to analytics/journal only? Argument for keeping: pattern awareness (trader knows they panic). Argument for removing: fires after the fact, can't change anything.

3. **IV crush**: Merge into premium_destruction or keep separate? IV is a real phenomenon Indian F&O traders face (especially around budget/RBI) but we can only infer it.

4. **Same-symbol loss chasing** (new pattern): Is 3+ losses on same underlying per day the right trigger? Or should it be same symbol + losses + re-entry within X min each time?

5. **Adaptive phase 1 rollout**: Write baseline from last 30 sessions immediately, or only from sessions after a threshold count (e.g. require 30 complete sessions)? Too few sessions = unstable baseline.

6. **Alert fatigue**: Should we track dismissed vs acknowledged alerts per pattern and auto-mute patterns that the user never acts on? Risk: might mute legitimately important patterns.

7. **Notification tier**: Is the guardian threshold (only 3 patterns) too restrictive? Or too broad? Guardian should feel the weight of the alert, not be desensitized.

8. **Daily count as separate pattern type**: `overtrading_burst` currently covers both 30-min window AND daily total. Should daily total be `daily_overtrading` (new pattern_type) with its own dedup and message?

---

*Status: DISCUSSION DOCUMENT — no implementation. Update this doc with your thoughts, then we plan.*
