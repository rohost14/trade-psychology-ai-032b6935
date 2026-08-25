# `danger_zone_service` — consecutive-loss logic

26 Aug 2026. Review, then **APPROVED AND IMPLEMENTED the same day** — see
`## 6. What shipped` at the end. Closes limitation #1 recorded in `STATUS.md`
when `consecutive_loss_streak` was retired.

**Verdict: MODIFY.** It makes the same unsupported claim, on harsher terms, using
numbers the engine no longer trusts — while the trader's own declared limit is
already sitting in the dict it reads and is ignored.

---

## 1. What it currently does

`app/services/danger_zone_service.py:222-243`, inside `assess_danger_level`.

```python
consec_caution  = trader_thresholds['consecutive_loss_caution']   # 3 at cold start
consec_danger   = trader_thresholds['consecutive_loss_danger']    # 5 at cold start
consec_critical = consec_danger + 2                               # 7 — inline, no key

if consecutive_losses >= consec_critical:   # CRITICAL + HARD_COOLDOWN
    recommendations.append(f"{consecutive_losses} consecutive losses. Take a break.")
elif consecutive_losses >= consec_danger:   # DANGER + SOFT_COOLDOWN
    recommendations.append("Consider pausing to reset mentally.")
elif consecutive_losses >= consec_caution:  # WARNING, no intervention
    triggers.append("consecutive_loss_warning")
```

`consecutive_losses` is `facts.consecutive_losses` — **the identical canonical
session fact** the retired detector read (changed to session scope 2026-08-23,
`test_danger_zone_session_scope.py`).

### Where it is used

| caller | live? | what happens |
|---|---|---|
| `GET /api/danger-zone/status` | routed, **no frontend caller** | returns level/triggers/recommendations |
| `POST /api/danger-zone/trigger-intervention` | routed, **no frontend caller** | starts cooldown, notification, WhatsApp |
| `GET /api/danger-zone/summary` | routed, **no frontend caller** | same assessment |
| **`api/zerodha.py:893-919`, inside `sync/all`** | **YES — this is the live path** | assesses on every sync; if `danger`/`critical`, calls `trigger_intervention` |

`grep` across `src/` finds **one** occurrence of "danger zone" in the entire
frontend: a marketing bullet on `Welcome.tsx:366`. Nothing calls the API.

### What an intervention actually does

Traced end to end, because the tier names promise more than they deliver:

| tier | intervention | real-world effect |
|---|---|---|
| WARNING (3) | `NONE` | **nothing.** `zerodha.py` only intervenes at danger/critical, and no client reads the response |
| DANGER (5) | `SOFT_COOLDOWN` | writes a `Cooldown` row. **`check_cooldown` has exactly one caller — this same service.** `/api/cooldown` is routed but has no frontend caller either. Nothing is blocked, nothing is shown |
| CRITICAL (7) | `HARD_COOLDOWN` + `NOTIFICATION` | cooldown row; `notification_sent` is recorded but **no push is actually sent** (`trigger_intervention` only sends WhatsApp, and only at CRITICAL); **WhatsApp to the guardian's phone**, gated on `profile.guardian_enabled`, and Twilio is in SAFE MODE until `TWILIO_*` is set |

So the only consequence that reaches a human today is **a WhatsApp to a third
party at 7 consecutive losses.** `InterventionType.TRADING_BLOCK` and
`SOFT_WARNING` are never assigned anywhere — dead enum members.

## 2. Does it duplicate the retired detector?

**Yes — the same claim, from the same fact, against the same two thresholds.**

| | retired `consecutive_loss_streak` | `danger_zone_service` |
|---|---|---|
| streak source | `ctx.facts.consecutive_losses` | `facts.consecutive_losses` — **same** |
| caution/warning at | `consecutive_loss_caution` (3) | `consecutive_loss_caution` (3) — **same key** |
| danger at | `consecutive_loss_danger` (5) | `consecutive_loss_danger` (5) — **same key** |
| extra tier | — | `danger + 2` = 7, inline literal, no key, no test |
| what it asserts | a run of N losses is a state worth interrupting | identical |
| consequence | a `RiskAlert` | a cooldown, and at 7 a message to the trader's guardian |

The evidence that retired the detector applies unchanged: **63 of 189 sessions
contained a 3+ loss run against 63.0 expected** by shuffling at the trader's
39.9% win rate; the 5-tier is 7 observed against 7.4 expected. The counts carry
no information about state.

**It is worse here in one specific way.** The engine's version produced an alert
the trader could read and dismiss. This one escalates to a person who is not the
trader, on a number nobody chose, with no way for the trader to see why.

### The personalisation does not rescue it

`consecutive_loss_caution` / `_danger` can resolve from history —
`loss_streak_p60` / `loss_streak_p85`, percentiles of the trader's own streak
distribution (`baseline_service.py:399-400`, `threshold_resolution.py:410-415`).
That is **fairer across traders** than a flat 3, because it self-normalises for
win rate.

**But it does not make the count evidence.** If runs occur at exactly the rate
chance produces — which is the measured finding — then the p60 of a trader's own
run distribution is the p60 of a distribution their win rate already determines.
It answers *"is this run long for you?"*, and the answer is *"runs this long
happen to you at a predictable rate."* Percentile-of-noise is still noise. It
also does not reach a new user at all: cold start is the flat 3 / 5 / 7.

## 3. Should it use the declared `max_consecutive_losses` instead?

**Yes, and the value is already there.** `get_thresholds(profile)` returns
`max_consecutive_losses` (`trading_defaults.py:471`,
`threshold_resolution.py:491` — `Source.FACT`, "declared"). Verified against the
live code:

```
cold start        consecutive_loss_caution=3  _danger=5  max_consecutive_losses=None
declared limit 4  consecutive_loss_caution=3  _danger=5  max_consecutive_losses=4
```

**The trader's declared 4 is in the same dictionary the service reads, on the
same line, and the service uses 3 / 5 / 7 instead.**

The consequence is not academic. A trader who declared a limit of 4:

| streak | their rule says | `constitution_violation` says | `danger_zone_service` says |
|---|---|---|---|
| 3 | one away | **caution** (as of `6534146`) | WARNING — inert |
| **4** | **broken** | **danger — breached** | still WARNING — nothing |
| 5 | — | critical (125%) | DANGER → soft cooldown |
| 7 | — | critical | CRITICAL → **WhatsApp to guardian** |

**The danger zone stays silent at the exact moment the trader broke their own
rule, then escalates to their guardian at nearly double it.** The two surfaces
disagree about the same trader at the same moment, which is the class of defect
`session_facts` was built to end.

There is a further problem with substituting the declared value directly:
`max_consecutive_losses` is `None` for anyone who has not completed onboarding.
`constitution_violation` handles that correctly — **no declaration, no check**.
The danger zone would have to do the same, which means **the consecutive-loss
trigger disappears entirely for undeclared traders.** That is the honest outcome
and it should be stated as the intent, not worked around with a fallback.

## 4. Blast radius of changing it

| surface | affected? | detail |
|---|---|---|
| `DangerZoneResponse` schema | **No** | `consecutive_losses` stays a reported field; only `level`/`triggers`/`recommendations` change value |
| frontend | **No** | nothing calls the API |
| `sync/all` response | **shape no, values yes** | `results["danger_zone"]` keeps its keys; fewer `danger`/`critical` levels |
| cooldowns written | **Yes — fewer** | the only writer besides `POST /api/cooldown/start` |
| WhatsApp to guardians | **Yes — fewer** | currently the only human-visible effect |
| `_get_notification_type` | two dead keys | `consecutive_loss_critical`, `consecutive_loss_danger` |
| `RiskAlert` rows | **No** | the danger zone writes none |
| **tests** | **1 file, 1 test** | `test_danger_zone_session_scope.py::test_todays_losses_still_escalate` asserts 7 losses reach danger/critical with a `consecutive_loss*` trigger |

**That test must be retargeted, not deleted.** Its subject is session scoping —
that yesterday's run does not carry — and that subject survives. It currently
uses the consecutive tiers as its vehicle for "today's still count".

## 5. Recommendation — **MODIFY, do not delete the service**

Delete the *claim*, keep the *service*. Loss-limit and overtrading triggers are
untouched by this review and are not count-of-losses claims.

### Exact changes required — for approval, not implemented

| # | change | file | why |
|---|---|---|---|
| 1 | Delete the three-tier `consec_caution` / `consec_danger` / `consec_critical` block | `danger_zone_service.py:222-243` | same unsupported claim as the retired detector, from the same fact and the same two keys |
| 2 | Replace it with **one** check against `trader_thresholds['max_consecutive_losses']`, and **skip entirely when it is `None`** | same | the declared number is already in the dict; a commitment needs no evidence about tilt |
| 3 | Delete the inline `consec_danger + 2` | same | an unkeyed, untested literal deciding a message to a third party |
| 4 | Delete `TriggerThresholds.consecutive_loss_warning/_danger/_critical` (2/3/5) | `danger_zone_service.py:110-113` | **already dead** — the code reads `trader_thresholds`, never `self.thresholds`, for these |
| 5 | Retarget `test_todays_losses_still_escalate` onto the declared rule | `tests/test_danger_zone_session_scope.py` | its subject is session scoping and survives; give the fixture a declared limit |
| 6 | Drop the two now-dead keys from `_get_notification_type` | `danger_zone_service.py:375-376` | dead map entries read as though the triggers still exist |

**Severity mapping for #2, using only what already exists** — no new threshold,
no new multiplier. The service's own `_upgrade_level` vocabulary maps onto the
constitution ladder that shipped in `6534146`:

| streak vs declared limit | danger zone level | intervention |
|---|---|---|
| `limit − 1` | `WARNING` | `NONE` |
| `>= limit` | `DANGER` | `SOFT_COOLDOWN` |
| `>= 1.2 × limit` | `CRITICAL` | `HARD_COOLDOWN` |

The `1.2` is **not new** — it is `constitution_severe_pct`, already resolved and
already live. Using it keeps the two surfaces telling one story. If that is not
wanted, the alternative is no CRITICAL tier at all from consecutive losses, which
is also defensible and quieter.

### What is NOT proposed

Deleting `danger_zone_service`. Touching the loss-limit or overtrading triggers.
Adding a fallback when `max_consecutive_losses` is undeclared. Any change to
`consecutive_loss_caution` / `consecutive_loss_danger` themselves — they keep
their remaining readers (`api/profile.py`, `api/behavioral.py`,
`api/constitution.py`) and this review does not reach those.

### Recorded, not fixed here

- `danger_patterns` (`:264-273`) contains **`revenge_sizing` and
  `tilt_loss_spiral`, both retired pattern names**. They are set members, not
  `==` comparisons, so `test_no_shipping_module_compares_against_a_retired_pattern_name`
  does not catch them. Two dead entries claiming the engine still emits those.
- `TriggerThresholds` has **11 more fields that nothing reads**:
  `loss_limit_critical_percent`, `trades_per_15min_*`, `trades_per_hour_*`,
  `avoid_first_minutes`, `avoid_last_minutes`. Only
  `loss_limit_warning_percent` and `loss_limit_danger_percent` survive.
- `InterventionType.TRADING_BLOCK` and `SOFT_WARNING` are never assigned.
  `TRADING_BLOCK` also contradicts "mirror, not blocker" by name alone.
- `notification_sent: True` is recorded when **no notification is sent**. Only
  WhatsApp, only at CRITICAL. Misreports what happened.
- The whole service reaches no user: three routed endpoints with no frontend
  caller, and a cooldown table only it reads. **Whether it should exist at all is
  a product question this review does not answer.**

---

## 6. What shipped

Approved 26 Aug with **one adjustment: no `1.2 x limit` CRITICAL tier.** The
user's reasoning, recorded because it is the standing rule now: *there is no
evidence that a second severity level above the trader's declared limit adds
value, and `constitution_violation` already owns the severe percentage logic.*
So the danger zone has exactly two rungs and never escalates past the line the
trader drew.

### Final behaviour

| streak vs declared limit | level | intervention | trigger |
|---|---|---|---|
| below `limit - 1` | — | — | none |
| `limit - 1` (and `limit >= 2`) | `WARNING` | `NONE` | `consecutive_loss_warning` |
| `>= limit` | `DANGER` | `SOFT_COOLDOWN` | `consecutive_loss_danger` |
| **`max_consecutive_losses` is `None`** | **— no check at all —** | | |

`CRITICAL` and `HARD_COOLDOWN` are no longer reachable from consecutive losses,
so **consecutive losses can no longer send a WhatsApp to the trader's guardian**.
The loss-limit path still can; it was out of scope and is untouched.

### Changes made

| # | change | where |
|---|---|---|
| 1 | 3/5/7 ladder deleted; one check against declared `max_consecutive_losses`, skipped entirely when `None` | `danger_zone_service.py:222-263` |
| 2 | inline `consec_danger + 2` deleted | same |
| 3 | `TriggerThresholds.consecutive_loss_warning/_danger/_critical` deleted — confirmed dead before removal (the code read `trader_thresholds`, never `self.thresholds`, for these) | `danger_zone_service.py:110-113` |
| 4 | `consecutive_loss_critical` dropped from `_get_notification_type`; **`consecutive_loss_danger` KEPT** — that trigger still fires | `danger_zone_service.py:375` |
| 5 | module docstring no longer claims a "GRADUATED" escalating ladder | `danger_zone_service.py:14` |
| 6 | `test_todays_losses_still_escalate` retargeted onto a declared limit — its subject is session scoping, which survives | `tests/test_danger_zone_session_scope.py` |
| 7 | 12 new tests | `tests/test_danger_zone_consecutive_losses.py` |

**Deliberately NOT removed:** the `consecutive_loss_caution` /
`consecutive_loss_danger` *threshold keys*. They keep live readers in
`api/behavioral.py`, `api/constitution.py`, `api/profile.py`,
`core/threshold_registry.py` and the resolution ladder. **They now have zero
detector readers and are configuration/display values only** — that is a fact to
record, not a licence to delete them here.

### Still recorded, still not fixed — carried forward

Untouched by explicit instruction. Repeated here so they survive this document:

1. `danger_patterns` (`:264-273`) lists **`revenge_sizing` and `tilt_loss_spiral`,
   both retired pattern names**. Set membership, so the retired-name contract
   test does not catch them.
2. `TriggerThresholds` has **8 remaining fields nothing reads**:
   `loss_limit_critical_percent`, `trades_per_15min_warning/_danger`,
   `trades_per_hour_warning/_danger`, `avoid_first_minutes`,
   `avoid_last_minutes`. Only `loss_limit_warning_percent` and
   `loss_limit_danger_percent` survive.
3. `InterventionType.TRADING_BLOCK` and `SOFT_WARNING` are never assigned.
   `TRADING_BLOCK` contradicts "mirror, not blocker" by name alone.
4. `notification_sent: True` is recorded when **no notification is sent** — only
   WhatsApp, only at CRITICAL.
5. **The whole service reaches no user.** Three routed `/api/danger-zone`
   endpoints with no frontend caller; a `Cooldown` table only it reads. Whether
   it should exist at all is a product question no review has answered.
6. `consecutive_loss_caution` / `consecutive_loss_danger` are now
   detector-orphaned (see above).
