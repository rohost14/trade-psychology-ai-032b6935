# External review (ChatGPT transcript) — what survives contact with the code

Source: `docs/taxdocx.txt`, 789 lines, 2026-08-08. Three separate conversations: a product
critique/VVFU/RICE assessment, a dashboard redesign round, and an overall UI/UX direction.

Every claim below was checked against the repo. **Findings only — nothing implemented.**

Headline: the review's *product* advice is ~70% already shipped. But verifying it exposed a
cluster of real defects in the **WhatsApp alert layer** — a subsystem that appears to have
been written early and never revisited while the engine moved to v2.

---

## A. Real defects, found while verifying the review's claims

The review said *"do not diagnose emotion, describe observable events"* (line 33–35) and
*"default the partner message to a rule breach, not P&L"* (line 125). Checking whether we
already comply surfaced six issues in `alert_service.py` and its caller.

**The in-app engine is fine.** `behavior_engine.py:845` produces
`"{burst_count} positions opened {entry_range}{loss_note}"` — observable, evidenced,
no diagnosis. The WhatsApp path is a separate, stale codebase.

### A1. Critical alerts never send on WhatsApp — silent drop
`alert_service.py:39`
```python
if risk_alert.severity != "danger":
    return False
```
Caller `trade_tasks.py:1357` gates on `alert.severity in ("danger", "critical")`.
So `critical` — the most severe class we have — passes the caller's gate, reaches
`send_risk_alert`, and is discarded. The task records `results["whatsapp"] = <False>`
and moves on. Severity vocabulary is `info/caution/danger/critical`.

### A2. Every WhatsApp message falls through to the generic branch
`alert_service.py:66–104` branches on `overtrading`, `revenge_sizing`, `consecutive_loss`.
None of those are detector names. The registry (`detector_registry.py:59–138`) has
`overtrading_burst` / `daily_overtrading`, `size_escalation`, `consecutive_loss_streak`.
All three tailored messages are dead code; every alert renders the `else` branch.

### A3. The guardian receives the message written for the trader
`trade_tasks.py:1364` calls `send_risk_alert(alert, account, phone)` where `phone` is
`user.guardian_phone`. That formatter is second-person:

> ⚠️ *REVENGE TRADING DETECTED* — Position size increased 50% after recent trade.
> 🛑 *STOP IMMEDIATELY* — You are in tilt mode. Close this position and step away.

A third party gets "you are in tilt mode". `_format_guardian_alert` (`alert_service.py:166`)
exists and is correctly third-person — it has **zero production callers**; only
`test_notifications.py` reaches it, via `send_risk_alert_with_guardian`, which nothing in
`app/` calls. A correct implementation exists and is not wired up.

### A4. Guardian message footer leaks the Zerodha client ID
`alert_service.py:116` — `f"Account: {broker_account.broker_user_id}"`. On the guardian
path that discloses the trader's broker client ID to a third party. Review line 123:
*"let the trader choose the information disclosed"*; DPDP purpose limitation. Nothing in
the guardian flow needs it.

### A5. Live guardian path does not check `guardian_confirmed`
`trade_tasks.py:1350–1364` gates on `phone` + `guardian_eligible` + `severity` + monthly
budget. It never reads `user.guardian_confirmed`. `reports.py:453` **does** check it and
returns a 403 with "your guardian has not confirmed consent yet."

We built a proper WhatsApp consent handshake (`profile.py:885` sends "Reply YES to
confirm, NO to decline"; migration 056 stores `guardian_confirmed` / `_at`) — and the
highest-volume send path bypasses it. Weekly reports respect consent; real-time danger
alerts do not.

### A6. Copy contradicts the product charter
Same strings: "STOP TRADING NOW", "Take a mandatory 30-minute break", "You are in tilt
mode", "This pattern historically leads to major losses". That is blocker voice, an
emotional diagnosis from transactions alone, and an unsubstantiated causal claim —
the same class of problem `docs/LANDING_PAGE_AUDIT.md` flagged on `Welcome.tsx`.
Philosophy is "mirror, not blocker".

### A7. `not_useful` is collected and never reported
`risk.py:22` — `VALID_OUTCOMES = {"stopped", "took_anyway", "not_useful"}`.
`alert-response-stats` (`risk.py:327–354`) counts `total / acknowledged / stopped /
took_anyway`. `not_useful` is accepted, written, and never surfaced anywhere. It is the
only false-positive signal we have, and the review's gate #1 (80% precision on
high-severity alerts, line 165) is unmeasurable without it.

---

## B. Genuinely missing — the review is right and we have nothing

### B1. No event→alert latency measurement anywhere
Gate proposed: **under 5 seconds** (line 166). Grep for latency instrumentation across
`backend/app` returns three code comments and no metric. We cannot state our detection
latency today, and this is the cheapest gate to instrument: postback receipt timestamp →
`RiskAlert.detected_at`, recorded per alert. Directly feeds the Gate-3 live validation
already sitting in `docs/PENDING.md`.

### B2. No precision measurement / shadow mode
Review's experiment 2 (line 156): connect read-only, suppress display, measure missed
events and false positives. We have 28 detectors and no confusion matrix. A1–A2 above are
exactly the class of defect a shadow-mode pass catches. Cheapest usable version: report
`not_useful` rate per pattern (needs A7) plus a mute-rate-per-pattern read from
`/api/risk/mutes` — a pattern muted by many users is a false-positive pattern.

### B3. Multi-leg positions are not grouped into strategies
Review lines 254–262 and 550–553: show `NIFTY Bull Call Spread · 2 legs · +₹680`, expand
to legs. `OpenPositionsTable.tsx` has no match for `strategy|spread|legs` — every option
leg is its own row. For F&O this is the single largest per-screen readability gap the
review identified, and it is not a design problem — it needs leg-pairing logic in the
backend. It also has second-order value: `size_escalation` and `excess_exposure` on a
four-leg iron condor are counting legs, not risk. Worth a separate look at whether any
detector is currently miscounting spread legs as independent positions.

### B4. Session timeline is not on the Dashboard
Review lines 554–564. `SessionLog.tsx` exists but lives in `src/components/analytics/`.
The review's argument is that a compact factual timeline (`10:18 closed −₹1,200 · 10:24
similar position reopened · 10:56 pace alert`) gives an alert its context *without
navigating away*. That is a placement decision for the rev6 rollout, and it costs no new
backend work — `/api/analytics/session-log` already serves it.

### B5. Data freshness is not visible
NN/h "visibility of system status" (line 96): show whether broker data is connected,
delayed, or unavailable. We have a shared KiteTicker, a webhook path and an EOD sync;
if the ticker drops, the P&L on screen goes stale silently. Related to the known
misleading-empty bug class already in memory.

---

## C. Already shipped — no action, do not re-litigate

| Review recommendation | Where it already lives |
|---|---|
| Read-only broker connection, no order placement | Zerodha OAuth, read scopes only |
| Evidence-based alert text, not emotional diagnosis | `behavior_engine.py` messages (in-app only — see A6) |
| Five deterministic MVP patterns | 28 detectors in `detector_registry.py` |
| Auto-populated journal, ask only for reasoning | `TradeJournalSheet.tsx` |
| User-defined rules + tighten-instant/loosen-gated | `constitution_service.py`, `RULE_FIELDS` |
| Separate partner consent, YES/NO handshake | `profile.py:885`, migration 056 |
| Alert snooze / user control | `/api/risk/mutes` per pattern |
| "Mark alert incorrect" | `not_useful` outcome (collected — see A7) |
| DPDP: notice, deletion, consent withdrawal | `api/account_data.py` export/delete/import |
| Guardian is emergency-only, not daily coaching | `guardian_eligible` on 2 of 28 detectors + monthly budget |
| EOD behavioural summary | `report_tasks.py` |
| Flat, low-card, full-width alerts, no gimmicks | rev6 — the review independently reached the same conclusion |

The UI/UX section (lines 425–786) is worth reading only as **confirmation**: it arrives
at flat surfaces, thin dividers, cards only for summary/drawer/empty/modal, full-width
alerts, no confetti or streaks, no motivational quotes, one screen of density — which is
where rev6 already landed after seven rejections. Its specific values (blue primary,
12–22px radius, Inter) are behind our current tokens; do not adopt them.

---

## D. Reject, with reason

- **"Import three months of trades and have users label episodes"** (line 155). Kite gives
  no trade history; Console CSV import is the only path, and asking users to hand-label
  episodes runs straight into the zero-manual-input constraint (55 alerts → 0 outcomes).
  A weaker but real version: run the engine over an imported tradebook in a dry-run mode
  and compare against the alerts the live pipeline produced for the same days.
- **"Delay broad analytics"** (line 85) and the RICE table ranking analytics last (line 139).
  Analytics is built and approved. Sunk.
- **Portable behavioural-risk layer / MCP server / broker-embedded distribution**
  (lines 176–188). Correct long-term read, but we are blocked on Zerodha multi-user
  approval for a single-broker consumer product. Not now.
- **"Show a maximum of three unresolved alerts"** (line 508). `RecentAlertsCard` shows 4
  with a "more" affordance. Arbitrary difference, no evidence either way.
- **Reposition for Wolters Kluwer** (line 18) — artifact of ChatGPT's own context, not ours.

---

## E. Worth keeping for the landing page (still unapproved)

The landing hook — **"Catch the trading pattern before it becomes the day"** (line 291) —
promises intervention without promising profit, which is precisely the constraint
`LANDING_PAGE_AUDIT.md` imposes. Its sequence (hero with a real alert mockup → how it
works → during-market / post-trade / long-term → trust and privacy → pricing →
disclaimer, line 324) is a reasonable skeleton, and the explicit "never present alerts as
guaranteed protection against losses" (line 127) matches the audit's P0s.

Still the same blocker as before: no approved visual reference. This is copy and
structure, not a design direction.

---

## F. The three-layer alert system — we already have it, and it is better

Review's proposal (lines 499–523, 670–672): row → click → right-side drawer → optional
full review, never a page navigation.

**Shipped.** `AlertDetailSheet.tsx`, opened from `Alerts.tsx:786` and from the Dashboard
(`Dashboard.tsx:603` sets `selectedAlert`, `:677` renders the same sheet). Layer 1 is the
row in `RecentAlertsCard`; layer 2 is the sheet; layer 3 is the Alerts page history.

The sheet already carries more than the review asked for:

| Review asked for | Have |
|---|---|
| Complete evidence | `pattern.description` + a `buildFacts` data table |
| Related trades | "Trades involved" block from `details.losing_trades` / `trade_list` |
| Why it triggered | "Why this fired" — stacked confidence signals with importance |
| User feedback | Footer outcome buttons, writes `/alerts/{id}/feedback` |
| Journal action | Journal button in the sheet |
| — | Confidence %, per-pattern mute, IST + relative timestamps |
| Timeline | **missing** — the only piece of the review's list we do not render |

So the answer to "do we have the three-layer system" is yes. But the layer-2 content has
three defects of its own:

### F1. Pattern-keyed copy uses names that do not exist — same bug as A2, in the frontend
`TRADER_BENCHMARKS`, `PATTERN_EXPLANATIONS` and `buildFacts` are all keyed on
`alert.pattern.backend_type` with **no normalisation** (`AlertDetailSheet.tsx:180`).
All three contain a key `overtrading`. The registry has `overtrading_burst` and
`daily_overtrading`. **Overtrading alerts — among our most frequent — open a sheet with
no facts table, no explanation and no context block.**

### F2. Coverage is 13 of 28 detectors
Everything else falls through silently: `excess_exposure`, `session_meltdown`,
`early_exit`, `winning_streak_overconfidence`, `expiry_day_overtrading`,
`cooldown_violation`, `constitution_violation`, `same_symbol_obsession`,
`time_of_day_bias`, `win_rate_collapse`, `strategy_breakdown`, `direction_instability`,
`options_premium_avg_down`, `premium_loss_event`, `daily_overtrading`. `buildFacts`
covers 10. A user who triggers one of those gets a description and nothing else.

The structural fix is to move this copy **backend-side onto the DetectorSpec**, where it
cannot drift from the pattern name again — the registry is already declarative. That also
delivers the review's line 112 ("define every behavioural pattern and the evidence used to
detect it") for free.

### F3. The benchmark statistics are invented
`AlertDetailSheet.tsx:21–35`, comment: *"Based on trading psychology research and
aggregate behavioral data."* No source exists. Examples shipping to users today:

> "Win rate on the 4th trade after 3 losses is typically below 30%."
> "Traders who escalate size after a loss sequence experience 2–3× their normal drawdown."
> "Options premiums in the first 5–8 minutes are typically 15–25% inflated."

These are precise, quantified, unsourced claims presented as fact — the same class as the
fabricated per-pattern costs `docs/LANDING_PAGE_AUDIT.md` flags as P0 on `Welcome.tsx`,
and the same class as A6's "historically leads to major losses". The "General pattern (not
individual advice)" label handles the SEBI risk, not the truthfulness one.

We already own the honest replacement: **My Record** computes the user's own history for
exactly this lookup. "The last 4 times you traded after three losses, you lost on 3 of
them" is both true and stronger. Where a user has no record yet (cold start), the correct
copy is the mechanism with no number attached.

### F4. `/risk/state` cannot represent `critical`
`risk.py:52` — `elif any(a.severity == "danger")` → `"danger"`, `else` → `"caution"`.
A session whose only unacknowledged alert is `critical` reports **`caution`**. Same
severity-vocabulary drift as A1, on the endpoint that drives the dashboard's session
status. The review's four-level ladder (Stable / Elevated / High Risk / Critical, line 221)
is the right shape; we have three levels and the top one is unreachable.

---

## G. New features in the transcript — what is actually new, ranked

### G1. A "Planned" one-tap action on an alert — **the best idea in the document**
Line 248: alert actions are *View context*, **Planned**, *Not accurate*.

`VALID_OUTCOMES = {stopped, took_anyway, not_useful}` (`risk.py:22`). There is no way to
say **"this was my plan"**. That is a different statement from all three: the trade was
deliberate and pre-intended, so the alert is correct about the facts and wrong about the
concern.

Why this one matters more than it looks:
- It is **one tap, no typing** — the only kind of input this user base has ever given us
  (55 alerts → 0 outcomes is an argument against forms, not against taps).
- It is the **cleanest false-positive signal we can get**. `not_useful` conflates "wrong
  detection" with "I don't care". "Planned" separates intent from error, which is exactly
  what a precision measurement (B2) needs.
- It **feeds the constitution**: a pattern repeatedly marked Planned is a rule the user
  actually trades by, and is the raw material for G3.
- It matches the charter better than anything else in the review — a mirror asks "was this
  deliberate?", a blocker tells you to stop.

Cost is small: one enum value, one button, one column in `alert-response-stats`.
Pair it with A7 (surface `not_useful`) and the response stats become a real precision
instrument rather than an engagement metric.

### G2. Trade episodes as a user-facing unit
Line 224 lists "Trade episodes" alongside trades in the session summary. We already have
the concept **internally** — `journal.py:91`, `analytics.py:941` and
`TradeJournalSheet.tsx:183` all pass "a synthetic per-episode id" — but the user never
sees it. An episode (a cluster of trades on one instrument inside one window) is the unit
the behaviour engine actually reasons about, and "3 episodes, 11 trades" says something
"11 trades" does not. Low cost, mostly surfacing something that exists.

### G3. Rule suggestions derived from the user's own data
Line 186: an agent for post-session coaching, weekly summaries **and rule suggestions**.
The first two ship (`coach`, `report_tasks.py`). The third does not exist —
grep for `suggest_rule` / `rule_suggestion` returns nothing.

This is the strongest fit for the zero-manual-input constraint of anything in the
document: the user never authors a rule, they accept or reject one we computed.
*"Your last 30 sessions: you finish green in 82% of sessions with 6 or fewer trades, and
in 31% above that. Set trade limit to 6?"* — one tap, and it is factual, from their own
ledger, not a benchmark we invented (see F3).

Interaction with the constitution gate is already handled: tightening applies instantly,
loosening needs an override (`constitution_service.py`).

### G4. Rule presets at onboarding
Line 106: presets for new traders, custom rules for the experienced. None exist. This is
the cold-start problem in a different costume — a new user has no history, so G3 cannot
suggest anything, and an empty rules page produces no engine constraints at all. A preset
is the only thing that makes the constitution useful on day one. Worth pairing with G3:
preset first, replaced by data-derived suggestions once there is data.

### G5. Warn before enabling over-sensitive escalation
Line 102 (NN/h error prevention). If a user sets a guardian rule that would ping their
accountability partner constantly, tell them before saving. We enforce this on our side —
`guardian_eligible` on 2 of 28 detectors plus a monthly budget — but the user cannot see
that reasoning at the moment they configure it. Small, and it protects the guardian
relationship, which is the fragile part.

### G6. Standalone pattern glossary
Line 112. Partly in the sheet (F1/F2), nothing browsable. Falls out of the F2 fix almost
free if the copy moves onto `DetectorSpec` — a page that lists all 28 patterns, what each
observes, and the threshold that fires it. It is also the honest answer to "why did I get
this alert", and doubles as pre-sale content.

### Considered and not worth it
- **Four-level status ladder** — the level names are cosmetic; the actual defect is F4.
- **"Max three alerts"** (line 508) vs our four. No evidence either way.
- **Merge Journal into Alerts nav** (line 659) — we already merged My Patterns into Alerts;
  a second merge makes Alerts a dumping ground.
- **Subtle live updates, no flashing** (lines 690–702) — already the rev6 position; the one
  live-pulse dot in `RecentAlertsCard` is a design call, not a feature.

---

## Suggested order

1. **A1–A6 as one fix pass** — the WhatsApp layer is currently sending consent-bypassing,
   client-ID-leaking, charter-violating copy to third parties, while silently dropping the
   most severe class. Highest severity, and it is one file plus its caller.
2. **F1 + F4** — same stale-name and severity-vocabulary drift, now on screen. F1 means our
   most common alert type opens an empty sheet.
3. **F3** — invented statistics, shipping to users. Truthfulness, not design; the same call
   as the landing-page P0s.
4. **G1 ("Planned") + A7 + B1** — one enum value, one button, two metrics. Together they
   turn Gate-3 live validation from a judgement call into a measurement.
5. **F2** — move pattern copy onto `DetectorSpec`; G6 then costs almost nothing.
6. **G3 + G4** — rule suggestions and presets. Real work, and the two features here that
   survive the zero-manual-input constraint intact.
7. **B3** — strategy grouping. Check the detector-miscount question first.
8. **B4, B5, G2, G5** — fold into the rev6 rollout.
