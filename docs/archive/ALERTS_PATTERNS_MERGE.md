> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> Merge shipped; /my-patterns redirects. Its "28 detectors" is historical.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# Alerts + My Patterns — should they merge?

Researched 2026-08-01. Sources: the Lovable mockup, this repo's page-ownership rule, the shipped code for both pages, and published notification-UX practice.

**Verdict: yes, merge — but the reason is not the one that motivated the question, and Lovable does not do what you would expect.**

---

## 1. What Lovable actually does

Worth stating plainly because it cuts against the assumption: **Lovable does not merge Alerts with Patterns.**

- **Alerts** merges with **Rules** — left is the alert stream (active/history, severity filter, past cost per card), right is a live rules panel with toggles and threshold sliders, and four money stats across the top.
- **Patterns** stays separate as a **master-detail cost-leak browser** — per-pattern cost, frequency, trend, triggers, related trades.

So Lovable's answer is "merge Alerts with the thing that *changes behaviour* (rules), and keep the cost browser separate."

**But that Patterns role is now filled.** Analytics → Behaviour already is the ranked cost-leak browser: leak, money, occurrences, the rule that constrains it, and when it happened. We shipped Lovable's Patterns screen into Analytics last week. That is what makes the merge question live.

## 2. The overlap is real, and it is bidirectional

Not a matter of taste — the two pages already reach into each other:

| Page | Contains | Whose job it is |
|---|---|---|
| `Alerts.tsx` | a **Patterns tab** (`PatternsTab` + `ResponseStatsCard`) | My Patterns |
| `MyPatterns.tsx` | **`AlertHistoryCard`** | Alerts |
| `MyPatterns.tsx` | **`BehaviourCostCard`** | Analytics, since the port |

Our own rule reads: *Analytics owns quantified cost · Alerts owns live loop + response stats · My Patterns owns at-a-glance scorecard.* All three clauses are currently violated by the code.

## 3. What is actually left of My Patterns

This is the argument. After Analytics took quantified cost, My Patterns holds:

- `StreakTrackerCard` — **the hero, and a streak counter.** The charter bans gamification explicitly: no badges, XP, streaks, trophies.
- `BehaviorScoresCard` — a behaviour score. `quality_score` is populated by no service and is a constant; the Weekly Discipline Score was already killed for the same reason.
- `BehaviourCostCard` — now duplicated with Analytics.
- `AlertHistoryCard` — belongs to Alerts.
- `PatternCalendar` — a genuine asset, and the research says a calendar answers *when do I trade well* better than any table.
- Recommendations / worst-pattern callout — thin.

**Strip the duplicated and the charter-violating, and roughly one and a half blocks remain.** That is not a page. My Patterns is not a screen that lost an argument; it is a screen whose content moved out from under it.

## 4. So: one page, and what it is for

Merge into **Alerts**, which keeps the route. `/my-patterns` redirects.

The merged screen answers one question in two tenses:

- **What fired** — the live loop. Newest first, what triggered it, whether it was reviewed.
- **What keeps firing** — the same behaviours ranked by *frequency and trend*, not money. Money is Analytics'.

That split keeps the ownership rule intact rather than breaking it further: Analytics owns cost, this page owns the loop and the repetition, and nothing is computed twice.

**Moves off the page entirely:** streak tracker (gamification), behaviour score (constant, not real), `BehaviourCostCard` (Analytics owns it). **Moves on:** the pattern calendar, retitled to what it answers.

## 5. How it should look

**No coloured left edge and no tinted row.** This is a standing rule now: that treatment is reserved for live behavioural alerts on the Dashboard, where something has just fired and wants attention. On a page that is *entirely* alerts it communicates nothing — every row would carry it — and a wall of red-striped, red-tinted rows is severity theatre. Severity is carried by a dot, the category chip, and order.

Beyond that:

- **GitHub's triage model.** Its notification inbox works because every row carries a *reason label* — "you were mentioned", "you're reviewing" — so dozens can be triaged by relevance in seconds. We already have the vocabulary: `SIZE / PACE / EMOTIONAL / RISK`. It should be the primary scan target, not decoration.
- **The default for a new event is silence.** The published guidance is that alert fatigue comes from a low bar. Our engine has 28 detectors and the measured evidence is 55 alerts, 0 outcomes recorded. That is the fatigue signature. The page should make *unreviewed* the exception worth showing, not the wall.
- **Kite's table treatment**, as on Analytics: `10px 12px` cells, tabular numerals, no zebra, tint the column that matters. Rows ≥44px on mobile.
- **One dominant region**, per the reference research: not a stack of equal cards. The live loop leads; the repetition summary supports.
- **A pattern row states plain language + number + one action** — the same rule that fixed Analytics. A frequency count with no next step is the documented failure state.

## 6. What we are not taking from Lovable

- **Merging Rules into this page.** Rules already have a screen with a tighten-instantly / loosen-behind-friction mechanism, and the constitution gate is real logic, not a panel. Cross-link instead — which is what `BehaviourLead`'s action button already does.
- **Money on every alert row.** Analytics owns quantified cost. Repeating it here is the exact duplication this merge is meant to end.
