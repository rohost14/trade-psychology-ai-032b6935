# Implementation plan — defects and features from the external review

Companion to `docs/CHATGPT_REVIEW_FINDINGS.md`.

**Status — 2026-08-09.** Phase 1 (notification integrity) **shipped** — `8d762c8`.
Phase 7 (rule presets + rule suggestions) **shipped** — `9e064a9`.
Phases 2–6 are still proposals.

Phase 1 landed one thing not in the original scope: `backend/app/core/severity.py`, the
single owner of the severity vocabulary. A1 needed it, and it is the first half of the
Phase 2 argument — the pattern vocabulary needs the same treatment. Two of Phase 1's
defects turned out to live on the **push** path as well (`== "danger"` titling every
critical alert "Caution", plus a pattern-name table keyed on dead v1 names) and were fixed
in the same pass. `_format_guardian_alert` no longer accepts a `BrokerAccount` at all, and
`send_risk_alert_with_guardian` — correct, tested three times, called from nowhere — is
deleted; `send_guardian_alert` is the one guardian entry point and the live path calls it.

---

## 0. Corrections to the findings doc

Three claims in the earlier report were wrong. They change the plan, so they come first.

**Shadow mode exists.** I said we had none. We have the full apparatus: `DetectorSpec.default_mode`
(`off | shadow | canary | on`), a `detector_flags` table (migration 068) that overrides it at
runtime, an admin API (`api/admin/detector_flags.py`) to flip a detector without deploying,
`BehaviorEvent.shadow` to mark output, and scoring that reads `WHERE shadow = false`
(`analytics.py:3148`). What is missing is **not the mechanism, it is the readout** — nothing
anywhere answers "this detector has been in shadow for three weeks; what did it produce?"
So B2 shrinks from "build shadow mode" to "build one query over infrastructure we already own."

**Latency is already derivable.** I said we had no raw material. `RiskAlert.detected_at` is set
to the trade's own time (`behavior_engine.py:271` → `trade_time`), and `created_at` is the row
write time. `created_at − detected_at` is the true event→alert latency, no schema change needed.
The webhook additionally has `order_timestamp` and `exchange_timestamp` from Kite
(`webhooks.py:220`) if we want broker-clock truth later. B1 shrinks from "instrument the
pipeline" to "report a subtraction we can already do."

**The multi-leg concern is confirmed, not speculative.** I raised it as a question. It is real:
`_detect_overtrading_burst` counts `trades_in_window = len(all_trades)` where each element is a
CompletedTrade, and a CompletedTrade is per `tradingsymbol`. One four-leg iron condor closing
produces four CompletedTrades in the same minute. Default `burst_trades_per_30min_caution = 5`,
`danger = 8`. **Two condors in a session = eight "trades" = a danger-severity overtrading alert
for two positions.** The same inflation hits `daily_overtrading`, `expiry_day_overtrading`, and
any constitution trade-count rule. This is an accuracy defect in the engine, not a table-layout
preference — it changes B3 from a UI nicety to the highest-value correctness item in the list.

---

## 1. Why these were missed

Worth answering properly, because the answer determines whether the fixes hold.

### 1.1 Every one of these is a silent failure

None of A1–A6, F1–F4 throws. Each one degrades into a plausible-looking result:

- `_format_alert_message` doesn't match a pattern name → renders the generic `else` branch. Valid message.
- `severity != "danger"` → returns `False`. Reads as "nothing to send", identical to a genuine skip.
- `PATTERN_EXPLANATIONS["overtrading_burst"]` → `undefined` → React renders nothing. A slightly shorter sheet.
- `any(a.severity == "danger")` false for a critical alert → falls to `else` → `"caution"`. A valid state.

There is no exception, no 500, no failed test, no empty screen. The misleading-empty class already
in memory (`catch { setX([]) }`) is the same disease: **a failure that renders as a plausible
success.** Our tests assert that functions return what they should when called correctly; nothing
asserts that a *string key still refers to something real*.

### 1.2 Two vocabularies changed underneath string-keyed lookups

Both bug clusters are one mechanism.

*Pattern names.* Engine v1 had `overtrading`, `revenge_sizing`, `consecutive_loss`. Engine v2
renamed them to `overtrading_burst` / `daily_overtrading`, `size_escalation`,
`consecutive_loss_streak`. Renaming the registry did not — could not — break `alert_service.py`'s
`if alert.pattern_type == "overtrading"` or `AlertDetailSheet`'s `PATTERN_EXPLANATIONS.overtrading`.
Both are string comparisons against a literal. Python and TypeScript both compile them happily.

*Severity.* The vocabulary grew from `caution | danger` to `info | caution | danger | critical`.
Every comparison written against the old two-value world still runs: `!= "danger"` now silently
excludes `critical` (A1), `any(== "danger")` now silently downgrades it (F4).

**A rename is not a refactor when the name is a string in a dict key.** We have four independent
copies of the pattern vocabulary — `detector_registry.py`, `alert_service.py`,
`AlertDetailSheet.tsx`, and the severity helpers — and nothing that fails when they diverge.

### 1.3 The unrendered surfaces got no review

Memory records the working rule: *screen reviews = logic/backend/real-time/edge-cases only*, and
the last several sessions were design work. Every defect found here lives somewhere **nothing
renders**: a WhatsApp message body, a Celery task's third branch, a lookup table that degrades to
blank. Design review can't see them, and screen review didn't cover them because they aren't screens.
`AlertDetailSheet` *is* a screen — but F1 only shows up if you open the sheet from an
**overtrading** alert specifically, and it looks fine from any of the other twelve.

### 1.4 Test coverage measured functions, not call graphs

`send_risk_alert_with_guardian` is correct, third-person, tested three times in
`test_notifications.py` — and called from nowhere in `app/`. Production calls `send_risk_alert`
with the guardian's phone instead. **Green tests on a function no caller reaches is worse than no
test**: it converts an untested path into one that looks covered.

### 1.5 Consent was retrofitted forward, not backward

`guardian_confirmed` arrived in migration 056. It was wired into what was being actively built at
the time (`reports.py:453`) and never applied retroactively to the older real-time path
(`trade_tasks.py:1350`). Nothing enumerates "all places that send to a guardian", so there was no
list to work through.

### 1.6 The product measures the user and never itself

28 detectors, zero accuracy metrics. `alert-response-stats` looks like a quality metric but ranks
by `took_anyway` and `ignored` — it measures *the user's* compliance. `not_useful` — the only
field that says the engine was wrong — is accepted, stored, and never read (A7). Shadow mode was
built and then had no readout attached (§0).

This is the root cause behind the root causes: **we had no instrument that would have gone red.**
A2 means every WhatsApp alert has been generic for months. F1 means our most common alert type
opens a bare sheet. Both are invisible without a metric, and both stay invisible after we fix
them unless a metric lands too.

### 1.7 Honest reading

This is normal decay for a system that went through an engine v2 rename, a severity expansion, and
a consent retrofit while most attention was on UI. It is not sloppiness in any single change; it is
the absence of a mechanism that makes a vocabulary drift fail loudly. **The fix that matters most
here is not any individual bug — it is §2's contract test.** The bugs are a symptom; without the
test we will be reading a list like this again after the next rename.

---

## 2. Triage — what actually needs doing

| ID | Item | Verdict |
|---|---|---|
| A1 | Critical alerts never sent on WhatsApp | **Must.** Most severe class, silently dropped |
| A2 | Dead pattern branches in WhatsApp copy | **Must.** Every message is generic today |
| A3 | Guardian gets trader-voice message | **Must.** Third party told "you are in tilt mode" |
| A4 | Client ID leaked to guardian | **Must.** DPDP purpose limitation |
| A5 | Guardian consent not checked on live path | **Must.** We built consent and bypass it |
| A6 | Charter-violating copy | **Must.** Blocker voice, unsubstantiated claim |
| A7 | `not_useful` never surfaced | **Must.** Only false-positive signal we have |
| F1 | FE pattern copy keyed to dead names | **Must.** Most common alert opens bare sheet |
| F2 | 13 of 28 detectors have copy | **Must** (same fix as F1) |
| F3 | Invented benchmark statistics | **Must.** Truthfulness, same class as landing P0s |
| F4 | `/risk/state` can't represent `critical` | **Must.** Drives dashboard session status |
| B3 | Multi-leg inflates count detectors | **Must.** Confirmed engine accuracy defect |
| B1 | No latency readout | **Should.** Cheap; unblocks Gate-3 |
| B2 | No shadow readout | **Should.** Infra exists; needs one query |
| G1 | "Planned" outcome | **Should.** One tap; best precision signal available |
| G3 | Rule suggestions from own data | **Should.** Best fit for zero-manual-input |
| G4 | Rule presets at onboarding | **Should.** Only thing making rules useful day one |
| B4 | SessionLog on Dashboard | **Nice.** Fold into rev6 rollout |
| B5 | Data staleness indicator | **Nice**, but see §3.7 — it has a real failure mode |
| G2 | Episodes user-facing | **Nice.** Mostly surfacing what exists |
| G5 | Warn on over-sensitive escalation | **Nice.** Protects the guardian relationship |
| G6 | Pattern glossary page | **Nice.** Nearly free after F2 |

Not everything here is equally load-bearing. If only one phase ships, it should be Phase 1 —
it is the only one where the current behaviour is actively wrong toward a third party.

---

## 3. The plan

Six phases. Each is independently shippable and independently revertible. Phases 1–3 are
correctness; 4–6 are product.

---

### Phase 1 — Notification integrity (A1–A6) — **SHIPPED 2026-08-09** (`8d762c8`)

**Delivered.** `backend/app/core/severity.py` (new) · `alert_service.py` (rewritten) ·
`trade_tasks.py` (consent gate, correct formatter, two dispatch filters) ·
`push_notification_service.py` (same two defects) · `test_notifications.py` (35 pass).
Full non-production suite: 464 pass. `tests/production` needs a live server, unchanged.

Notes worth carrying forward:
- The old tests **asserted the defects** — they checked for the word "STOP", for
  per-pattern branches under their v1 names, and for the client id in the guardian
  message. They passed only because the tests shared the same dead vocabulary as the
  code. That is the sharpest illustration of §1.1 in this document.
- Guardian disclosure is now the floor: who, which pattern, how serious, when. Letting the
  trader choose what their guardian sees is the natural follow-up and is **not** built.
- `alert.message` is second-person in many detectors ("You entered NIFTY after…"), which
  is why forwarding it to a guardian was never merely a formatting slip.

**Original scope.** `alert_service.py`, `trade_tasks.py:1346–1367`.

1. Delete `_format_alert_message`'s pattern branches. Do **not** re-key them to v2 names — that
   recreates the drift with fresh strings. The engine already writes an evidenced sentence to
   `alert.message`; WhatsApp renders that plus a fixed frame. One copy of the copy.
2. Fix the severity gate to accept `danger` and `critical`, taking the set from one shared
   constant rather than a literal.
3. Route guardian sends through `_format_guardian_alert` (third person, no imperatives) and
   delete `send_risk_alert_with_guardian` or wire it — it must not stay as tested dead code.
4. Drop `broker_account.broker_user_id` from the guardian footer. Trader's chosen display name
   or nothing.
5. Gate the live guardian send on `user.guardian_confirmed`, matching `reports.py:453`.
6. Rewrite the copy to mirror voice: observation, evidence, no instruction, no causal claim.

**Why this is production-grade, not a patch.** The defect class is *duplicated pattern copy*, so
the fix is to stop duplicating it — one authored sentence, rendered by every channel. Point 3
removes the "tested but uncalled" trap that produced A3. Point 5 makes consent a property of the
send path rather than of whichever endpoint remembered.

**Verification.** A test asserting a `critical` alert produces a send; a test asserting no send
when `guardian_confirmed` is false; a test asserting the guardian body contains no `broker_user_id`
and no second-person imperative. All three fail today.

**Risk.** Low, and bounded: WhatsApp is in SAFE MODE until `TWILIO_*` is set, so the blast radius
today is zero. That is also the argument for doing it **before** Twilio goes live, not after.

---

### Phase 2 — One pattern vocabulary, enforced (A2/F1/F2/F4/A7)

The structural phase. Everything in §1.2 exists because pattern identity has four homes.

1. Extend `DetectorSpec` with the display contract: `label`, `observes` (what the detector looks
   at, one line), `explanation` (why it matters), and a declarative facts spec for the sheet's
   data table. The registry is already frozen and declarative; this is what it is for.
2. Serve it — either a `GET /api/patterns` catalogue or embedded in the alert payload. Prefer the
   catalogue: it is cacheable, it is the glossary (G6), and it keeps alert rows thin.
3. `AlertDetailSheet` consumes that instead of three local `Record`s. Delete
   `TRADER_BENCHMARKS`, `PATTERN_EXPLANATIONS`, and the `buildFacts` switch.
4. **The contract test** — for every name in `REGISTRY`, copy exists; for every key any renderer
   uses, a registry entry exists; every severity comparison draws from the shared vocabulary
   constant. This is the piece that stops §1.2 from recurring.
5. Fix `/risk/state` to handle `critical` as its own level, and audit every other
   `== "danger"` comparison in the same pass.
6. Add `not_useful` to `alert-response-stats` output, and a per-pattern rate.

**Why production-grade.** After this, adding a detector without copy fails CI, and renaming one
cannot silently orphan a renderer. It converts a whole bug class from "discovered by reading code
six months later" into "caught before merge". It also removes ~120 lines of frontend copy that had
no business living in a component.

**Verification.** The contract test itself. Plus: open a sheet from an overtrading alert and see
facts, explanation and context — impossible today.

**Risk.** Medium surface, low danger — mostly moving strings, with one new endpoint. Do it as
registry-first, then FE, so the API exists before anything depends on it.

---

### Phase 3 — Honest context (F3)

Delete the invented benchmarks. Replace with the user's own record via **My Record**, which
already computes exactly this lookup. Where the user has no history (cold start), state the
mechanism with **no number**: *"Trades taken immediately after a loss are the ones this alert
watches"* — true with zero users, still true with ten thousand.

**Why this is not optional.** The strings shipping today are precise, quantified, unsourced claims
presented as fact ("win rate below 30%", "2–3× drawdown", "15–25% inflated"). Same category as the
fabricated testimonials `LANDING_PAGE_AUDIT.md` flags as P0 on `Welcome.tsx`, and it is worse here
because it sits inside the product where it reads as a measurement we performed. The "not
individual advice" label addresses SEBI exposure; it does not make an invented number true.

**Why the replacement is stronger.** "The last 4 times you traded after three losses you lost 3 of
them" beats any population statistic on persuasiveness *and* is defensible. It is also the
differentiator — no competitor has the user's ledger.

**Risk.** Copy-only, reversible. Depends on Phase 2 (the copy must live in the registry first).

---

### Phase 4 — Measurement (B1, B2)

Small, and it is what makes everything above stay fixed.

1. **Latency.** Report `created_at − detected_at` per alert: p50/p95, per pattern, over a window.
   Admin surface. The 5-second gate becomes a number instead of an opinion.
2. **Shadow readout.** One query over `BehaviorEvent WHERE shadow = true`: fire count per detector,
   what severity it would have raised, overlap with alerts the live detectors already produced.
   Attach it to the existing admin detector-flags screen so the promote decision sits next to
   its evidence.
3. **Precision proxy.** Per pattern: `not_useful` rate (A7) + mute rate from `/api/risk/mutes`.
   A pattern many users mute is a false-positive pattern, and muting costs the user one tap —
   we already have that data and have never looked at it.

**Why production-grade.** No new pipeline, no new storage, no new dependency — three read queries
over columns that already exist. And per §1.6, this is the layer whose absence let A2 and F1 live
for months. It is also the exact instrument Phase 6 needs before it can safely change detector
counting.

**Caveat to state honestly:** `detected_at` falls back to `now()` when a caller doesn't pass the
trade time. The engine does pass it; verify no other write path relies on the default before
trusting the p95, or the metric will read as suspiciously perfect.

---

### Phase 5 — "Planned" (G1)

Add a fourth outcome. `RiskAlert.outcome` is a plain `String` column, so this is a `VALID_OUTCOMES`
entry, a button in the sheet footer, and a column in the stats response — **verify migration 069
did not add a CHECK constraint** before assuming no migration is needed.

**Why it earns its place.** It is the only proposal in the entire review that respects the
zero-manual-input constraint while producing information we cannot otherwise get. `not_useful`
conflates *"your detection is wrong"* with *"I don't care"*; "Planned" separates intent from error,
which is precisely what Phase 4's precision proxy needs to mean anything. It is also charter-shaped:
a mirror asks whether that was deliberate; a blocker tells you to stop.

Sequence it **after** Phase 4 so the signal lands in an instrument that already exists, rather than
accumulating unread the way `not_useful` did.

**Risk.** Trivial technically. The real risk is the known one — 55 alerts, 0 outcomes — so treat
adoption as a hypothesis to measure, not a result to assume. If Planned also gets zero taps, that
is a finding about the surface, and Phase 4 will show it.

---

### Phase 6 — Strategy grouping (B3, G2)

The largest piece, and the one that changes engine output. Confirmed defect per §0.

**Approach.** Derive a `strategy_key` over CompletedTrades — same underlying, same expiry, entries
within a short window, same product — as an **additive** field. Raw rows stay untouched; nothing
is merged destructively. Then give the engine one shared helper for "how many trades happened
here", counting groups rather than legs, and route every count-based detector through it instead
of each one calling `len()` on its own list.

**Why additive and shared.** Rewriting CompletedTrade would put a heuristic in the ledger, and a
grouping heuristic *will* be wrong sometimes — a trader legging into a spread over ten minutes is
genuinely ambiguous. Keeping the raw rows means a bad grouping is a display and counting error,
never data loss. One shared counter means the next count-based detector cannot reintroduce the bug.

**Why this must ship behind shadow mode.** We have `detector_flags` and `BehaviorEvent.shadow`
already (§0). Run the regrouped counters in shadow, use Phase 4's readout to compare old vs new
firing on real sessions, then promote. This is exactly the migration path
`DetectorSpec.default_mode` was designed for and has not yet been used for in anger. **Changing
how alerts count without this comparison would be the single riskiest thing in the plan** — it
silently re-tunes every threshold a user has already calibrated against.

**Second-order effects to work through before starting:** thresholds in `trading_defaults.py` were
tuned against leg counts, so grouping will make alerts fire *less*, and the defaults may need
retuning; constitution trade-limit rules a user set while seeing leg counts change meaning;
`OpenPositionsTable` gets the strategy row the review asked for as a by-product; episodes (G2)
become expressible from the same key.

**Risk.** Highest in the plan, which is why it is last and gated on Phase 4 existing.

---

### Phase 7 — Rules that write themselves (G3, G4) — **SHIPPED 2026-08-09**

The two features you singled out. They are one feature at two ends of the data curve.

**What was built**

| Piece | Where |
|---|---|
| Suggestion engine (4 rules, pure functions over CompletedTrades) | `backend/app/services/rule_suggestion_service.py` |
| Endpoint | `GET /api/constitution/suggestions` |
| UI section on My Rules | `src/components/rules/RuleSuggestions.tsx` |
| Guest fixture | `DEMO_RULE_SUGGESTIONS` in `demoData.ts` + route in `guestMode.ts` |
| Tests | `backend/tests/test_rule_suggestions.py` (13) · `src/test/ruleSuggestions.smoke.test.tsx` (2) |

Four suggestions, each from 90 days of the user's own ledger: **daily trade limit** (the count
above which their sessions stop finishing green), **daily loss limit** (70th percentile of their
red days), **max consecutive losses** (the streak after which the next trade stops winning),
**cooldown after loss** (how long re-entries stay impaired).

Rules the implementation holds to:
- **Only tightening is ever proposed.** A rule already tighter than the data supports gets silence.
- **No counterfactuals** — "4 of your last 14 red sessions reached this limit", never "would have saved ₹X".
- **Sampling gates**: ≥10 sessions, ≥30 trades, ≥3 observations per side of a split, and a split
  must move the outcome rate by ≥15pp. Nothing shown beats a confident wrong limit the user would
  then be gated against loosening.
- **Cold start ≠ nothing-to-change.** Two different messages; conflating them teaches the user the
  feature is broken.
- **Multi-leg guard.** A CompletedTrade is per leg, so a trade-*count* limit is inflated for spread
  traders. The service detects spread trading (same underlying, entries within 60s) and **withholds**
  the trade-limit suggestion with the reason shown on screen. Phase 6's problem contained, not ignored.
- **Nothing auto-applies.** Accept posts the ordinary constitution PUT — same audit, same change control.

**G4 turned out to already exist**, and the real defect was a duplicate. `generate_defaults`
(experience × capital) has been in `ConstitutionService` all along and the wizard has shown
recommended rules at step 4 — but `OnboardingWizard.tsx` kept **its own TypeScript copy of the
matrix**, and that copy had already drifted: it never set `max_position_size`, so every user has
been posting the hardcoded `50000` into a field the backend defines as a **percent**
(`ConstitutionUpdate` validates `0.1–100`). Same duplication class as A2 and F1, third instance.
The wizard now calls `POST /api/constitution/generate` and uses all five returned values, keeping
prior values if the call fails so a dead request cannot block onboarding.

**Original plan text follows.**

**G4, presets.** A new user has no history, so nothing can be derived; an empty constitution means
the engine has no user-specific constraints at all on day one. Three or four presets — conservative
/ standard / active, expressed in the same `RULE_FIELDS` the constitution already uses — make the
rule engine functional from the first session. This is the cold-start problem in another costume.

**G3, suggestions.** Once there is history, stop guessing: compute the rule from their ledger and
offer it. *"In your last 30 sessions you finish green in 82% of sessions with 6 or fewer trades,
and 31% above that. Set your trade limit to 6?"* One tap to accept.

**Why production-grade, and why this order.** Presets first because they need no data and unblock
day one; suggestions second because they need Phase 6's grouping to count correctly (a suggestion
built on leg-inflated trade counts would recommend the wrong limit) and Phase 4 to verify anyone
accepts them. The constitution gate already handles the dangerous direction — tightening applies
instantly, loosening returns 409 `override_required` (`constitution_service.py`) — so an accepted
suggestion cannot be used to quietly weaken a rule.

**The discipline that keeps this honest:** a suggestion must cite the numbers it came from and
never be auto-applied. We are proposing a rule from the user's own evidence, which is the mirror
philosophy working as intended; applying it for them would be the blocker we refuse to be.

---

## 4. Sequencing summary

```
Phase 1  Notification integrity      independent, do first, before Twilio goes live
Phase 2  One pattern vocabulary      independent; unblocks 3 and 6
Phase 3  Honest context              needs 2
Phase 4  Measurement                 independent; needed by 5 and 6
Phase 5  "Planned" outcome           needs 4
Phase 6  Strategy grouping           needs 2 and 4; highest risk, gated on shadow
Phase 7  Presets, then suggestions   presets independent; suggestions need 4 and 6
```

Phases 1, 2 and 4 are the ones that would have prevented this entire list from existing.
Phase 6 is the one that most improves detection accuracy. Phase 7 is the one that most improves
the product.

## 5. What is deliberately not here

`B4` (SessionLog on Dashboard), `B5` (staleness indicator), `G5` (escalation warning) and `G6`
(glossary page) are all placement or surfacing work that belongs with the rev6 rollout, not in a
correctness pass. G6 in particular costs almost nothing once Phase 2 lands.

One caution on B5: a staleness indicator that is wrong is worse than none — a "live" badge on
stale prices is a stronger false claim than no badge at all. It needs a real freshness signal from
the ticker, not a timestamp on last render.
