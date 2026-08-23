# The Behavioural Engine as it actually exists

23 Aug 2026. Written from the code, not from the design documents. No code was
changed to produce it.

Headline: **the detection pipeline is sound and the foundation around it is
largely unconsumed.** Five modules built in the last week have zero effect on
what a trader sees. That is by design and on a schedule — but it is also the main
risk in the whole exercise, and §7 says so bluntly.

---

## 1. End to end, as it runs

```
Zerodha postback
  → trade_tasks.process_webhook_trade          (queue: trades, 1 worker × 4)
  → TradeSyncService.upsert_trade              raw Trade row
  → PositionLedgerService.apply_fill           append-only, handles partials/flips
  → build_completed_trade_on_close             CompletedTrade on CLOSE/FLIP
  → pnl_calculator.ensure_feature_for          CompletedTradeFeature  [new 2026-08-23]
  → BehaviorEngine.analyze(completed_trade)
  → RiskAlert + BehaviorEvent rows
  → event_bus.publish_event → Redis Streams → WebSocket → browser
```

Inside `analyze`:

**a. Session.** `get_or_create_session(broker_account_id, today_ist)`.

**b. `_load_context`** — 4 queries, constant in session length (guarded by test):
profile (+ pending constitution changes), this session's CompletedTrades, active
cooldowns, strategy group, exit order types.

**c. Session facts.** `session_facts.derive(session_trades + [trade])` — the single
definition of `pnl`, `trades`, `consecutive_losses/wins`, `peak_pnl`,
`drawdown_from_peak`, `max_drawdown`, `longest_loss_run`. Written to
`trading_sessions`; `_load_context` is their sole writer.

**d. Thresholds.** `resolve_thresholds(profile, session_trades)` walks the ladder
HISTORY → SESSION → DECLARED → CAPITAL → POPULATION → GLOBAL, then UNIVERSAL_FLOORS,
then safety bounds. Returned as `RecordingThresholds`, which notes which keys each
detector reads.

**e. Account risk.** Resolved once per session and frozen on the row
(`risk_denominator*`). **Read by no detector.**

**f. Detectors.** 27 run in registry order, gated by feature flags
(off / shadow / on). Each returns `Optional[DetectedEvent]` — or a list, for the
constitution detector. Pure: zero DB work, guarded by test. Median 3.2ms for all 27.

**g. Severity and confidence.** Assigned *inside each detector*, by hand. Severity
is the detector author's judgement of impact; confidence is capped by data quality
(`GOOD 100 / PARTIAL 75 / UNKNOWN 50`). Below `confidence_alert_gate` (50) the
severity is rewritten to `info`, which records the event and suppresses the alert.

**h. Consolidation.** `_consolidate` folds by meaning, not by cap: a composite
(`death_spiral`) absorbs everything else; otherwise within three hand-ordered
families the most specific description wins. Folded events keep their
`BehaviorEvent` with a `_suppressed` marker — hidden from the trader, not deleted.

**i. Persistence and routing.** Every event becomes a `BehaviorEvent`
(idempotency key = `detector:trade:discriminator`). Non-`info`, non-suppressed,
non-shadow events also become `RiskAlert`s. `input_snapshot` is stored only for
danger/critical. Evidence now carries `_thresholds` — the numbers the detector was
judged against, with provenance. Then Redis Streams → WebSocket, with push and
WhatsApp on the guardian path.

### What is missing from this pipeline

- **Reference frames are nowhere in it.** No detector declares whether it is
  reasoning about the account, the trade, the trader, or structure.
- **Abstention is nowhere in it.** `Evidence` has zero references in
  `behavior_engine.py`. `None` still means both "did not happen" and "could not
  tell".
- **Measurements are nowhere in it.** `measurements.py` is imported by nothing.

---

## 2. Constants, by the numbers

Counted from the running system, not from a document.

| | count |
|---|---|
| `COLD_START_DEFAULTS` | **86** |
| Resolved keys (incl. derived) | **100** |
| `UNIVERSAL_FLOORS` | **10** |
| Classified in the registry | **16** |
| `personalise=True` | **0** |
| Safety bounds declared | **0** |
| Detectors / pattern types | **27 / 33** |

Kind spread across all 100 resolved keys:

| Kind | count | can it adapt? |
|---|---|---|
| `fallback` | **84** | unconstrained — any rung may answer |
| `personal_baseline` | 14 | may learn; `personalise=False` on all |
| `definitional` | 2 | defines what is measured, not where the line is |
| `universal_safety` | **0** | — |
| `product_policy` | **0** | — |
| `user_rule` | **0** | — |

**What actually adapts today.** Seven keys, and only these:
`daily_trade_limit` (own P75), `daily_trade_danger` (×1.5),
`burst_trades_per_30min_caution` (own P75), `burst_trades_per_30min_danger` (×1.6),
`revenge_window_caution_min` (own P25), `consecutive_loss_caution` (own P60),
`consecutive_loss_danger` (own P85). Every one is `fallback` — the Kind with no
constraint.

**What cannot adapt.** The other 93, by omission rather than by decision. Nothing
declares them fixed; no path exists to move them.

**Retired**: the L3 behaviour score, weights, bands and the severity multiplier;
the 40/70/90 session-state ladder; six unread constants; `burst_trades_per_15min`
(no runtime consumer); the client-side `patternDetector.ts`; the legacy
`behavioral_analysis_service`.

**Flagged mandatory-review (4)**: `burst_trades_per_15min`, `fomo_symbols_at_open`,
`premium_loss_caution_pct`, `revenge_window_danger_min`.

**Frozen by your decision**: the three capital-relative rupee floors from `91975d4`.
Now demonstrated rather than argued — replaying 40 sessions at ₹50k vs ₹500k with
nothing else changed: `revenge_trade` 8 → **0**, `profit_giveaway` 5 → **0**,
`consecutive_loss_streak` unchanged.

---

## 3. Cold start — a brand-new trader

**They are protected, and the protection is real.** All 27 detectors run from trade
one. Most are structural: "you added to a losing position", "you re-entered four
minutes after a loss", "this position had no stop" are facts about a sequence and
need no history. Rung 2 (SESSION) also gives same-day comparisons from the second
trade onward.

**Three honest caveats.**

1. The numbers those detectors use are `COLD_START_DEFAULTS` — the 86 constants
   whose calibration is exactly what this whole exercise is questioning. Cold-start
   protection is genuine, and its thresholds are unjustified.
2. Account-relative claims are unavailable and correctly abstain. Worse than
   intended, for a reason found this week: `margin_snapshots` has **no scheduled
   producer**, so the GOOD rung is reached only if the trader happened to load a
   page that fetched margins.
3. The three-family cold-start argument in `measurements.py` describes an intended
   design. That module is imported by nothing.

---

## 4. Against the original three-layer engine

**Then**: L1 detectors → L2 meta-detectors → L3 a 0–100 behaviour score built from
per-detector weights, severity multipliers and 40/70/90 bands.

**Wrong with it.** The weights were invented and unvalidatable. The score mixed
incommensurable things into one number — a fast re-entry and an oversized position
are not addends. Nobody could explain a score of 62. Worst, the score was *derived
state feeding detection*, so a detector could react to a number produced by other
detectors, and a threshold change rippled invisibly.

**Removed**: L3 entirely — score, weights, bands, multiplier, and the session-state
ladder. Replay-verified identical afterwards, which is itself the finding: the
score changed no alert.

**Added since**: canonical session facts; threshold ladder with provenance;
per-alert threshold recording; account-risk denominator (frozen, unread);
abstention primitives (unused); baseline contamination rules (used); runtime
enforcement of the safety Kind rule; the safety-bound mechanism (empty).

**Better**: nothing is scored, so nothing has to be defended as a weight; every
alert is a statement about an observable; the derived-state ban is enforced by L3
simply not existing.

**Worse, and unresolved**: L3 was also the *prioritisation*. With 33 pattern types
and no score, ordering rests entirely on severity — which is hand-assigned per
detector — and on consolidation. "Which of these four alerts matters most today"
has no answer beyond a four-value enum. That is a real capability that was removed
and not replaced.

**Not actually one layer.** `death_spiral` is still a meta-detector consuming other
detections. The architecture is L1 + one L2, not L1 alone. Worth stating plainly,
since documents describe it as a single engine.

---

## 5. Old vs current threshold system

**Then**: constants in a file, read directly by detectors, with a partial
"personalisation" path whose key names did not match what the readers looked for —
so two personalised values never arrived at all.

**Now**: a six-rung ladder; every resolution records its rung, confidence and
detail; `Kind` states what a threshold *is*, independent of where it resolved;
`violates_kind` runs inside `put()` at resolution time; baselines learn only from
cleaned data (median/MAD, outliers excluded, adaptation capped 20%/period, harmful
sequences excluded); alerts store the thresholds they were judged against; safety
bounds exist as a mechanism.

**Genuinely changed**: provenance exists and is stored. The reader/writer key
mismatch is closed. Baseline contamination is defended against. The rule against
learning a safety threshold is machinery rather than prose.

**Problems that remain**:

1. **84 of 100 thresholds are unclassified `fallback`.** The provenance story
   covers 16%.
2. **Zero `universal_safety` thresholds**, so the runtime rule guards an empty set.
3. **Zero safety bounds**, so nothing yet limits how quiet history can make a
   detector. `daily_trade_limit` = own P75 remains live and unbounded.
4. **`UNIVERSAL_FLOORS` mixes directions** — for `consecutive_loss_caution` a bigger
   number is looser, for `revenge_window_caution_min` a bigger window is stricter,
   and one `<` is applied to both.
5. **Severity is still judgement.** Assigned per detector with inline literals
   (`size_ratio >= 1.5` inside `revenge_trade`). The percentile-based severity in
   `BEHAVIOUR_SYSTEM_DESIGN.md` is not implemented.
6. **`confidence_alert_gate = 50`** is a single unvalidated constant that decides
   whether *any* detection reaches the trader.

---

## 6. Implemented / infrastructure-only / deferred

**Implemented and affecting behaviour**

- Canonical session facts, single-writer, nine competing definitions collapsed
- `trade_count` bug fix (session log, EOD intent comparison)
- Feature-row writing on the live path
- Baseline contamination rules wired into `baseline_service`
- Threshold provenance recorded on every alert
- Account-risk denominator frozen per session (written, not read)
- Danger zone / prediction / My Rules / coach reading canonical facts
- Engine observability metrics
- L3 removal

**Infrastructure only — zero behavioural effect today**

| module | consumers |
|---|---|
| `measurements.py` (three frames) | **none** |
| `detector_result.py` (`DetectorResult`, `Layer`) | **none** |
| `evidence.py` (abstention) | **none** in the engine |
| `safety_bounds.py` | live, guards an empty set |
| `DetectorSpec.frames` | empty on all 27 |
| `ctx.account_risk` | **no detector reads it** |
| baseline `divergence` | computed and stored, read by nothing |
| `EpisodeRole` / `EpisodeHint` | defined, deliberately not built |

**Deferred to pattern-by-pattern**

Classifying the 84 `fallback` thresholds; deciding which are `universal_safety`;
every safety-bound value with its justification; per-detector reference frames;
enabling `personalise` where evidence supports it; the four mandatory-review
constants; the frozen capital-relative floors; migrating detectors to
`DetectorResult`/abstention/`measurements`; severity as measurement rather than
judgement.

---

## 7. Critical assessment

**The single biggest risk is that the foundation stays unconsumed.** Eight items in
that table have no consumer. Each was built to an approved spec with a named
adoption point, and that is a real answer — but it is also exactly what
overengineering looks like from the inside. If pattern-by-pattern does not adopt
them, they are not architecture, they are maintenance.

The clearest instance: **`EpisodeRole`/`EpisodeHint` should probably not have been
written.** They are defined for a state machine deliberately not built, with the
open design question (an episode needs a lifetime; the session boundary is wrong
for overnight positions) recorded but unanswered. That is speculative work.

**`threshold_recorder` over-records by design** — it captures keys *read*, not keys
*used*. Defensible for an explanation, and it will attach irrelevant numbers to
some alerts.

**Consolidation is heuristic and undefended.** The three families and their internal
ordering ("the strongest claim" first) are hand-picked. Sensible, unvalidated,
and the ordering silently decides which alert a trader sees.

**Severity is the largest remaining conceptual gap.** The design says severity
should be a percentile of the trader's own distribution. It is currently a
hand-written ladder inside each detector, with inline magic numbers. Every
constant-elimination argument applies to it verbatim, and none of it has been
applied.

**Two things are genuinely right and should not be touched**: consolidation-by-
meaning rather than an alert cap, and the removal of L3. Both are better than what
the specification proposed.

**What I would not build more of right now.** Nothing further in the shared
foundation until a detector consumes it. The next honest step is one detector, end
to end, using frames, bounds, abstention and measurements — and if that detector
does not come out demonstrably better, the foundation is wrong and it is far
cheaper to learn that at one detector than at twenty-seven.
