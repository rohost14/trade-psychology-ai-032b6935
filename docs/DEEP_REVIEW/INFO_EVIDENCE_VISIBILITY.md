# INFO Evidence Visibility — CLOSED DECISION

**29 Aug 2026. Product/architecture rule. Decided, not pending.**

Raised by the Pattern 13 review, which found that `danger_zone_service` contains
a `rapid_reentry` CAUTION path that cannot be taken, and that four detectors
write evidence no trader-facing surface reads. The question was whether to
activate that path.

**It is not activated. The rule below is the answer, and it is closed.**

---

## The rule

1. **`severity="info"` patterns are evidence and analytics only.**
2. **INFO events MUST NOT create `RiskAlert` rows.**
3. **INFO events MUST NOT influence `danger_zone`, severity escalation, or any
   trader-facing alert.**
4. **The existing `rapid_reentry` CAUTION path in `danger_zone_service` MUST NOT
   be activated.**
5. **No INFO pattern may be promoted to a trader-facing alert.**
6. **Making an INFO pattern trader-facing is an explicit future product
   decision** — never a bug fix, never a side effect of tidying.

---

## Why this is a decision and not a defect

`danger_zone_service.py:310` lists `rapid_reentry` in `caution_patterns`, but
`_get_recent_alerts` queries `RiskAlert` and `behavior_engine.py:376` skips info
severities before any `RiskAlert` is built. The path is unreachable.

**Calling that a dead branch invites the wrong repair.** Anyone "fixing" it has
exactly two options, and both change the product rather than correct an error:

- make an analytics-disposition detector notify, or
- make the danger zone read `BehaviorEvent` evidence.

The first changes what interrupts a trader. The second changes what the danger
zone means. Neither is a one-line correction, so the inconsistency is recorded
as **intentional** and the path stays as written.

---

## What this rule protects

The separation between **recording** and **interrupting**.

An `info` event is the product's memory: it makes a clean session
distinguishable from an unmonitored one, and it is what analytics and the
journal are built from. An alert is an interruption. Letting the first leak into
the second would raise alert volume without any decision being taken about
whether those behaviours deserve to interrupt anyone — which is precisely how
alert fatigue arrives unnoticed.

`§1C.8` already states the related half: suppression is a notification-layer
concern, and suppressed evidence is still recorded. This rule is the mirror —
recorded evidence does not become notification.

---

## Affected detectors — recorded, unchanged

Four detectors are `severity="info"` with `disposition=analytics`:

| detector | status |
|---|---|
| `rapid_reentry` | Pattern 13, **KEEP AS-IS**, reviewed 29 Aug |
| `panic_exit` | source-list #6, not yet reviewed |
| `early_exit` | source-list #14, not yet reviewed |
| `opening_5min_trap` | source-list #19, not yet reviewed |

Verified across all 15 `BehaviorEvent` readers: nothing trader-facing consumes
them. Every reader either filters `severity != "info"` or sources from
`RiskAlert`. The sole reader is an admin aggregate.

**That is the intended state, not a gap.** The remaining three still get their
own reviews; this rule settles only the visibility question, so those reviews do
not have to reopen it.

---

## Enforcement

`backend/tests/test_info_evidence_visibility.py` pins every clause. The rule is
not a convention — a change that lets an INFO event reach `RiskAlert`, the
danger zone, or a notification channel fails the suite.

## Not decided here

Whether evidence with no reader should be **written at all**. That is a separate
question about the value of the analytics disposition, and it does not affect
this rule: if the answer is ever "stop writing it", INFO events still must not
become alerts in the meantime.
